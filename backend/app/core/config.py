from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Clothing Store IMS"
    database_url: str = "postgresql+psycopg://ims:ims@localhost:5432/ims"
    jwt_secret: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: list[str] = ["http://localhost:3000"]
    cookie_secure: bool = False
    store_timezone: str = "Asia/Kolkata"

    first_admin_email: str = "admin@store.local"
    first_admin_password: str = "admin123"


@lru_cache
def get_settings() -> Settings:
    return Settings()
