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

    # Video Processing
    video_transcription_model: str = "mlx-community/whisper-base-mlx"
    video_max_frames: int = 15
    video_min_frame_gap_seconds: float = 2.0
    video_subprocess_timeout_seconds: int = 300

    # Application
    debug: bool = False

    # Embedding config
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    embedding_batch_size: int = 32

    # LLM Provider Configuration
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    vision_model: str | None = None
    llm_timeout_seconds: float = 45.0
    provider_mode: str = "compatible"
    openai_api_key: str | None = None

    model_config = {"env_prefix": "CONCEPTLENS_", "env_file": str(_ENV_FILE)}


settings = Settings()
