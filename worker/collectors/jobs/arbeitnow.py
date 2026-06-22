"""
collectors/jobs/arbeitnow.py
Fetch jobs from Arbeitnow public API (free, no auth).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
SOURCE_NAME   = "Arbeitnow"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.arbeitnow):
      tags      — list of tag filters
    """
    keywords  = cfg.get("tags", ["devops"])
    collected: list[dict] = []

    try:
        resp = requests.get(ARBEITNOW_API, timeout=15)
        resp.raise_for_status()
        jobs = resp.json().get("data", [])

        for job in jobs:
            title   = (job.get("title") or "").strip()
            company = (job.get("company_name") or "").strip()
            url     = job.get("url") or ""
            if not title or not url:
                continue

            searchable = " ".join([title, company, " ".join(job.get("tags") or [])]).lower()
            if keywords and not any(kw.lower() in searchable for kw in keywords):
                continue

            item_id   = make_job_id(url, title, company, SOURCE_NAME)
            posted_at = job.get("created_at")
            if posted_at:
                try:
                    posted_at = datetime.fromtimestamp(int(posted_at), tz=timezone.utc).isoformat()
                except Exception:
                    posted_at = datetime.now(timezone.utc).isoformat()
            else:
                posted_at = datetime.now(timezone.utc).isoformat()

            location = "Remote" if job.get("remote") else (job.get("location") or "")
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
                "salary_range":    None,
            })

    except Exception as exc:
        log.error("Arbeitnow failed: %s", exc)

    log.info("Arbeitnow: collected %d jobs", len(collected))
    return collected
