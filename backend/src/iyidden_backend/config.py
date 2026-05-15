from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000

    jwt_secret: str = Field(min_length=32)
    agent_api_key: str = Field(min_length=16)

    anthropic_api_key: str = ""

    db_path: str = "./iyidden.db"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8000"

    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 30 * 24 * 60 * 60
    mashpia_setup_token_ttl_seconds: int = 24 * 60 * 60

    @property
    def db_path_abs(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[2] / p
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
