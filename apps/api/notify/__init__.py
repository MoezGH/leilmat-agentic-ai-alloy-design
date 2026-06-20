"""Outbound user notifications (transactional email).

Dark by default — `send_job_complete_email` is a no-op (logged) until
RESEND_API_KEY is configured, mirroring the Daytona + LeilAI-5 gates.
"""
