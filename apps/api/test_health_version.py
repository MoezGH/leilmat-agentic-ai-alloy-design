"""/health stays a cheap liveness probe and also says which release is running."""
from fastapi.testclient import TestClient

from apps.api.main import APP_VERSION, app


def test_health_reports_status_and_version():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": APP_VERSION}
