import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings:
    # Backend Configuration
    BASE_HTTP_URL = os.getenv("BASE_HTTP_URL", "https://cognibot.org")
    WS_PATH = os.getenv("WS_PATH", "/ws/chat/")
    SOURCE = os.getenv("SOURCE", "qtrobot")
    USERNAME = os.getenv("USERNAME")
    PASSWORD = os.getenv("PASSWORD")

    # STT Configuration
    STT_ENGINE = os.getenv("STT_ENGINE", "gspeech").lower()
    
    # Audio Configuration
    AUDIO_RATE = int(os.getenv("AUDIO_RATE", "16000"))
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en-US")
    SPEECH_MODEL = os.getenv("SPEECH_MODEL", "default")
    USE_ENHANCED_MODEL = os.getenv("USE_ENHANCED_MODEL", "True").lower() == "true"
    
    # Speech Speed
    SPEECH_SPEED = int(os.getenv("SPEECH_SPEED", "90"))
    
    # Timeout Configuration
    DEFAULT_TIMEOUT = float(os.getenv("DEFAULT_TIMEOUT", "20.0"))
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "25.0"))
    
    # Emotion Configuration
    EMOTION_LISTENING = os.getenv("EMOTION_LISTENING", "QT/confused,QT/showing_smile").split(",")

settings = Settings()
