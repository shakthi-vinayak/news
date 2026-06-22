"""
collectors/jobs/remotive.py
Fetch remote jobs from the Remotive public API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
SOURCE_NAME  = "Remotive"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.remotive):
      categories  — list of Remotive category slugs
    """
    categories = cfg.get("categories", ["devops"])
    keywords   = cfg.get("keywords", [])
    collected: list[dict] = []
    seen_ids: set[str] = set()

    for cat in categories:
        try:
            params = {"category": cat, "limit": 50}
            resp   = requests.get(REMOTIVE_API, params=params, timeout=15)
            resp.raise_for_status()
            jobs   = resp.json().get("jobs", [])

            for job in jobs:
                title   = (job.get("title") or "").strip()
                company = (job.get("company_name") or "").strip()
                url     = job.get("url") or ""
                if not title or not url:
                    continue

                # Keyword gate
                searchable = f"{title} {company}".lower()
                if keywords and not any(kw.lower() in searchable for kw in keywords):
                    continue

                item_id = make_job_id(url, title, company, SOURCE_NAME)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                published = job.get("publication_date") or datetime.now(timezone.utc).isoformat()
                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "company":         company,
                    "url":             url,
                    "source":          SOURCE_NAME,
                    "location":        job.get("candidate_required_location") or "Remote",
                    "posted_at":       published,
                    "category":        job.get("job_type") or "",
                    "relevance_score": 0.0,
                    "salary_range":    job.get("salary") or None,
                })

        except Exception as exc:
            log.error("Remotive category '%s' failed: %s", cat, exc)

    log.info("Remotive: collected %d jobs", len(collected))
    return collected
