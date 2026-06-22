"""
worker/notify/smtp_alert.py
Optional SMTP email digest of new high-relevance items.
All credentials come from environment variables (never hardcoded).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

MIN_SCORE_THRESHOLD = 0.6   # only include items above this relevance score


def _build_html(news: list[dict], jobs: list[dict]) -> str:
    """Build a simple HTML digest."""

    def news_row(item: dict) -> str:
        tags = ", ".join(item.get("tags") or [])
        return (
            f'<tr><td><a href="{item["url"]}">{item["title"]}</a></td>'
            f'<td>{item.get("source","")}</td>'
            f'<td>{tags}</td>'
            f'<td>{item.get("relevance_score", 0):.0%}</td></tr>'
        )

    def job_row(item: dict) -> str:
        return (
            f'<tr><td><a href="{item["url"]}">{item["title"]}</a></td>'
            f'<td>{item.get("company","")}</td>'
            f'<td>{item.get("location","")}</td>'
            f'<td>{item.get("category","")}</td>'
            f'<td>{item.get("relevance_score", 0):.0%}</td></tr>'
        )

    news_rows = "".join(news_row(i) for i in news[:20])
    jobs_rows = "".join(job_row(i) for i in jobs[:20])

    return f"""
<html><body style="font-family:sans-serif;color:#1a1d23">
<h2>DevOps &amp; AI Hub Digest</h2>
<h3>📰 News ({len(news)} new items)</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
  <thead style="background:#f0f2f5">
    <tr><th>Title</th><th>Source</th><th>Tags</th><th>Score</th></tr>
  </thead>
  <tbody>{news_rows}</tbody>
</table>
<h3>💼 Jobs ({len(jobs)} new items)</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
  <thead style="background:#f0f2f5">
    <tr><th>Title</th><th>Company</th><th>Location</th><th>Category</th><th>Score</th></tr>
  </thead>
  <tbody>{jobs_rows}</tbody>
</table>
</body></html>
"""


def send_digest(news: list[dict], jobs: list[dict]) -> None:
    """
    Send an HTML email digest.
    Silently skips if SMTP_ENABLED != true or credentials are missing.
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_to   = os.getenv("SMTP_TO", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, smtp_to]):
        log.warning("SMTP not fully configured — skipping digest")
        return

    # Filter to high-relevance only
    hi_news = [i for i in news if (i.get("relevance_score") or 0) >= MIN_SCORE_THRESHOLD]
    hi_jobs = [i for i in jobs if (i.get("relevance_score") or 0) >= MIN_SCORE_THRESHOLD]

    if not hi_news and not hi_jobs:
        log.info("No high-relevance items; skipping SMTP digest")
        return

    html  = _build_html(hi_news, hi_jobs)
    msg   = MIMEMultipart("alternative")
    msg["Subject"] = f"DevOps & AI Hub Digest — {len(hi_news)} news, {len(hi_jobs)} jobs"
    msg["From"]    = smtp_from
    msg["To"]      = smtp_to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [smtp_to], msg.as_string())
        log.info("SMTP digest sent to %s (%d news, %d jobs)", smtp_to, len(hi_news), len(hi_jobs))
    except Exception as exc:
        log.error("SMTP send failed: %s", exc)
        raise
