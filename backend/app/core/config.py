"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve the repository-root .env regardless of CWD (this file lives at
# <repo>/backend/app/core/config.py → parents[3] is <repo>).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Central configuration.  All values come from env vars (or .env)."""

    # Database
    database_url: str = "postgresql+asyncpg://conceptlens:conceptlens@localhost:55432/conceptlens"

    # File storage
    upload_dir: str = "storage/uploads"

    # Application
    debug: bool = False

    model_config = {"env_prefix": "CONCEPTLENS_", "env_file": str(_ENV_FILE)}


settings = Settings()
