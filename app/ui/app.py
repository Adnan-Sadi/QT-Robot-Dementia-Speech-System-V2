import customtkinter as ctk
from app.ui.widgets.transcript_panel import TranscriptPanel
from app.ui.widgets.activity_grid import ActivityGrid
from app.ui.widgets.status_bar import StatusBar
from app.config.settings import settings

class MainWindow(ctk.CTk):
    def __init__(self, controller, bus):
        super().__init__()
        self.title("QT Robot Dementia Speech System")
        self.geometry("900x650")
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._controller = controller
        self._bus = bus

        # Layout
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        start_btn = ctk.CTkButton(header, text="Start Chat", command=self._on_start)
        stop_btn = ctk.CTkButton(header, text="Stop Chat", command=self._on_stop)
        start_btn.pack(side="left", padx=8, pady=8)
        stop_btn.pack(side="left", padx=8, pady=8)

        # Center: transcripts
        self.transcripts = TranscriptPanel(self)
        self.transcripts.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # Right: activities
        #side = ctk.CTkFrame(self)
        #side.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        #side.grid_rowconfigure(1, weight=1)

        #side_title = ctk.CTkLabel(side, text="Activities", font=("", 16, "bold"))
        #side_title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        #self.activities = ActivityGrid(side, settings.activity_images_dir, on_select=self._on_activity)
        #print( "Loading activity images from:", settings.activity_images_dir)
        #self.activities.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # Input bar: live transcript preview + Send button
        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))
        input_frame.grid_columnconfigure(0, weight=1)

        self._transcript_preview = ctk.CTkLabel(
            input_frame,
            text="(Start chat and speak — your words will appear here)",
            anchor="w",
            text_color="gray",
        )
        self._transcript_preview.grid(row=0, column=0, sticky="ew", padx=12, pady=8)

        self._send_btn = ctk.CTkButton(
            input_frame, text="Send", width=120,
            command=self._on_send, state="disabled"
        )
        self._send_btn.grid(row=0, column=1, padx=8, pady=8)

        # Footer: status bar
        self.status = StatusBar(self)
        self.status.grid(row=3, column=0, columnspan=2, sticky="ew")

        self._poll_bus() # start polling for events to update UI

    def _on_start(self):
        self._send_btn.configure(state="normal")
        self._transcript_preview.configure(
            text="(Listening...)", text_color="gray"
        )
        self._controller.start_chat()

    def _on_stop(self):
        self._send_btn.configure(state="disabled")
        self._transcript_preview.configure(text="(Session ended)", text_color="gray")
        self._controller.stop_chat()

    def _on_send(self):
        self._send_btn.configure(state="disabled")
        self._controller.send_message()

    def _on_activity(self, name: str):
        # Placeholder: later, publish an event or call controller to start that activity
        self.transcripts.append("ACTIVITY", f"Selected: {name}")

    def _poll_bus(self):
        ev = self._bus.try_get()
        if ev:
            if ev.kind == "log":
                self.transcripts.append("LOG", ev.text)
            elif ev.kind == "stt":
                # Legacy single-utterance transcript
                self.transcripts.append("User", ev.text)
            elif ev.kind == "stt_interim":
                # Live preview of accumulating speech — show in preview label
                self._transcript_preview.configure(text=ev.text, text_color="gray")
            elif ev.kind == "stt_final":
                # Accumulated text was sent — show in chat history, reset preview
                self.transcripts.append("User", ev.text)
                self._transcript_preview.configure(
                    text="(Listening...)", text_color="gray"
                )
                self._send_btn.configure(state="normal")
            elif ev.kind == "llm":
                self.transcripts.append("Cognibot", ev.text)
                # Re-enable Send after robot responds
                self._send_btn.configure(state="normal")
            elif ev.kind == "status":
                self.status.set(ev.text)
        self.after(60, self._poll_bus) # poll ~16 fps