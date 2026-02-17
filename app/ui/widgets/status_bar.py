import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, height=32)
        self.label = ctk.CTkLabel(self, text="Ready")
        self.label.pack(side="left", padx=8)


    def set(self, text: str):
        self.label.configure(text=text)