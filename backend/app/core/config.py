"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration.  All values come from env vars (or .env)."""

    # Database
    database_url: str = "postgresql+asyncpg://conceptlens:conceptlens@localhost:5432/conceptlens"

    # File storage
    upload_dir: str = "storage/uploads"

    # Application
    debug: bool = False

    model_config = {"env_prefix": "CONCEPTLENS_", "env_file": ".env"}


settings = Settings()
