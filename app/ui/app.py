import customtkinter as ctk
from app.ui.widgets.transcript_panel import TranscriptPanel
from app.ui.widgets.activity_grid import ActivityGrid
from app.ui.widgets.status_bar import StatusBar
from app.config.settings import settings

class MainWindow(ctk.CTk):
    def __init__(self, controller, bus):
        super().__init__()
        self.title("QT Robot Dementia Speech System")
        self.geometry("900x600")
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Layout
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        start_btn = ctk.CTkButton(header, text="Start Chat", command=controller.start_chat)
        stop_btn = ctk.CTkButton(header, text="Stop Chat", command=controller.stop_chat)
        start_btn.pack(side="left", padx=8, pady=8)
        stop_btn.pack(side="left", padx=8, pady=8)

        # Center: transcripts
        self.transcripts = TranscriptPanel(self)
        self.transcripts.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # Right: activities
        side = ctk.CTkFrame(self)
        side.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        side.grid_rowconfigure(1, weight=1)

        side_title = ctk.CTkLabel(side, text="Activities", font=("", 16, "bold"))
        side_title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        self.activities = ActivityGrid(side, settings.activity_images_dir, on_select=self._on_activity)
        self.activities.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # Footer: status bar
        self.status = StatusBar(self)
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")

        self._bus = bus
        self._poll_bus() # start polling for events to update UI

    def _on_activity(self, name: str):
        # Placeholder: later, publish an event or call controller to start that activity
        self.transcripts.append("ACTIVITY", f"Selected: {name}")

    def _poll_bus(self):
        ev = self._bus.try_get()
        if ev:
            if ev.kind == "log":
                self.transcripts.append("LOG", ev.text)
            elif ev.kind == "stt":
                self.transcripts.append("STT", ev.text)
            elif ev.kind == "llm":
                self.transcripts.append("LLM", ev.text)
            elif ev.kind == "status":
                self.status.set(ev.text)
        self.after(60, self._poll_bus) # poll ~16 fps