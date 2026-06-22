"""
collectors/jobs/greenhouse.py
Fetch jobs from Greenhouse.io public job boards (no auth required).
Config-driven list of company board slugs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

GH_JOBS_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
SOURCE_NAME  = "Greenhouse"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.greenhouse):
      boards    — list of company board slugs
    """
    boards   = cfg.get("boards", [])
    keywords = cfg.get("keywords", [])
    collected: list[dict] = []

    for slug in boards:
        try:
            url  = GH_JOBS_API.format(slug=slug)
            resp = requests.get(url, timeout=15)
            if resp.status_code == 404:
                log.warning("Greenhouse board '%s' not found (404)", slug)
                continue
            resp.raise_for_status()
            jobs = resp.json().get("jobs", [])

            for job in jobs:
                title   = (job.get("title") or "").strip()
                job_url = job.get("absolute_url") or ""
                if not title or not job_url:
                    continue

                # Location may be nested
                loc_obj  = job.get("location") or {}
                location = loc_obj.get("name") or ""

                searchable = f"{title} {slug}".lower()
                if keywords and not any(kw.lower() in searchable for kw in keywords):
                    continue

                item_id   = make_job_id(job_url, title, slug, SOURCE_NAME)
                posted_at = job.get("updated_at") or datetime.now(timezone.utc).isoformat()

                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "company":         slug.replace("-", " ").title(),
                    "url":             job_url,
                    "source":          SOURCE_NAME,
                    "location":        location,
                    "posted_at":       posted_at,
                    "category":        "",
                    "relevance_score": 0.0,
                    "salary_range":    None,
                })

            log.debug("Greenhouse '%s': %d jobs", slug, len(jobs))
        except Exception as exc:
            log.error("Greenhouse board '%s' failed: %s", slug, exc)

    log.info("Greenhouse: collected %d total jobs", len(collected))
    return collected
