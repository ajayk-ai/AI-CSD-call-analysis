"""Regression test for middleware ordering.

CORSMiddleware must wrap the error catcher, so that a failing request still
returns Access-Control-Allow-Origin. If that ordering is broken (or the
catcher is replaced with @app.exception_handler(Exception), which Starlette
routes to the outermost ServerErrorMiddleware), the browser reports a
misleading "blocked by CORS policy" and the real error becomes invisible.
That's a genuinely painful thing to debug, hence this test.
"""

import pytest
from fastapi.testclient import TestClient

from app.api import routes_pipeline
from app.main import app

ORIGIN = "http://localhost:5173"


@pytest.fixture
def client_with_failing_pipeline(monkeypatch):
    def boom(db, **kwargs):
        raise RuntimeError("simulated GCS/TLS failure")

    monkeypatch.setattr(routes_pipeline, "run_pipeline", boom)
    # raise_server_exceptions=False so the response is returned rather than
    # re-raised into the test, mirroring what a browser actually receives.
    return TestClient(app, raise_server_exceptions=False)


def test_failing_request_still_returns_cors_header(client_with_failing_pipeline):
    response = client_with_failing_pipeline.post(
        "/api/pipeline/run", headers={"Origin": ORIGIN}
    )

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_failing_request_reports_the_real_error(client_with_failing_pipeline):
    response = client_with_failing_pipeline.post(
        "/api/pipeline/run", headers={"Origin": ORIGIN}
    )

    detail = response.json()["detail"]
    assert "RuntimeError" in detail
    assert "simulated GCS/TLS failure" in detail


def test_successful_request_has_cors_header():
    client = TestClient(app)
    response = client.get("/api/health", headers={"Origin": ORIGIN})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_preflight_is_allowed():
    client = TestClient(app)
    response = client.options(
        "/api/pipeline/run",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ORIGIN
