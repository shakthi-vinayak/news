"""
collectors/news/rss_feeds.py
Generic config-driven RSS/Atom collector using feedparser.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from scoring.dedupe import make_news_id

log = logging.getLogger(__name__)


def _parse_date(entry: Any) -> str:
    """Best-effort ISO8601 date extraction from a feedparser entry."""
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
    cfg keys (from config.yaml news.rss_feeds):
      feeds                 — list of {name, url}
      max_items_per_feed    — cap per feed
    """
    feeds         = cfg.get("feeds", [])
    max_per_feed  = cfg.get("max_items_per_feed", 20)
    collected: list[dict] = []

    for feed_cfg in feeds:
        name = feed_cfg.get("name", "RSS")
        url  = feed_cfg.get("url", "")
        if not url:
            continue
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                log.warning("RSS feed '%s' returned bozo error: %s", name, parsed.bozo_exception)
                continue

            count = 0
            for entry in parsed.entries:
                link  = getattr(entry, "link", "") or ""
                title = (getattr(entry, "title", "") or "").strip()
                if not link or not title:
                    continue

                item_id = make_news_id(link, title, name)
                published = _parse_date(entry)

                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "url":             link,
                    "source":          name,
                    "published_at":    published,
                    "summary":         "",
                    "tags":            [],
                    "relevance_score": 0.0,
                })
                count += 1
                if count >= max_per_feed:
                    break

            log.debug("RSS '%s': %d items", name, count)
        except Exception as exc:
            log.error("RSS feed '%s' (%s) failed: %s", name, url, exc)

    log.info("RSS collector: %d total items from %d feeds", len(collected), len(feeds))
    return collected
