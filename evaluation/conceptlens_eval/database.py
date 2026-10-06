"""Only caller-supplied local /postgres administration; never use app DB settings."""
import asyncio
import os
import re
import subprocess
import uuid
from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy.engine import make_url
from .common import ROOT

PREFIX = "conceptlens_eval_"


def validate_admin(value: str):
    url = make_url(value)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"} or url.database != "postgres" or url.host not in {"localhost","127.0.0.1","::1"} or url.query:
        raise ValueError("evaluation requires an explicit local PostgreSQL /postgres admin URL without query options")
    return url


def validate_disposable(value: str):
    url = make_url(value)
    if not re.fullmatch(PREFIX+r"[0-9a-f]{32}",url.database or ""):
        raise ValueError("not an evaluation-owned disposable database")
    return url


@asynccontextmanager
async def disposable_database(admin_url: str, events: list):
    admin = validate_admin(admin_url)
    name = PREFIX + uuid.uuid4().hex
    target = admin.set(database=name,drivername="postgresql+asyncpg")
    validate_disposable(target.render_as_string(hide_password=False))
    connection = await asyncpg.connect(admin.set(drivername="postgresql").render_as_string(hide_password=False))
    created = False
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
        created = True
        events.append({"action":"created","database":name})
        result = await asyncio.to_thread(subprocess.run,
            [str(ROOT/"backend/.venv/bin/python"),"-m","alembic","upgrade","0006"],cwd=ROOT/"backend",
            env={**os.environ,"CONCEPTLENS_DATABASE_URL":target.render_as_string(hide_password=False)},
            text=True,capture_output=True,timeout=120)
        if result.returncode:
            raise RuntimeError("disposable migration failed; database will be dropped (connection details redacted)")
        events.append({"action":"migrated","revision":"0006"})
        yield target.render_as_string(hide_password=False)
    finally:
        try:
            if created:
                validate_disposable(target.render_as_string(hide_password=False))
                await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
                exists = await connection.fetchval("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)",name)
                if exists: raise RuntimeError("disposable database cleanup failed")
                events.append({"action":"dropped","database":name,"absence_verified":True})
        finally:
            await connection.close()


async def check_lifecycle(admin_url: str, *, fail_inside: bool = False) -> dict:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    events = []
    try:
        async with disposable_database(admin_url,events) as url:
            engine = create_async_engine(url)
            try:
                async with engine.begin() as db:
                    revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
                    if revision != "0006": raise AssertionError("unexpected migration revision")
                    await db.execute(text("INSERT INTO courses (id,name) VALUES (:id,'Evaluation lifecycle fixture')"),{"id":uuid.uuid4()})
                    events.append({"action":"seeded_and_checked","revision":revision})
                    if fail_inside: raise RuntimeError("intentional lifecycle failure")
            finally:
                await engine.dispose()
    except RuntimeError as exc:
        if not fail_inside or str(exc)!="intentional lifecycle failure": raise
        events.append({"action":"intentional_failure_cleanup_verified"})
    return {"label":"TEST FIXTURE — NOT A SUBMISSION RESULT","normal_development_db_touched":False,"events":events}
