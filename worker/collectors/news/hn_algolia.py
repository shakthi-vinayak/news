"""
collectors/news/hn_algolia.py
Fetch DevOps/AI/SRE articles from Hacker News via the Algolia Search API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from scoring.dedupe import make_news_id

log = logging.getLogger(__name__)

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
SOURCE_NAME = "Hacker News"


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml news.hacker_news):
      tags         — list of search terms
      min_points   — minimum score/points
      max_items    — max items to return (across all tags)
    """
    tags      = cfg.get("tags", ["devops"])
    min_pts   = cfg.get("min_points", 5)
    max_items = cfg.get("max_items", 50)

    collected: list[dict] = []
    seen_ids: set[str] = set()

    for tag in tags:
        try:
            params = {
                "query":        tag,
                "tags":         "story",
                "hitsPerPage":  max(20, max_items // max(len(tags), 1)),
            }
            resp = requests.get(ALGOLIA_SEARCH, params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            for hit in hits:
                if int(hit.get("points", 0)) < min_pts:
                    continue
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                title = (hit.get("title") or "").strip()
                if not title or not url:
                    continue

                item_id = make_news_id(url, title, SOURCE_NAME)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                published = hit.get("created_at") or datetime.now(timezone.utc).isoformat()
                collected.append({
                    "id":              item_id,
                    "title":           title,
                    "url":             url,
                    "source":          SOURCE_NAME,
                    "published_at":    published,
                    "summary":         "",
                    "tags":            [],
                    "relevance_score": 0.0,
                })

                if len(collected) >= max_items:
                    break

        except Exception as exc:
            log.error("HN Algolia tag '%s' failed: %s", tag, exc)

        if len(collected) >= max_items:
            break

    log.info("HN Algolia: collected %d items", len(collected))
    return collected
