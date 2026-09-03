from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

TEST_DB = Path("/tmp/mlr_ruleops_pytest.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["LLM_PROVIDER"] = "deterministic"
os.environ["JWT_SECRET"] = "pytest-jwt-secret"
os.environ["SECRET_KEY"] = "pytest-secret"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"

from app.core.config import get_settings

get_settings.cache_clear()

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.seed import seed_all
from app import models  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if TEST_DB.exists():
        TEST_DB.unlink()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db, reviews=80)
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "mlr.admin@mlr-ruleops.local", "password": "ChangeMe!Mlr1"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@mlr-ruleops.local", "password": "ChangeMe!Admin1"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
