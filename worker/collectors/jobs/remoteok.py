"""
collectors/jobs/remoteok.py
Fetch DevOps/SRE/Kubernetes jobs from the RemoteOK public API.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"
SOURCE_NAME  = "RemoteOK"
HEADERS      = {"User-Agent": "devops-news-bot/1.0"}


def _ts_to_iso(ts: Any) -> str:
    if not ts:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.remoteok):
      tags     — list of tag filters to check
    """
    keywords  = cfg.get("tags", ["devops"])
    collected: list[dict] = []

    try:
        time.sleep(1)  # RemoteOK asks for 1s delay
        resp = requests.get(REMOTEOK_API, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # First element is a legal notice dict
        jobs = [j for j in data if isinstance(j, dict) and j.get("id")]

        for job in jobs:
            title   = (job.get("position") or "").strip()
            company = (job.get("company") or "").strip()
            url     = job.get("url") or job.get("apply_url") or ""
            if not title or not url:
                continue

            # Keyword relevance gate
            searchable = " ".join([title, company, " ".join(job.get("tags") or [])]).lower()
            if keywords and not any(kw.lower() in searchable for kw in keywords):
                continue

            item_id    = make_job_id(url, title, company, SOURCE_NAME)
            posted_at  = _ts_to_iso(job.get("date"))
            location   = job.get("location") or "Remote"
            salary     = job.get("salary") or None

            collected.append({
                "id":              item_id,
                "title":           title,
                "company":         company,
                "url":             url,
                "source":          SOURCE_NAME,
                "location":        location,
                "posted_at":       posted_at,
                "category":        "",
                "relevance_score": 0.0,
                "salary_range":    salary,
            })

    except Exception as exc:
        log.error("RemoteOK failed: %s", exc)

    log.info("RemoteOK: collected %d jobs", len(collected))
    return collected
