import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEST_DB = "crimemind_test"
os.environ["CM_DATABASE_URL"] = f"postgresql://cm_app:cm_app_dev@localhost:5432/{TEST_DB}"
os.environ["CM_JWT_SECRET"] = "test-secret-not-for-production-use-0123456789"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)
os.environ["CM_AI_PROVIDER"] = "offline"  # tests never call a real model, even if a local .env holds keys
sys.path.insert(0, str(ROOT / "backend"))

C1, C2 = "CASE-2026-001", "CASE-2026-002"
PW = "crimemind-demo"


def reseed():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "init_db.py"), "--db", TEST_DB, "--reset"], check=True, capture_output=True, cwd=ROOT / "backend")
    subprocess.run([sys.executable, "-m", "synth.seed", "--db", TEST_DB], check=True, capture_output=True, cwd=ROOT / "backend")


@pytest.fixture(scope="module")
def world():
    """A freshly seeded database per test module (tests may change evidence validity)."""
    reseed()
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        yield client


class Api:
    def __init__(self, client):
        self.c = client
        self._tok = {}

    def login(self, user):
        if user not in self._tok:
            r = self.c.post("/api/auth/login", json={"username": user, "password": PW})
            assert r.status_code == 200, r.text
            self._tok[user] = {"Authorization": "Bearer " + r.json()["access_token"]}
        return self._tok[user]

    def get(self, path, user="inv.asha", **kw):
        return self.c.get(path, headers=self.login(user), **kw)

    def post(self, path, user="inv.asha", json=None):
        return self.c.post(path, headers=self.login(user), json=json or {})


@pytest.fixture(scope="module")
def api(world):
    return Api(world)


def admin_conn():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(f"postgresql://postgres:postgres@localhost:5432/{TEST_DB}", row_factory=dict_row)
