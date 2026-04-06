# app/controllers/chat_controller.py
import rospy
from app.services.ros_control import ROSControl
from app.services.event_bus import EventBus

# ROS param used to signal speech_app.py to send the accumulated transcript
SEND_PARAM = "/dss/send_requested"


class ChatController:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.ros = ROSControl()
   
    # Publishes a "Starting chat…" status event.
    def start_chat(self):
        self.bus.publish("status", "Chat Started")

        # on_started -> print to terminal (do not publish as UI log)
        def on_started(msg: str):
            print(msg, flush=True)

        # on_log receives raw lines from speech_app stdout; parse and publish only STT/LLM events
        def on_log(raw_line: str):
            if not raw_line:
                return
            line = raw_line.strip()

            # Live interim transcript (accumulating, not yet sent)
            if line.startswith("STT_INTERIM:"):
                text = line.split("STT_INTERIM:", 1)[1].strip()
                if text:
                    self.bus.publish("stt_interim", text)
                return

            # Final accumulated transcript (user clicked Send)
            if line.startswith("STT_FINAL:"):
                text = line.split("STT_FINAL:", 1)[1].strip()
                if text:
                    self.bus.publish("stt_final", text)
                return

            # STT transcript lines — legacy single-utterance format (keep for compatibility)
            # "Transcript: <text>"
            if line.startswith("Transcript:"):
                text = line.split("Transcript:", 1)[1].strip()
                if text:
                    self.bus.publish("stt", text)
                return
           
            # LLM reply lines
            # "Cognibot: <reply>"
            if line.startswith("Cognibot:"):
                reply = line.split("Cognibot:", 1)[1].strip()
                if reply:
                    self.bus.publish("llm", reply)
                return

            # Everything else -> do not publish to UI (already printed by ROSControl)
            # (keeps UI clean for only STT/LLM)
            return

        # Start speech app and stream logs
        self.ros.start_speech_app(on_started=on_started, on_log=on_log)

    def stop_chat(self):
        self.bus.publish("status", "Chat Stopped")
        self.ros.stop_speech_app(on_log=lambda m: self.bus.publish("log", m))

    def send_message(self):
        """Signal speech_app.py to flush its accumulated transcript to the backend."""
        try:
            rospy.set_param(SEND_PARAM, True)
            self.bus.publish("status", "Sending...")
        except Exception as e:
            self.bus.publish("status", f"Send failed: {e}")