# app/controllers/chat_controller.py
from app.services.ros_control import ROSControl
from app.services.event_bus import EventBus


class ChatController:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.ros = ROSControl()
   
    # Publishes a “Starting chat…” status event.
    def start_chat(self):
        self.bus.publish("status", "Starting chat…")
        self.ros.start_speech_app(on_started=lambda m: self.bus.publish("log", m))
        self.ros.trigger_recognize(on_log=lambda m: self.bus.publish("log", m))

    def stop_chat(self):
        self.bus.publish("status", "Stopping chat…")
        self.ros.stop_speech_app(on_log=lambda m: self.bus.publish("log", m))

    # Hooks for incoming STT/LLM events 
    # need to wire these up to the pipeline later
    def on_stt_text(self, text: str):
        self.bus.publish("stt", text)

    def on_llm_text(self, text: str):
        self.bus.publish("llm", text)