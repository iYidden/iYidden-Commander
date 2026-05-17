from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    backend_url: str = Field(..., description="Backend websocket URL")
    agent_api_key: str = Field(..., min_length=16, description="Shared secret with backend")
    agent_name: str = Field(default="unnamed-agent", description="Identifies this agent")
    heartbeat_interval: int = Field(default=30, ge=5, description="Heartbeat frequency in seconds")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
