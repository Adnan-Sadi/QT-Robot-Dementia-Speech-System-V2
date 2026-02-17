# app/config/settings.py
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    python_executable: str = "python" # or absolute path to the venv python
    speech_app: str = "speech_app.py" 
    ros_recognize_service: str = "/qt_robot/speech/recognize"
    # Use an absolute path for activity images so widgets can load them reliably
    activity_images_dir: str = str(PROJECT_ROOT.joinpath("assets", "activities"))


settings = Settings()
