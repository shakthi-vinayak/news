"""
tests/test_schema.py
Validate docs/data/*.json against the documented schema.
Run with:  pytest tests/test_schema.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"

NEWS_ITEM_REQUIRED = {"id", "title", "url", "source", "published_at"}
JOBS_ITEM_REQUIRED = {"id", "title", "company", "url", "source", "posted_at"}


# ── Helpers ──────────────────────────────────────────────────────────────────
def load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    assert path.exists(), f"{filename} not found in docs/data/"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ── Tests ────────────────────────────────────────────────────────────────────
class TestMetaJson:
    def test_file_exists_and_is_valid_json(self):
        meta = load_json("meta.json")
        assert isinstance(meta, dict)

    def test_required_keys(self):
        meta = load_json("meta.json")
        for key in ("generated_at", "news_count", "jobs_count", "source_health"):
            assert key in meta, f"meta.json missing key: {key}"

    def test_counts_are_non_negative(self):
        meta = load_json("meta.json")
        assert meta["news_count"] >= 0
        assert meta["jobs_count"] >= 0

    def test_source_health_is_dict(self):
        meta = load_json("meta.json")
        assert isinstance(meta["source_health"], dict)

    def test_generated_at_is_string(self):
        meta = load_json("meta.json")
        assert isinstance(meta["generated_at"], str)
        assert meta["generated_at"]  # non-empty


class TestNewsJson:
    def test_file_exists_and_is_valid_json(self):
        news = load_json("news.json")
        assert isinstance(news, dict)

    def test_required_top_level_keys(self):
        news = load_json("news.json")
        assert "generated_at" in news
        assert "items" in news

    def test_items_is_list(self):
        news = load_json("news.json")
        assert isinstance(news["items"], list)

    @pytest.mark.parametrize("field", sorted(NEWS_ITEM_REQUIRED))
    def test_news_item_has_required_field(self, field: str):
        news = load_json("news.json")
        for i, item in enumerate(news["items"]):
            assert field in item, (
                f"news.json items[{i}] missing required field '{field}'"
            )

    def test_news_item_tags_is_list(self):
        news = load_json("news.json")
        for i, item in enumerate(news["items"]):
            assert isinstance(item.get("tags", []), list), (
                f"news.json items[{i}].tags must be a list"
            )

    def test_news_item_relevance_score_is_float_or_zero(self):
        news = load_json("news.json")
        for i, item in enumerate(news["items"]):
            score = item.get("relevance_score", 0)
            assert isinstance(score, (int, float)), (
                f"news.json items[{i}].relevance_score must be numeric"
            )
            assert 0.0 <= float(score) <= 1.0, (
                f"news.json items[{i}].relevance_score out of range [0,1]: {score}"
            )

    def test_no_duplicate_ids(self):
        news = load_json("news.json")
        ids = [item["id"] for item in news["items"]]
        assert len(ids) == len(set(ids)), "Duplicate IDs found in news.json"


class TestJobsJson:
    def test_file_exists_and_is_valid_json(self):
        jobs = load_json("jobs.json")
        assert isinstance(jobs, dict)

    def test_required_top_level_keys(self):
        jobs = load_json("jobs.json")
        assert "generated_at" in jobs
        assert "items" in jobs

    def test_items_is_list(self):
        jobs = load_json("jobs.json")
        assert isinstance(jobs["items"], list)

    @pytest.mark.parametrize("field", sorted(JOBS_ITEM_REQUIRED))
    def test_jobs_item_has_required_field(self, field: str):
        jobs = load_json("jobs.json")
        for i, item in enumerate(jobs["items"]):
            assert field in item, (
                f"jobs.json items[{i}] missing required field '{field}'"
            )

    def test_jobs_item_relevance_score_is_float_or_zero(self):
        jobs = load_json("jobs.json")
        for i, item in enumerate(jobs["items"]):
            score = item.get("relevance_score", 0)
            assert isinstance(score, (int, float)), (
                f"jobs.json items[{i}].relevance_score must be numeric"
            )
            assert 0.0 <= float(score) <= 1.0, (
                f"jobs.json items[{i}].relevance_score out of range [0,1]: {score}"
            )

    def test_no_duplicate_ids(self):
        jobs = load_json("jobs.json")
        ids = [item["id"] for item in jobs["items"]]
        assert len(ids) == len(set(ids)), "Duplicate IDs found in jobs.json"
