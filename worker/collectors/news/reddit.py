"""
collectors/news/reddit.py
Fetch hot posts from subreddits using Reddit's RSS feeds (no auth required).
Reddit's JSON API now blocks unauthenticated requests with 403.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from scoring.dedupe import make_news_id

log = logging.getLogger(__name__)

REDDIT_RSS = "https://www.reddit.com/r/{sub}/.rss"


def _parse_date(entry: Any) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml news.reddit):
      subreddits            -- list of subreddit names (without r/)
      max_items_per_sub     -- cap per subreddit
    """
    subreddits  = cfg.get("subreddits", ["devops"])
    max_per_sub = cfg.get("max_items_per_sub", 25)
    collected: list[dict] = []

    for sub in subreddits:
        try:
            url = REDDIT_RSS.format(sub=sub)
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                log.warning("Reddit r/%s RSS error: %s", sub, parsed.bozo_exception)
                continue

            count = 0
            for entry in parsed.entries:
                title = (getattr(entry, "title", "") or "").strip()
                link  = getattr(entry, "link", "") or ""
                if not title or not link:
                    continue

                source_name = f"Reddit r/{sub}"
                item_id     = make_news_id(link, title, source_name)
                published   = _parse_date(entry)

                # Extract a short summary from content if available
                summary = ""
                content = getattr(entry, "summary", "") or ""
                if content:
                    summary = re.sub(r"<[^>]+>", "", content)[:300]

                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "url":             link,
                    "source":          source_name,
                    "published_at":    published,
                    "summary":         summary,
                    "tags":            [],
                    "relevance_score": 0.0,
                })
                count += 1
                if count >= max_per_sub:
                    break

            log.debug("Reddit r/%s RSS: %d items", sub, count)
        except Exception as exc:
            log.error("Reddit r/%s RSS failed: %s", sub, exc)

    log.info("Reddit: collected %d total items", len(collected))
    return collected