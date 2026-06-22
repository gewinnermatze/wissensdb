from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WISSENSDB_", env_file=".env", extra="ignore")

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    database_url: str = "postgresql+psycopg://wissensdb:change-me@localhost:5432/wissensdb"
    embedding_provider: str = "hash"
    embedding_dimension: int = 384
    agent_tokens: str = Field(
        default="agent-token-reader:reader-agent:reader,"
        "agent-token-contributor:coding-agent:contributor"
    )
    openai_embedding_model: str = "text-embedding-3-small"


@lru_cache
def get_settings() -> Settings:
    return Settings()
