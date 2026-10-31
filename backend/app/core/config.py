from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./backend/sugarcane.db"
    frontend_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    access_token_minutes: int = 60
    max_upload_bytes: int = 10 * 1024 * 1024
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    image_model_path: str = ""
    enable_experimental_image_model: bool = False
    risk_model_path: str = ""
    enable_experimental_risk_model: bool = False

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def secure_production_settings(self):
        if self.app_env.lower() == "production":
            if self.secret_key == "development-only-change-me" or len(self.secret_key) < 32:
                raise ValueError("Production requires a SECRET_KEY with at least 32 characters.")
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true.")
            if self.cookie_samesite.lower() == "none" and not self.cookie_secure:
                raise ValueError("SameSite=None requires secure cookies.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def resolved_database_url(self) -> URL:
        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            return url

        database_path = Path(url.database)
        if not database_path.is_absolute():
            project_root = Path(__file__).resolve().parents[3]
            database_path = project_root / database_path
        database_path = database_path.resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return url.set(database=str(database_path))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
