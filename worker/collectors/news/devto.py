"""
collectors/news/devto.py
Fetch articles from Dev.to public API filtered by tags.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_news_id

log = logging.getLogger(__name__)

DEVTO_API   = "https://dev.to/api/articles"
SOURCE_NAME = "Dev.to"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml news.devto):
      tags        — list of Dev.to tag slugs
      max_items   — max total items
    """
    tags      = cfg.get("tags", ["devops"])
    max_items = cfg.get("max_items", 30)
    per_page  = min(30, max_items)
    collected: list[dict] = []
    seen_ids: set[str] = set()

    for tag in tags:
        if len(collected) >= max_items:
            break
        try:
            params = {"tag": tag, "per_page": per_page, "top": 7}
            resp = requests.get(DEVTO_API, params=params, timeout=15)
            resp.raise_for_status()
            articles = resp.json()

            for art in articles:
                url   = art.get("url", "")
                title = (art.get("title") or "").strip()
                if not url or not title:
                    continue

                item_id = make_news_id(url, title, SOURCE_NAME)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                published = art.get("published_at") or datetime.now(timezone.utc).isoformat()
                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "url":             url,
                    "source":          SOURCE_NAME,
                    "published_at":    published,
                    "summary":         (art.get("description") or "")[:400],
                    "tags":            art.get("tag_list") or [],
                    "relevance_score": 0.0,
                })
                if len(collected) >= max_items:
                    break

        except Exception as exc:
            log.error("Dev.to tag '%s' failed: %s", tag, exc)

    log.info("Dev.to: collected %d items", len(collected))
    return collected
