"""
collectors/jobs/lever.py
Fetch jobs from Lever.co public job boards (no auth required).
Config-driven list of company slugs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

LEVER_API   = "https://api.lever.co/v0/postings/{slug}?mode=json"
SOURCE_NAME = "Lever"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.lever):
      boards    — list of Lever company slugs
    """
    boards   = cfg.get("boards", [])
    keywords = cfg.get("keywords", [])
    collected: list[dict] = []

    for slug in boards:
        try:
            url  = LEVER_API.format(slug=slug)
            resp = requests.get(url, timeout=15)
            if resp.status_code == 404:
                log.warning("Lever board '%s' not found (404)", slug)
                continue
            resp.raise_for_status()
            jobs = resp.json()
            if not isinstance(jobs, list):
                continue

            company_name = slug.replace("-", " ").title()

            for job in jobs:
                title   = (job.get("text") or "").strip()
                job_url = job.get("hostedUrl") or job.get("applyUrl") or ""
                if not title or not job_url:
                    continue

                categories = job.get("categories") or {}
                location   = categories.get("location") or categories.get("allLocations") or ""
                team       = categories.get("team") or ""

                searchable = f"{title} {team} {company_name}".lower()
                if keywords and not any(kw.lower() in searchable for kw in keywords):
                    continue

                item_id   = make_job_id(job_url, title, slug, SOURCE_NAME)
                created   = job.get("createdAt")
                posted_at = (
                    datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat()
                    if created else datetime.now(timezone.utc).isoformat()
                )

                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "company":         company_name,
                    "url":             job_url,
                    "source":          SOURCE_NAME,
                    "location":        location if isinstance(location, str) else ", ".join(location),
                    "posted_at":       posted_at,
                    "category":        team,
                    "relevance_score": 0.0,
                    "salary_range":    None,
                })

            log.debug("Lever '%s': %d jobs", slug, len(jobs))
        except Exception as exc:
            log.error("Lever board '%s' failed: %s", slug, exc)

    log.info("Lever: collected %d total jobs", len(collected))
    return collected
