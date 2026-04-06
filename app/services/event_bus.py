from dataclasses import dataclass
from queue import Queue, Empty
from typing import Literal, Optional

EventType = Literal["log", "stt", "llm", "status", "stt_interim", "stt_final"]

@dataclass
class Event:
    kind: EventType
    text: str

class EventBus:
    def __init__(self):
        self._q: Queue[Event] = Queue()

    def publish(self, kind: EventType, text: str):
        self._q.put(Event(kind, text))

    def try_get(self, timeout: float = 0.0) -> Optional[Event]:
        try:
            return self._q.get(timeout=timeout)
        except Empty:
            return None