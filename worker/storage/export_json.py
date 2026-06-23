"""
worker/storage/export_json.py
Reads from SQLite AND existing JSON files, merges, and writes
docs/data/news.json, jobs.json, meta.json.

Key behaviour:
- New items from the current run are merged with existing items from
  the previously committed JSON files.
- For duplicate IDs the newer item wins (latest data retained).
- Items older than ``retention_days`` are dropped.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.db import get_jobs, get_news

log = logging.getLogger(__name__)

DOCS_DATA_PATH = Path(__file__).parent.parent.parent / "docs" / "data"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    log.info("Wrote %s (%d bytes)", path.name, path.stat().st_size)


def _read_existing(path: Path) -> list[dict]:
    """Read existing JSON items list, return [] if file missing or corrupt."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("items") or []
    except Exception as exc:
        log.warning("Could not read existing %s: %s", path.name, exc)
        return []


def _is_expired(item: dict, retention_days: int) -> bool:
    """Return True if the item is older than retention_days.
    Uses first_seen_at if available (from DB), falls back to published_at/posted_at.
    This avoids expiring jobs that were posted long ago but recently discovered."""
    # Prefer first_seen_at (when we first collected it) over published_at/posted_at
    date_str = item.get("first_seen_at") or item.get("published_at") or item.get("posted_at") or ""
    if not date_str:
        return False  # keep if no date
    try:
        # Strip timezone offset for simple parsing
        cleaned = date_str.replace("+00:00", "").replace("Z", "")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        return age_days > retention_days
    except Exception:
        return False  # keep if date unparseable


def _merge_items(
    existing: list[dict],
    fresh: list[dict],
    retention_days: int,
) -> list[dict]:
    """Merge existing + fresh items. For duplicate IDs, fresh wins.
    Drop items older than retention_days (based on first_seen_at)."""
    by_id: dict[str, dict] = {}

    # Add existing first
    for item in existing:
        item_id = item.get("id")
        if item_id:
            by_id[item_id] = item

    # Fresh items overwrite existing (same ID = keep latest)
    for item in fresh:
        item_id = item.get("id")
        if item_id:
            by_id[item_id] = item
        else:
            # Items without ID: keep anyway
            by_id[f"_no_id_{len(by_id)}"] = item

    # Expire old items
    kept = []
    expired = 0
    for item in by_id.values():
        if _is_expired(item, retention_days):
            expired += 1
            continue
        kept.append(item)

    if expired:
        log.info("Retired %d expired items (older than %d days)", expired, retention_days)

    return kept


def _clean_item(item: dict) -> dict:
    """Remove internal DB fields that shouldn't appear in JSON."""
    # NOTE: keep first_seen_at for retention checking in _is_expired!
    item.pop("last_seen_at", None)
    if not isinstance(item.get("tags"), list):
        item["tags"] = []
    return item


def export_all(
    conn: sqlite3.Connection,
    *,
    output_dir: Path | None = None,
    retention_days: int = 7,
    jobs_retention_days: int = 60,
    source_health: dict[str, str] | None = None,
) -> dict[str, int]:
    """
    Export news + jobs to static JSON files, merging with existing data.

    Returns a dict with counts: {"news": N, "jobs": M}.
    """
    out = output_dir or DOCS_DATA_PATH
    out.mkdir(parents=True, exist_ok=True)

    generated_at = _now_iso()

    # ── News ──────────────────────────────────────────────────────────
    fresh_news = get_news(conn, days=retention_days)
    for item in fresh_news:
        _clean_item(item)

    existing_news = _read_existing(out / "news.json")
    merged_news = _merge_items(existing_news, fresh_news, retention_days)
    # Remove first_seen_at from final JSON output (was kept for merge/expiry logic)
    for item in merged_news:
        item.pop("first_seen_at", None)

    news_payload = {
        "generated_at": generated_at,
        "items": merged_news,
    }
    _write_json(out / "news.json", news_payload)

    # ── Jobs ──────────────────────────────────────────────────────────
    fresh_jobs = get_jobs(conn, days=jobs_retention_days)
    for item in fresh_jobs:
        _clean_item(item)

    existing_jobs = _read_existing(out / "jobs.json")
    merged_jobs = _merge_items(existing_jobs, fresh_jobs, jobs_retention_days)
    # Remove first_seen_at from final JSON output
    for item in merged_jobs:
        item.pop("first_seen_at", None)

    jobs_payload = {
        "generated_at": generated_at,
        "items": merged_jobs,
    }
    _write_json(out / "jobs.json", jobs_payload)

    # ── Meta ──────────────────────────────────────────────────────────
    meta_payload = {
        "generated_at": generated_at,
        "news_count": len(merged_news),
        "jobs_count": len(merged_jobs),
        "source_health": source_health or {},
    }
    _write_json(out / "meta.json", meta_payload)

    log.info(
        "Export complete: %d news (%d fresh), %d jobs (%d fresh) -> %s",
        len(merged_news), len(fresh_news),
        len(merged_jobs), len(fresh_jobs),
        out,
    )
    return {"news": len(merged_news), "jobs": len(merged_jobs)}
