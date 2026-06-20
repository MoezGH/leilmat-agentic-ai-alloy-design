"""Outbound user notifications (transactional email).

Dark by default — `send_job_complete_email` is a no-op (logged) until
MAILTRAP_API_TOKEN is configured. Uses Mailtrap, the same provider LeilAI-5
sends from, so one token covers the whole Leil stack.
"""
