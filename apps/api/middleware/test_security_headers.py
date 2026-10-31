"""Security headers: present on every kind of response, never overriding the app's own, and the real app wears them."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from apps.api.middleware.security_headers import SECURITY_HEADERS, SecurityHeadersMiddleware


def _app() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail="handled error")

    @app.get("/own")
    def own():
        return JSONResponse({"ok": True}, headers={"X-Frame-Options": "SAMEORIGIN"})

    @app.get("/stream")
    def stream():
        return StreamingResponse(iter([b"data: 1\n\n", b"data: 2\n\n"]), media_type="text/event-stream")

    return TestClient(app, raise_server_exceptions=False)


def _has_all(resp) -> bool:
    return all(resp.headers.get(name) for name, _ in SECURITY_HEADERS)


def test_present_on_success_not_found_and_handled_errors():
    # (An UNHANDLED exception's 500 is built by Starlette outside the middleware stack and cannot carry them: see the module doc.)
    c = _app()
    assert _has_all(c.get("/ok"))
    assert _has_all(c.get("/missing"))          # 404
    assert _has_all(c.get("/teapot"))           # an HTTPException the app raised on purpose


def test_streaming_responses_are_untouched_apart_from_the_headers():
    r = _app().get("/stream")
    assert r.text == "data: 1\n\ndata: 2\n\n"
    assert _has_all(r)


def test_an_application_set_header_is_not_overridden():
    r = _app().get("/own")
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_the_real_app_sends_them_on_health_and_on_a_cors_preflight():
    from apps.api.main import app
    c = TestClient(app)
    assert _has_all(c.get("/health"))
    pre = c.options("/api/predict", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert _has_all(pre)
