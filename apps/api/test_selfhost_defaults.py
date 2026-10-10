"""
A fresh, self-hosted install must not carry the hosted service's identity.

Before the open-source release, three things were baked in as defaults:

* CORS allowlisted the hosted product's origins WITH credentials, so every
  self-hosted API trusted someone else's websites;
* the PDF report footer printed the hosting domain on every report;
* notification email defaulted to the hosted sender address.

These tests pin neutral defaults.  The hosted deployment supplies its own values
through environment variables (CORS_ORIGINS, PUBLIC_APP_URL, MAILTRAP_SENDER_EMAIL).
"""
from __future__ import annotations

import io

import pytest

from apps.api.config import Settings, cors_origin_list

HOSTED = ("leil.xyz", "leil.app")


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("CORS_ORIGINS", "PUBLIC_APP_URL", "MAILTRAP_SENDER_EMAIL"):
        monkeypatch.delenv(k, raising=False)


def _fresh_settings() -> Settings:
    return Settings(_env_file=None)       # ignore the developer's own .env


# ── defaults ────────────────────────────────────────────────────────────────

def test_default_cors_trusts_only_localhost(clean_env):
    origins = cors_origin_list(_fresh_settings().cors_origins)
    assert origins, "local development needs at least one allowed origin"
    for o in origins:
        assert o.startswith("http://localhost"), f"unexpected default origin {o}"
        assert not any(h in o for h in HOSTED)


def test_default_public_url_and_sender_are_not_hosted(clean_env):
    s = _fresh_settings()
    assert not any(h in s.public_app_url for h in HOSTED)
    assert not any(h in s.mailtrap_sender_email for h in HOSTED)


def test_environment_overrides_defaults(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.org, https://x.example.org/")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://app.example.org")
    s = _fresh_settings()
    assert cors_origin_list(s.cors_origins) == ["https://app.example.org",
                                                "https://x.example.org"]
    assert s.public_app_url == "https://app.example.org"


# ── parsing ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("", []),
    ("   ", []),
    ("http://a.test", ["http://a.test"]),
    (" http://a.test ,http://b.test, ", ["http://a.test", "http://b.test"]),
    ("http://a.test/", ["http://a.test"]),            # trailing slash never matches an Origin
])
def test_cors_origin_list_parsing(raw, expected):
    assert cors_origin_list(raw) == expected


def test_wildcard_origin_is_rejected():
    """'*' + allow_credentials=True is invalid in browsers and a misconfiguration trap."""
    assert cors_origin_list("*") == []
    assert cors_origin_list("https://a.test,*") == ["https://a.test"]


# ── PDF footer attribution ──────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["", "http://localhost:4000", "https://mat.example.org"])
def test_report_footer_credits_project_home_not_deployment_host(monkeypatch, url):
    """Reports say where the software comes from, whatever host runs it."""
    from apps.api.config import settings
    from apps.api.ml.report import pdf
    monkeypatch.setattr(settings, "public_app_url", url)
    assert pdf._report_domain() == "leil.xyz"


@pytest.mark.parametrize("url", ["http://localhost:4000", "https://mat.example.org"])
def test_footer_renders(monkeypatch, url):
    from reportlab.pdfgen import canvas as rl_canvas
    from apps.api.config import settings
    from apps.api.ml.report import pdf
    monkeypatch.setattr(settings, "public_app_url", url)
    c = rl_canvas.Canvas(io.BytesIO())
    pdf._header_footer(c, doc=type("Doc", (), {"page": 1})())   # must not raise
    c.save()


# ── email sender guard ──────────────────────────────────────────────────────

def test_email_is_a_noop_without_a_sender_address(monkeypatch):
    import asyncio
    from apps.api.config import settings
    from apps.api.notify import email as mod

    monkeypatch.setattr(settings, "mailtrap_api_token", "token-present")
    monkeypatch.setattr(settings, "mailtrap_sender_email", "")
    monkeypatch.setattr(mod, "_send", lambda *a, **k: pytest.fail("must not attempt to send"))

    asyncio.run(mod.send_job_complete_email(
        "user@example.org", kind="cpfem_stress_strain", status="DONE",
        result={}, job_id="j-1"))
