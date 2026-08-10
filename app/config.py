"""App configuration — typed, env-driven.

Rule: never read os.environ directly in app code. Go through `settings`.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "aieng"
    postgres_host: str = "db"
    postgres_port: int = 5432

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    default_chat_model: str = "gemini-3.5-flash-lite"
    default_embed_model: str = "BAAI/bge-m3"
    embed_dimensions: int = 1024
    ollama_base_url: str = "http://localhost:11434"

    # Shopify API
    shopify_store_domain: str | None = None
    shopify_access_token: str | None = None
    shopify_api_version: str = "2024-04"
    shopify_rate_limit_per_min: int = 100  # REST Admin API limit

    # Vision
    ollama_vision_model: str = "llama3.2-vision"

    daily_cost_cap_usd: float = 0.50
    user_daily_cost_cap_usd: float = 0.10
    admin_api_key: str = "tarik-proje"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
