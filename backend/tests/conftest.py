"""Test isolation.

The suite must never touch the development database. `app.db.database` builds
its engine from `get_settings()` at import time and that call is `lru_cache`d,
so DATABASE_URL has to be set *before* the first `app.*` import — which makes
conftest.py the only correct place for it. Nothing here may import `app`.

Without this, `tests/test_intake_e2e.py`'s module fixture deletes every
request, infra and investment row from whatever database the app is configured
for: running `pytest` after `make seed` used to silently empty the demo data
and leave the dashboard blank.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TEST_DB = Path(tempfile.gettempdir()) / "jansetu_pytest.db"
_TEST_DB.unlink(missing_ok=True)

# Environment beats the .env file in pydantic-settings, so this wins over any
# DATABASE_URL the developer has configured locally.
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

# Photographs go to a temp directory for the same reason the database does. The
# suite uploads images, and `services/evidence.store` writes them: pointed at the
# real `data/evidence`, a test run would deposit files named after tokens issued by
# the test database into the directory the demo serves from, where they would
# outlive the run and be indistinguishable from genuine case evidence.
_TEST_EVIDENCE = Path(tempfile.gettempdir()) / "jansetu_pytest_evidence"
os.environ["EVIDENCE_DIR"] = str(_TEST_EVIDENCE)

# Gemini is switched off for the suite unless explicitly asked for. Three reasons,
# in order of how much they hurt: a live model makes assertions about extraction
# non-deterministic, every run spends free-tier quota that the demo needs, and a
# network round trip per intake test turns a 2-second suite into a 30-second one.
#
# This also keeps the fallback path continuously exercised, which is the thing
# that has to work when a judge clones the repo with no key at all.
#
# Set JANSETU_TEST_LIVE_GEMINI=1 to run the same suite against the real model.
if os.environ.get("JANSETU_TEST_LIVE_GEMINI") != "1":
    os.environ["GEMINI_API_KEY"] = ""


@pytest.fixture(scope="session", autouse=True)
def _discard_test_database():
    """Leave no database file behind for the next run to collide with."""
    from app.db.database import init_db
    init_db()
    yield
    from app.db.database import engine

    engine.dispose()
    _TEST_DB.unlink(missing_ok=True)
    # And no photographs. `ignore_errors` because a partially-written file on a
    # Windows filesystem that still holds a handle must not fail the whole run
    # after every assertion has already passed.
    import shutil

    shutil.rmtree(_TEST_EVIDENCE, ignore_errors=True)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    from app.db.database import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

