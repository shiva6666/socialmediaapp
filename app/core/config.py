from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./insta_clone.db"
    # Replace this through SECRET_KEY before exposing the app outside local development.
    secret_key: str = "local-development-only-change-me"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"
    media_dir: str = "uploads"
    redis_url: str = "redis://localhost:6379/0"
    feed_cache_ttl_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
