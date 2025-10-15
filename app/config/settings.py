# app/config/settings.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    python_executable: str = "python" # or absolute path to the venv python
    speech_app: str = "speech_app.py" 
    ros_recognize_service: str = "/qt_robot/speech/recognize"
    activity_images_dir: str = "app/assets/activities" # Future directory for activity images


settings = Settings()