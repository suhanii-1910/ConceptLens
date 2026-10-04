"""Pytest configuration — provides an async test client backed by an in-memory SQLite DB.

This lets tests run without a real PostgreSQL instance.  SQLite doesn't support
pgvector or PG-specific types natively, but we substitute UUID columns with
String and skip pgvector in the test environment.  The goal is to test
application logic, not database engine features.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force test settings before any app import
os.environ.setdefault("CONCEPTLENS_DATABASE_URL", "sqlite+aiosqlite:///")
os.environ.setdefault("CONCEPTLENS_UPLOAD_DIR", "/tmp/conceptlens_test_uploads")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("USE_FAKE_EMBEDDING", "1")

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402

# Import models to populate Base.metadata
import app.models  # noqa: E402, F401


# ---- in-memory SQLite engine & session ----

TEST_ENGINE = create_async_engine("sqlite+aiosqlite:///", echo=False)
TestSessionLocal = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db():
    """Create all tables before each test and drop after."""
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


# ---- FastAPI test client ----

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient wired to the FastAPI app with test DB."""
    async def _override_get_db():
        async with TestSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


# ---- upload-dir helper ----

@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    """Point file storage at a temporary directory for each test."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(upload_dir))
