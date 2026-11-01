"""Настройки приложения. Значения берутся из переменных окружения или файла .env."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/assistant"
    # Сколько раз можно уточнять одну команду, прежде чем она получит статус failed
    max_clarifications: int = Field(default=3, ge=1, le=20)
    log_level: str = "INFO"
    speech_model_path: str = "data/models/vosk-model-small-ru-0.22"


settings = Settings()
