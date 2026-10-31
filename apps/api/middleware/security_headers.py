"""
Baseline security headers on every API response.

The web app's pages get a full Content-Security-Policy from Next (apps/web/lib/securityHeaders.ts).  API responses never
pass through Next, so they carry the headers that make sense for JSON and event streams:

  X-Content-Type-Options: nosniff        a JSON body is never sniffed into HTML/script
  X-Frame-Options: DENY                  nothing here is meant to be framed
  Referrer-Policy: no-referrer           API URLs can carry ids; do not leak them onward
  Strict-Transport-Security              only meaningful over HTTPS; browsers ignore it on plain http

No Content-Security-Policy on purpose: FastAPI's own /docs page loads its UI from a CDN and a blanket policy would break it.

A header the application already set is left alone.  One limit: Starlette builds the plain-text 500 for an UNHANDLED exception
outside the user middleware stack, so that single kind of response does not carry these headers (handled errors, 4xx and
HTTPException responses do).  Pure ASGI (not BaseHTTPMiddleware) so streaming responses — the
chat endpoints stream server-sent events — are passed through untouched.
"""
from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS:
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
