from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # JWT
    jwt_secret: str = "change-me-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # App
    app_env: str = "development"
    cors_origins: str = "*"

    # Optional direct DB URL
    database_url: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
