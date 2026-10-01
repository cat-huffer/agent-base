from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path.cwd().resolve()
ENV_FILE = PROJECT_ROOT / ".env"
SESSION_DB_PATH = PROJECT_ROOT / ".data" / "sessions.sqlite3"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    default_model_profile: str = "default"
    log_level: str = "INFO"
    session_db_path: Path = SESSION_DB_PATH
    openai_tracing_api_key: str | None = None

    @field_validator("session_db_path")
    @classmethod
    def resolve_session_db_path(cls, path: Path) -> Path:
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path


settings = Settings()
