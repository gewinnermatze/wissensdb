from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WISSENSDB_", env_file=".env", extra="ignore")

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    database_url: str | None = None
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "wissensdb"
    postgres_user: str = "wissensdb"
    postgres_password: str = "change-me"
    embedding_provider: str = "hash"
    embedding_dimension: int = 384
    agent_tokens: str = Field(
        default="agent-token-reader:reader-agent:reader,"
        "agent-token-contributor:coding-agent:contributor"
    )
    openai_embedding_model: str = "text-embedding-3-small"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        host = self.postgres_host
        database = quote_plus(self.postgres_db)
        return f"postgresql+psycopg://{user}:{password}@{host}:{self.postgres_port}/{database}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
