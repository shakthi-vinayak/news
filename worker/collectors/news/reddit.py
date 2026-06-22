"""
collectors/news/reddit.py
Fetch hot/top posts from subreddits using the public JSON API (no auth).
Respects a configurable delay between requests to avoid rate-limiting.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_news_id

log = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com/r/{sub}/hot.json"
HEADERS     = {"User-Agent": "devops-news-bot/1.0 (https://github.com/devops-news-jobs-app)"}


def _ts_to_iso(ts: float | None) -> str:
    if not ts:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml news.reddit):
      subreddits            — list of subreddit names (without r/)
      max_items_per_sub     — cap per subreddit
      delay_seconds         — sleep between requests
    """
    subreddits    = cfg.get("subreddits", ["devops"])
    max_per_sub   = cfg.get("max_items_per_sub", 25)
    delay         = float(cfg.get("delay_seconds", 2.0))
    collected: list[dict] = []

    for i, sub in enumerate(subreddits):
        if i > 0:
            time.sleep(delay)
        try:
            url    = REDDIT_BASE.format(sub=sub)
            params = {"limit": max_per_sub}
            resp   = requests.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            posts  = resp.json().get("data", {}).get("children", [])

            for post in posts:
                d     = post.get("data", {})
                title = (d.get("title") or "").strip()
                link  = d.get("url") or f"https://reddit.com{d.get('permalink', '')}"
                if not title or d.get("is_self") and not d.get("selftext"):
                    continue

                source_name = f"Reddit r/{sub}"
                item_id     = make_news_id(link, title, source_name)
                published   = _ts_to_iso(d.get("created_utc"))

                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "url":             link,
                    "source":          source_name,
                    "published_at":    published,
                    "summary":         (d.get("selftext") or "")[:300],
                    "tags":            [],
                    "relevance_score": 0.0,
                })

            log.debug("Reddit r/%s: %d items", sub, len(posts))
        except Exception as exc:
            log.error("Reddit r/%s failed: %s", sub, exc)

    log.info("Reddit: collected %d total items", len(collected))
    return collected
