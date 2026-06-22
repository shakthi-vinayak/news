"""
collectors/jobs/weworkremotely_rss.py
Fetch DevOps/Sysadmin jobs from We Work Remotely RSS feed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

DEFAULT_FEED = "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"
SOURCE_NAME  = "WeWorkRemotely"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.weworkremotely):
      feed_url  — RSS URL (default: DevOps category)
    """
    feed_url  = cfg.get("feed_url", DEFAULT_FEED)
    keywords  = cfg.get("keywords", [])
    collected: list[dict] = []

    try:
        parsed = feedparser.parse(feed_url)
        if parsed.bozo and not parsed.entries:
            log.warning("WeWorkRemotely RSS bozo error: %s", parsed.bozo_exception)
            return collected

        for entry in parsed.entries:
            title = (getattr(entry, "title", "") or "").strip()
            link  = getattr(entry, "link", "") or ""
            if not title or not link:
                continue

            # WWR title format: "Company: Job Title at Company"
            company = ""
            if ": " in title:
                parts   = title.split(": ", 1)
                company = parts[0].strip()
                title   = parts[1].strip() if len(parts) > 1 else title

            searchable = f"{title} {company}".lower()
            if keywords and not any(kw.lower() in searchable for kw in keywords):
                continue

            # Parse date
            pub = None
            for attr in ("published", "updated"):
                val = getattr(entry, attr, None)
                if val:
                    try:
                        pub = parsedate_to_datetime(val).isoformat()
                        break
                    except Exception:
                        pass
            pub = pub or datetime.now(timezone.utc).isoformat()

            item_id = make_job_id(link, title, company, SOURCE_NAME)
            collected.append({
                "id":              item_id,
                "title":           title,
                "company":         company,
                "url":             link,
                "source":          SOURCE_NAME,
                "location":        "Remote",
                "posted_at":       pub,
                "category":        "",
                "relevance_score": 0.0,
                "salary_range":    None,
            })

    except Exception as exc:
        log.error("WeWorkRemotely RSS failed: %s", exc)

    log.info("WeWorkRemotely: collected %d jobs", len(collected))
    return collected
