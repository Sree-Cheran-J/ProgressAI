from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "ProgressAI"
    environment: str = "development"
    api_prefix: str = "/api"
    secret_key: str = Field(min_length=32)
    access_token_minutes: int = 60
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_database: str = "progressai"
    frontend_origins: str = "http://127.0.0.1:5500,http://localhost:5500"
    enable_scheduler: bool = False
    reminder_interval_minutes: int = 15
    reminder_hours_before_deadline: int = 24
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    model_dir: str = "ml/artifacts"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
