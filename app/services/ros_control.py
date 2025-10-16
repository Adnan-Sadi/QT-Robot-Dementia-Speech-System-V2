import subprocess
import threading
from typing import Optional, Callable
from app.config.settings import settings


class ROSControl:
    def __init__(self):
        self._speech_proc: Optional[subprocess.Popen] = None
        self._stdout_thread: Optional[threading.Thread] = None


    def start_speech_app(self, on_started: Optional[Callable[[str], None]] = None, on_log: Optional[Callable[[str], None]] = None):
        """
        Start speech_app.py and stream its stdout/stderr lines to on_log(callback).
        on_started is called once immediately after launching.
        """
        
        if self._speech_proc and self._speech_proc.poll() is None:
            if on_started: 
                on_started("speech_app.py is already running.")
            return

        # Start the speech app in a background process and capture stdout/stderr
        self._speech_proc = subprocess.Popen(
            [settings.python_executable, settings.speech_app],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Start a thread to read stdout lines and forward them to on_log
        def _reader(proc, callback):
            try:
                if proc.stdout:
                    for raw_line in proc.stdout:
                        line = raw_line.rstrip("\n")
                        if callback:
                            try:
                                callback(line)
                            except Exception:
                                # swallow callback exceptions to keep reader alive
                                pass
            except Exception:
                pass

        self._stdout_thread = threading.Thread(target=_reader, args=(self._speech_proc, on_log), daemon=True)
        self._stdout_thread.start()

        if on_started: 
            on_started("Launched speech_app.py")


    def stop_speech_app(self, on_log: Optional[Callable[[str], None]] = None):
        if self._speech_proc and self._speech_proc.poll() is None:
            self._speech_proc.terminate()
            if on_log: 
                on_log("Terminated speech_app.py")
        else:
            if on_log: on_log("speech_app.py not running.")
