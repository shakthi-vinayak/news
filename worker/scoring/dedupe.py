"""
worker/scoring/dedupe.py
Hash-based and fuzzy-title deduplication.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from typing import Any

from rapidfuzz import fuzz

log = logging.getLogger(__name__)

FUZZY_THRESHOLD = 88  # Levenshtein ratio 0-100; tweak if too aggressive


# ── ID generation ────────────────────────────────────────────────────────────
def make_news_id(url: str, title: str, source: str) -> str:
    """Stable deterministic ID for a news item."""
    key = f"{source}|{url}|{title}".lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def make_job_id(url: str, title: str, company: str, source: str) -> str:
    """Stable deterministic ID for a job item."""
    key = f"{source}|{company}|{title}|{url}".lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()[:32]


# ── DB-backed seen-check ─────────────────────────────────────────────────────
def is_news_seen(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute(
        "SELECT id FROM news WHERE id = ?", (item_id,)
    ).fetchone()
    return row is not None


def is_job_seen(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute(
        "SELECT id FROM jobs WHERE id = ?", (item_id,)
    ).fetchone()
    return row is not None


# ── Fuzzy title dedup (in-batch) ─────────────────────────────────────────────
def dedup_batch(items: list[dict[str, Any]], *, title_key: str = "title") -> list[dict]:
    """
    Remove near-duplicates within a single batch using fuzzy title matching.
    Keeps the first occurrence when duplicates are found.
    """
    seen_titles: list[str] = []
    unique: list[dict] = []

    for item in items:
        title = (item.get(title_key) or "").strip()
        if not title:
            unique.append(item)
            continue

        duplicate = False
        for seen in seen_titles:
            if fuzz.token_sort_ratio(title, seen) >= FUZZY_THRESHOLD:
                log.debug("Fuzzy-dedup: '%s' ≈ '%s'", title[:60], seen[:60])
                duplicate = True
                break

        if not duplicate:
            seen_titles.append(title)
            unique.append(item)

    removed = len(items) - len(unique)
    if removed:
        log.info("Fuzzy dedup removed %d near-duplicate(s) from batch", removed)
    return unique


# ── Keyword pre-filter ────────────────────────────────────────────────────────
def passes_keyword_filter(item: dict, keywords: list[str]) -> bool:
    """Return True if item title/summary contains at least one keyword."""
    if not keywords:
        return True
    text = " ".join(filter(None, [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("company", ""),
    ])).lower()
    return any(kw.lower() in text for kw in keywords)
