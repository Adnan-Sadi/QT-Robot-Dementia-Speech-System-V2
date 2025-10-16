import subprocess
import threading
from typing import Optional, Callable
from app.config.settings import settings


class ROSControl:
    def __init__(self):
        self._speech_proc: Optional[subprocess.Popen] = None


    def start_speech_app(self, on_started: Optional[Callable[[str], None]] = None):
        if self._speech_proc and self._speech_proc.poll() is None:
            if on_started: 
                on_started("speech_app.py is already running.")
            return
        # Start the speech app in a background process
        self._speech_proc = subprocess.Popen([settings.python_executable, settings.speech_app])
        if on_started: 
            on_started("Launched speech_app.py")


    def stop_speech_app(self, on_log: Optional[Callable[[str], None]] = None):
        if self._speech_proc and self._speech_proc.poll() is None:
            self._speech_proc.terminate()
            if on_log: 
                on_log("Terminated speech_app.py")
        else:
            if on_log: on_log("speech_app.py not running.")
