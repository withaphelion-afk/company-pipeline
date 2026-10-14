import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="pipeline-test-"))
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp / 'test.db'}", DATA_DIR=str(_tmp / "data"), QUEUE_MODE="none",
    PROFILE_PATH=str(Path(__file__).parent / "fixtures" / "profile.yaml"), LLM_PROVIDER="template",
    SMTP_PROBE_ENABLED="false", CONTROL_API_TOKEN="", CONTACT_EMAIL="test@example.com",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services import http_client  # noqa: E402
from app.stages import base as stage_base  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def make_transport(routes: dict[str, str | tuple[int, str]]) -> httpx.MockTransport:
    """Map URL (exact) -> body or (status, body). Unknown URLs 404, so robots.txt means allow-all."""
    def handler(req: httpx.Request) -> httpx.Response:
        hit = routes.get(str(req.url))
        if hit is None:
            return httpx.Response(404, text="")
        status, body = hit if isinstance(hit, tuple) else (200, hit)
        return httpx.Response(status, text=body)
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    http_client.clear_robots_cache()
    stage_base.RATE_OVERRIDE = 0
    stage_base.HTTP_TRANSPORT = None
    yield
    stage_base.HTTP_TRANSPORT = None


@pytest.fixture
def session():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    return TestClient(app)
