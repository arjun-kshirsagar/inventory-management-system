from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Clothing Store IMS"
    database_url: str = Field(
        default="postgresql+psycopg://ims:ims@localhost:5432/ims",
        validation_alias=AliasChoices(
            "DATABASE_URL",
            "POSTGRES_URL",
            "POSTGRES_URL_NON_POOLING",
        ),
    )
    jwt_secret: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: list[str] = ["http://localhost:3000"]
    cookie_secure: bool = False
    store_timezone: str = "Asia/Kolkata"

    first_admin_email: str = "admin@store.local"
    first_admin_password: str = "admin123"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Vercel's Supabase integration can append `supa` metadata to the URL;
        # psycopg/libpq treats it as a connection option and rejects it.
        parts = urlsplit(value)
        scheme = {
            "postgres": "postgresql+psycopg",
            "postgresql": "postgresql+psycopg",
        }.get(parts.scheme, parts.scheme)
        query = [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key != "supa"
        ]
        return urlunsplit(parts._replace(scheme=scheme, query=urlencode(query, doseq=True)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
