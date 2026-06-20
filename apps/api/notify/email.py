"""Transactional email for long-running cloud-job completion.

Uses Resend's HTTP API directly (no SDK — plain httpx, already a dependency).
Dark by default: when ``settings.resend_api_key`` is blank this is a logged
no-op, so it's safe to wire everywhere before the key exists. Never raises —
a mail failure must never affect a compute job.

Swap providers (SMTP/SES) by replacing the single POST in ``_send`` — the
public ``send_job_complete_email`` signature stays stable.
"""
from __future__ import annotations

import logging

import httpx

from apps.api.config import settings

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"

# Friendly labels per job kind.
_KIND_LABEL = {
    "grain_grow": "Grain-growth simulation",
    "grain_tessellate": "Grain-structure generation",
}


def _summary(kind: str, result: dict | None) -> str:
    if not result:
        return ""
    bits: list[str] = []
    if result.get("grain_count") is not None:
        bits.append(f"{result['grain_count']} grains")
    if result.get("mean_grain_size_um") is not None:
        bits.append(f"mean ⌀ {result['mean_grain_size_um']} µm")
    elif result.get("mean_grain_size_voxels") is not None:
        bits.append(f"mean ⌀ {result['mean_grain_size_voxels']} vox")
    if result.get("n_sweeps") is not None:
        bits.append(f"{result['n_sweeps']} MC sweeps")
    return " · ".join(bits)


def _render(kind: str, status: str, result: dict | None, job_id: str) -> tuple[str, str]:
    label = _KIND_LABEL.get(kind, kind)
    link = f"{settings.public_app_url.rstrip('/')}/canvas"
    if status == "done":
        subject = f"✓ Your {label.lower()} is ready"
        summ = _summary(kind, result)
        summ_html = f"<p style='color:#444'>{summ}</p>" if summ else ""
        body = (
            f"<h2 style='font-weight:500'>{label} complete</h2>"
            f"{summ_html}"
            f"<p><a href='{link}'>Open it in LeilMat →</a></p>"
            f"<p style='color:#999;font-size:12px'>Job {job_id}. "
            f"Results are qualitative (Monte-Carlo Potts) — see the in-app caveats.</p>"
        )
    else:
        subject = f"✗ Your {label.lower()} did not finish ({status})"
        body = (
            f"<h2 style='font-weight:500'>{label} {status}</h2>"
            f"<p>The job ended without a result. You can retry from the canvas.</p>"
            f"<p><a href='{link}'>Open LeilMat →</a></p>"
            f"<p style='color:#999;font-size:12px'>Job {job_id}.</p>"
        )
    return subject, body


async def send_job_complete_email(
    to: str | None, *, kind: str, status: str, result: dict | None, job_id: str
) -> None:
    """Email the user that their job finished. No-op (logged) when unconfigured."""
    if not to:
        logger.info("[notify] no recipient for job %s — email skipped", job_id)
        return
    if not settings.resend_api_key:
        logger.info("[notify] RESEND_API_KEY unset — email to %s for job %s is a no-op",
                    to, job_id)
        return
    subject, html = _render(kind, status, result, job_id)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                _RESEND_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={"from": settings.email_from, "to": [to],
                      "subject": subject, "html": html},
            )
        if r.status_code >= 300:
            logger.warning("[notify] Resend %s for job %s: %s",
                           r.status_code, job_id, r.text[:200])
        else:
            logger.info("[notify] completion email sent for job %s", job_id)
    except Exception as exc:  # never let mail failure touch the job
        logger.warning("[notify] email send failed for job %s: %s", job_id, exc)
