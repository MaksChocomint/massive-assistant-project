"""Настройки приложения. Значения берутся из переменных окружения или файла .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/assistant"
    # Сколько раз можно уточнять одну команду, прежде чем она получит статус failed
    max_clarifications: int = 3
    log_level: str = "INFO"


settings = Settings()
