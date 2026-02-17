import customtkinter as ctk
from pathlib import Path
from typing import Callable, List, Tuple


class ActivityGrid(ctk.CTkFrame):
    def __init__(self, master, images_dir: str, on_select: Callable[[str], None]):
        super().__init__(master)
        self.on_select = on_select
        self._load(images_dir)


    def _load(self, images_dir: str):
        images: List[Tuple[str, ctk.CTkImage]] = []
        for path in Path(images_dir).glob("*.png"):
            try:
                img = ctk.CTkImage(light_image=str(path), dark_image=str(path), size=(96, 96))
                images.append((path.stem, img))
            except Exception:
                pass


        # grid them
        for i, (name, img) in enumerate(images):
            r, c = divmod(i, 4)
            btn = ctk.CTkButton(self, image=img, text=name.replace("_", " ").title(), compound="top",
            command=lambda n=name: self.on_select(n))
            btn.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            self.grid_columnconfigure(c, weight=1)
        if not images:
            lbl = ctk.CTkLabel(self, text="No activity images found.")
            lbl.grid(row=0, column=0, padx=8, pady=8)