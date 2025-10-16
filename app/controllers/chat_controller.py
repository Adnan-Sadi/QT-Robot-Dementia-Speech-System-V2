# app/controllers/chat_controller.py
from app.services.ros_control import ROSControl
from app.services.event_bus import EventBus


class ChatController:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.ros = ROSControl()
   
    # Publishes a “Starting chat…” status event.
    # Publishes a “Starting chat…” status event.
    def start_chat(self):
        self.bus.publish("status", "Starting chat…")

        # on_started -> log (one-off)
        def on_started(msg: str):
            self.bus.publish("log", msg)

        # on_log receives raw lines from speech_app stdout; parse and publish proper events
        def on_log(raw_line: str):
            if not raw_line:
                return
            line = raw_line.strip()

            # STT transcript lines (examples from speech_app)
            # "Transcript: <text>"
            if line.startswith("Transcript:"):
                text = line.split("Transcript:", 1)[1].strip()
                if text:
                    self.bus.publish("stt", text)
                else:
                    self.bus.publish("log", line)
                return
            
            # Recognized printed final detection
            # "Detected [<text>]"
            if line.startswith("Detected ["):
                # attempt to extract inside brackets
                try:
                    content = line.split("Detected [", 1)[1].rstrip("]")
                    if content:
                        self.bus.publish("stt", content)
                        return
                except Exception:
                    pass

            # LLM reply lines
            # "Cognibot: <reply>"
            if line.startswith("Cognibot:"):
                reply = line.split("Cognibot:", 1)[1].strip()
                if reply:
                    self.bus.publish("llm", reply)
                else:
                    self.bus.publish("log", line)
                return

            # Everything else -> log
            self.bus.publish("log", line)

        # Start speech app and stream logs
        self.ros.start_speech_app(on_started=on_started, on_log=on_log)

    def stop_chat(self):
        self.bus.publish("status", "Stopping chat…")
        self.ros.stop_speech_app(on_log=lambda m: self.bus.publish("log", m))

    # # Hooks for incoming STT/LLM events 
    # # need to wire these up to the pipeline later
    # def on_stt_text(self, text: str):
    #     self.bus.publish("stt", text)

    # def on_llm_text(self, text: str):
    #     self.bus.publish("llm", text)
