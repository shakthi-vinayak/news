"""
collectors/news/github_releases.py
Collect release notes from GitHub repos via the public Atom feed.
No auth required for public repos; respects a small delay.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import feedparser

from scoring.dedupe import make_news_id

log = logging.getLogger(__name__)

GH_RELEASES_ATOM = "https://github.com/{repo}/releases.atom"
DELAY_SECONDS    = 1.0   # polite delay between GitHub requests


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml news.github_releases):
      repos               — list of "owner/repo" strings
      max_items_per_repo  — cap per repo
    """
    repos          = cfg.get("repos", [])
    max_per_repo   = cfg.get("max_items_per_repo", 5)
    collected: list[dict] = []

    for i, repo in enumerate(repos):
        if i > 0:
            time.sleep(DELAY_SECONDS)
        try:
            url    = GH_RELEASES_ATOM.format(repo=repo)
            parsed = feedparser.parse(url)

            if parsed.bozo and not parsed.entries:
                log.warning("GitHub releases '%s': bozo error %s", repo, parsed.bozo_exception)
                continue

            source_name = f"GitHub Releases ({repo.split('/')[0]})"
            count = 0

            for entry in parsed.entries:
                link  = getattr(entry, "link", "") or ""
                title = (getattr(entry, "title", "") or "").strip()
                if not link or not title:
                    continue

                # Use updated or published
                pub = None
                for attr in ("updated_parsed", "published_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        try:
                            pub = datetime(*val[:6], tzinfo=timezone.utc).isoformat()
                            break
                        except Exception:
                            pass
                pub = pub or datetime.now(timezone.utc).isoformat()

                item_id = make_news_id(link, title, source_name)
                collected.append({
                    "id":              item_id,
                    "title":           f"{repo}: {title}",
                    "url":             link,
                    "source":          source_name,
                    "published_at":    pub,
                    "summary":         "",
                    "tags":            [],
                    "relevance_score": 0.0,
                })
                count += 1
                if count >= max_per_repo:
                    break

            log.debug("GitHub releases '%s': %d items", repo, count)
        except Exception as exc:
            log.error("GitHub releases '%s' failed: %s", repo, exc)

    log.info("GitHub Releases: collected %d total items", len(collected))
    return collected
