import json
import asyncio
import threading
from urllib.parse import urlencode
from typing import Optional, Tuple
import contextlib

import aiohttp

class BackendClient:
    """
    - Auth: POST {BASE}/api/token/ -> {'access','refresh'}
    - WS :  wss://{HOST}/ws/chat/?token=<access>&source=<client>
    - Send: {"type":"transcription","data":"..."}
    - Receive: 'llm_response', 'emotion', etc.
    """

    def __init__(self, base_http: str, ws_path: str, source: str = "qtrobot"):
        self.base_http = base_http.rstrip("/")
        self.ws_path = ws_path if ws_path.startswith("/") else "/" + ws_path
        self.source = source

        self._http: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._listen_task: Optional[asyncio.Task] = None

        self.access: Optional[str] = None
        self.refresh: Optional[str] = None
        self.ws_url: Optional[str] = None

        # For request/response pairing in a single-flight fashion
        self._pending_future: Optional[asyncio.Future] = None

        # Prevents one send operation from overwriting another pending future before the first one completes.
        self._lock = asyncio.Lock()

    # ---------------------------
    # Lifecycle
    # ---------------------------
    async def start(self):
        self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) # maximum number of seconds for the whole operation
        await self._login() # get token and prepare ws_url
        await self._connect_ws() # connect to websocket
        self._listen_task = asyncio.create_task(self._listen_loop()) # start listen loop

    async def stop(self):
        if self._listen_task:
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._http:
            await self._http.close()

    async def _login(self):
        assert self._http
        url = f"{self.base_http}/api/token/"
        # Expect USERNAME/PASSWORD in environment
        username = "buddy_user"
        password = "1"

        if not username or not password:
            raise RuntimeError("USERNAME and PASSWORD must be set in environment")
        # get token
        async with self._http.post(url, json={"username": username, "password": password}) as r:
            if r.status != 200:
                raise RuntimeError(f"Token request failed: {r.status} {await r.text()}")
            data = await r.json()
        # fetch the access and refresh token from the response
        # In our case, both access and refresh are the same JWT token
        self.access = data.get("access")
        self.refresh = data.get("refresh")

        if not self.access:
            raise RuntimeError(f"Missing 'access' in token response: {data}")
        # prepare the websocket url
        scheme = "wss" if self.base_http.startswith("https") else "ws"
        qs = urlencode({"token": self.access, "source": self.source})
        self.ws_url = f"{scheme}://{self.base_http.split('://',1)[1]}{self.ws_path}?{qs}"

    async def _connect_ws(self):
        assert self._http and self.ws_url
        headers = {"Origin": self.base_http}
        # aiohttp uses its own ping/pong mechanism to keep the connection alive
        # if the server does not respond within 20 seconds, the connection is closed
        self._ws = await self._http.ws_connect(self.ws_url, headers=headers, heartbeat=20)

    # ---------------------------
    # Listen & dispatch
    # ---------------------------
    async def _listen_loop(self):
        assert self._ws
        while True:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
               
                mtype = data.get("type")
                if mtype == "llm_response":
                    # Resolve pending future with (text, emotion)
                    async with self._lock:
                        text = data.get("data")
                        emotion = data.get("emotion")
                        
                        if self._pending_future and not self._pending_future.done():
                            # resolves the pending future with the received response
                            # This unblocks the await that was waiting for it.
                            self._pending_future.set_result((text, emotion))


            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                # Try to reconnect with backoff
                await self._reconnect_with_backoff()
            elif msg.type == aiohttp.WSMsgType.ERROR:
                await self._reconnect_with_backoff()

    async def _reconnect_with_backoff(self):
        # simple exponential backoff up to 30s
        delay = 1
        while True:
            try:
                await asyncio.sleep(delay)
                await self._connect_ws()
                return
            except Exception:
                delay = min(delay * 2, 30)

    # ---------------------------
    # Public API (async)
    # ---------------------------
    async def send_transcription_and_wait(self, text: str, timeout: float = 20.0) -> Tuple[str, str]:
        """Send a transcription and wait for the next llm_response.
        Returns: (llm_text, emotion)
        """
        if not text.strip():
            return "", [], None
            
        async with self._lock:
            # It represents a single result that will be available in the future - either a value or an exception.
            # It is similar to Promise in Javascript
            self._pending_future = asyncio.get_running_loop().create_future()

        payload = {"type": "transcription", "data": text}
        assert self._ws
        await self._ws.send_str(json.dumps(payload))
        try:
            return await asyncio.wait_for(self._pending_future, timeout=timeout)
        finally:
            async with self._lock:
                # resets pending future to None after completion
                self._pending_future = None


class BackendBridge:
    """
    Thread-safe facade for ROS code.
    Spins an asyncio loop in a background thread and exposes blocking methods.
    """

    def __init__(self):
        # currently hardcoded, should move to an env or config file
        base = "https://cognibot.org"
        ws_path = "/ws/chat/"
        source = "qtrobot"
        if not base:
            raise RuntimeError("BASE must be set in .env or environment")
        self._client = BackendClient(base, ws_path, source)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._started = threading.Event()

    def start(self):
        self._thread.start()
        fut = asyncio.run_coroutine_threadsafe(self._client.start(), self._loop)
        fut.result()  # raise if fails
        self._started.set()

    def stop(self):
        if not self._started.is_set():
            return
        fut = asyncio.run_coroutine_threadsafe(self._client.stop(), self._loop)
        try:
            fut.result(timeout=5)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    def send_transcript_and_wait(self, text: str, timeout: float = 20.0) -> Tuple[str, str]:
        if not self._started.is_set():
            raise RuntimeError("BackendBridge not started. Call start() first.")
        fut = asyncio.run_coroutine_threadsafe(
            self._client.send_transcription_and_wait(text, timeout),
            self._loop,
        )
        return fut.result()
