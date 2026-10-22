from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "UGHS Student Management API"
    database_url: str = "postgresql+psycopg://ughs:ughs_dev@localhost:5432/ughs_students"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Roster uploads: reject anything bigger before parsing.
    max_upload_bytes: int = 5 * 1024 * 1024
    max_upload_rows: int = 2000

    # Only the roster-upload agent needs these; the rest of the API runs without a key.
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    agent_max_turns: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
