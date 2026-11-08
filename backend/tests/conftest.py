import os
import sys
import tempfile
from pathlib import Path

# Ensure backend on path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

_test_db_path = Path(tempfile.gettempdir()) / "speechshield_test.db"
if _test_db_path.exists():
    _test_db_path.unlink()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path.as_posix()}")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-1234567890")

import pytest  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limiters(client):
    try:
        from app.middleware import RATE_LIMIT_HITS

        RATE_LIMIT_HITS.clear()
    except Exception:  # noqa: BLE001
        pass
    try:
        import app.routers.audio as audio_router

        audio_router._upload_hits.clear()
    except Exception:  # noqa: BLE001
        pass
    try:
        import app.routers.auth as auth_router

        auth_router._login_hits_ip.clear()
        auth_router._login_hits_account.clear()
    except Exception:  # noqa: BLE001
        pass
    import contextlib

    with contextlib.suppress(Exception):
        client.cookies.clear()
    yield
