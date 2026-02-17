import customtkinter as ctk


class TranscriptPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)


        self.title = ctk.CTkLabel(self, text="Chat History", font=("", 16, "bold"))
        self.title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))


        self.textbox = ctk.CTkTextbox(self, width=600, height=320)
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=16)
        self.textbox.configure(state="disabled")


    def append(self, tag: str, text: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f"[{tag}] {text}\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")
