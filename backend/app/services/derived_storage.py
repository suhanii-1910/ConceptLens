"""Derived-artifact storage — stores extraction outputs separately from originals.

Derived artifacts (extracted images, etc.) are stored under:

    <upload_dir>/../derived/<source_version_id>/

This keeps them completely separate from original uploaded source files.
"""

import uuid
from pathlib import Path

from app.core.config import settings


def derived_dir_for(source_version_id: uuid.UUID) -> Path:
    """Return the derived-artifact directory for a source version.

    Creates the directory if it does not exist.
    """
    # Derive from the same parent as the upload dir
    base = Path(settings.upload_dir).resolve().parent / "derived" / str(source_version_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_derived_filename(*, prefix: str, page_index: int, img_index: int, ext: str) -> str:
    """Generate a safe, deterministic filename for a derived artifact.

    Example: ``page_003_img_001.png``
    """
    return f"{prefix}_page_{page_index:04d}_img_{img_index:04d}.{ext.lstrip('.')}"
