"""
collectors/jobs/hn_whoishiring.py
Parse the monthly HN "Who is Hiring" thread via Algolia API.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEMS  = "https://hn.algolia.com/api/v1/items/{id}"
SOURCE_NAME    = "HN Who's Hiring"


def _find_latest_whoishiring_id() -> str | None:
    """Search Algolia for the latest 'Ask HN: Who is Hiring?' post."""
    params = {
        "query":        "Ask HN: Who is Hiring?",
        "tags":         "story,ask_hn",
        "hitsPerPage":  5,
    }
    resp = requests.get(ALGOLIA_SEARCH, params=params, timeout=15)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    for hit in hits:
        if "ask hn: who is hiring" in (hit.get("title") or "").lower():
            return hit.get("objectID")
    return None


def _extract_job_from_comment(text: str) -> dict | None:
    """Very best-effort extraction of company/title/location from a free-text comment."""
    lines = text.strip().splitlines()
    if not lines:
        return None
    first_line = lines[0]

    # Try "Company | Title | Location | ..." pattern
    parts = re.split(r"\s*\|\s*", first_line)
    company = parts[0].strip() if parts else ""
    title   = parts[1].strip() if len(parts) > 1 else "Software Engineer"
    loc     = parts[2].strip() if len(parts) > 2 else "Remote"

    return company, title, loc


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.hn_whoishiring):
      keywords  — list of terms to filter comments by
    """
    keywords  = cfg.get("keywords", ["devops"])
    collected: list[dict] = []

    try:
        thread_id = _find_latest_whoishiring_id()
        if not thread_id:
            log.warning("Could not find 'Who is Hiring' thread on HN")
            return collected

        url   = ALGOLIA_ITEMS.format(id=thread_id)
        resp  = requests.get(url, timeout=30)
        resp.raise_for_status()
        data  = resp.json()
        kids  = data.get("children", [])

        for comment in kids:
            text = comment.get("text") or ""
            if not text:
                continue

            searchable = text.lower()
            if not any(kw.lower() in searchable for kw in keywords):
                continue

            result = _extract_job_from_comment(text)
            if not result:
                continue
            company, title, loc = result

            hn_id   = comment.get("id") or ""
            comment_url = f"https://news.ycombinator.com/item?id={hn_id}"
            item_id = make_job_id(comment_url, title, company, SOURCE_NAME)
            created = comment.get("created_at") or datetime.now(timezone.utc).isoformat()

            collected.append({
                "id":              item_id,
                "title":           title,
                "company":         company,
                "url":             comment_url,
                "source":          SOURCE_NAME,
                "location":        loc,
                "posted_at":       created,
                "category":        "",
                "relevance_score": 0.0,
                "salary_range":    None,
            })

    except Exception as exc:
        log.error("HN Who's Hiring failed: %s", exc)

    log.info("HN Who's Hiring: collected %d jobs", len(collected))
    return collected
