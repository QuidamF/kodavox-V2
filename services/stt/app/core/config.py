import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Speech-to-Text Microservice"
    
    # Whisper Settings
    MODEL_SIZE: str = "small"
    DEVICE: str = "cpu"
    MODELS_DIR: str = "./models"
    LANGUAGE: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
