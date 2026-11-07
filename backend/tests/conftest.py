import os
import sys
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)

from app.main import app
from app.services.auth_service import create_access_token

def auth_headers(username="admin", role="admin", shop_id=None) -> dict:
    return {"Authorization": f"Bearer {create_access_token(username, role, shop_id)}"}

@pytest.fixture(scope="session")
def client():
    with TestClient(app, headers=auth_headers()) as test_client:
        yield test_client

@pytest.fixture(scope="session")
def anon_client():
    with TestClient(app) as test_client:
        yield test_client
