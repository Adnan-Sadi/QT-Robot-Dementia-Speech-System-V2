# app/main.py
from app.ui.app import MainWindow
from app.services.event_bus import EventBus
from app.controllers.chat_controller import ChatController

def main():
    bus = EventBus()
    controller = ChatController(bus)
    win = MainWindow(controller, bus)
    win.mainloop()

if __name__ == "__main__":
    main()