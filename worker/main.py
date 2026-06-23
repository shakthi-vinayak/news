"""
worker/main.py
Orchestrator entrypoint — runs one full collection cycle:
  1. Collect news + jobs from all enabled sources
  2. Deduplicate
  3. Score/tag via OpenRouter (keyword pre-filter to limit LLM calls)
  4. Persist to SQLite
  5. Export static JSON files
  6. Publish (git commit + push) unless DRY_RUN=true

Secrets are loaded exclusively from environment variables.
NEVER put real credentials in config.yaml or any committed file.
For local runs: copy .env.example → .env and fill in values.
For GitHub Actions: add secrets via Settings → Secrets → Actions.
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── Load .env (local dev only — never committed) ──────────────────────────
# Loads .env from worker/ or repo root if present.
# In GitHub Actions / CI, secrets come from the environment directly.
load_dotenv(Path(__file__).parent / ".env", override=False)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)


# ── Secrets validation ─────────────────────────────────────────────────────
def _check_secrets() -> None:
    """
    Warn if OPENROUTER_API_KEY is missing — collection still runs, LLM scoring
    is skipped gracefully. Items will appear unscored (relevance_score=0.0).
    NEVER reads secrets from config.yaml or any committed file.
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        log.warning(
            "OPENROUTER_API_KEY is not set -- LLM scoring/summarisation will be "
            "skipped. Items will still be collected and published. "
            "Set the secret at Settings -> Secrets -> Actions to enable scoring."
        )

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("main")

# ── Path setup (allow running from repo root or worker/) ───────────────────
WORKER_DIR = Path(__file__).parent
sys.path.insert(0, str(WORKER_DIR))

# ── Imports (after sys.path is set) ────────────────────────────────────────
from collectors.news import (
    devto,
    github_releases,
    hn_algolia,
    reddit,
    rss_feeds,
)
from collectors.jobs import (
    arbeitnow,
    greenhouse,
    hn_whoishiring,
    lever,
    remoteok,
    remotive,
    weworkremotely_rss,
)
from scoring.dedupe import (
    dedup_batch,
    is_job_seen,
    is_news_seen,
    passes_keyword_filter,
)
from scoring.llm_relevance import score_jobs_batch, score_news_batch
from storage.db import finish_run, init_db, start_run, transaction, upsert_job, upsert_news
from storage.export_json import export_all


# ── Config ─────────────────────────────────────────────────────────────────
def load_config() -> dict:
    cfg_path = WORKER_DIR / "config.yaml"
    with open(cfg_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── Git publish ────────────────────────────────────────────────────────────
def git_publish(repo_root: Path) -> None:
    """Commit + push updated docs/data/*.json using GitPython."""
    try:
        import git  # gitpython

        pat      = os.getenv("GH_PAT", "")
        repo_url = os.getenv("GIT_REPO_URL", "")
        branch   = os.getenv("GIT_BRANCH", "main")
        username = os.getenv("GIT_USER_NAME", "devops-news-bot")
        email    = os.getenv("GIT_USER_EMAIL", "bot@example.com")

        repo = git.Repo(repo_root)
        repo.config_writer().set_value("user", "name",  username).release()
        repo.config_writer().set_value("user", "email", email).release()

        data_dir = repo_root / "docs" / "data"
        repo.index.add([
            str(data_dir / "news.json"),
            str(data_dir / "jobs.json"),
            str(data_dir / "meta.json"),
        ])

        changed = repo.index.diff("HEAD")
        if not changed:
            log.info("Git: nothing changed, skipping commit")
            return

        repo.index.commit("chore: update news/jobs data [skip ci]")

        if pat and repo_url:
            # Inject PAT into URL for push
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(repo_url)
            authed = parsed._replace(netloc=f"{pat}@{parsed.netloc}")
            remote_url = urlunparse(authed)
            origin = repo.remote("origin")
            origin.set_url(remote_url)
            origin.push(refspec=f"HEAD:{branch}")
            log.info("Git: pushed to %s/%s", repo_url, branch)
        else:
            log.info(
                "Git: committed locally (no GH_PAT / GIT_REPO_URL set — "
                "use GitHub Actions or set both env vars for auto-push)"
            )

    except Exception as exc:
        log.error("Git publish failed: %s", exc)


# ── Main pipeline ──────────────────────────────────────────────────────────
def run() -> None:
    _check_secrets()
    cfg           = load_config()
    retention     = cfg.get("retention_days", 30)
    llm_cfg       = cfg.get("llm", {})
    batch_size    = llm_cfg.get("batch_size", 10)
    kw_filter     = cfg.get("keyword_filter", [])
    news_cfg      = cfg.get("news", {})
    jobs_cfg      = cfg.get("jobs", {})
    job_keywords  = jobs_cfg.get("keywords", [])
    dry_run       = os.getenv("DRY_RUN", "false").lower() == "true"

    repo_root     = WORKER_DIR.parent
    db_path       = WORKER_DIR / "db" / "app.db"
    run_id        = str(uuid.uuid4())
    errors: list[str] = []

    conn = init_db(db_path)
    start_run(conn, run_id)
    log.info("Run %s started (dry_run=%s)", run_id, dry_run)

    # ── 1. Collect news ────────────────────────────────────────────────────
    raw_news: list[dict] = []
    source_health: dict[str, str] = {}

    def _collect_news(name: str, module, src_cfg: dict) -> None:
        try:
            items = module.collect(src_cfg)
            raw_news.extend(items)
            source_health[name] = "ok"
        except Exception as exc:
            log.error("News source '%s' failed: %s", name, exc)
            errors.append(f"news:{name}: {exc}")
            source_health[name] = "error"

    if news_cfg.get("hacker_news", {}).get("enabled", True):
        _collect_news("hacker_news", hn_algolia, news_cfg["hacker_news"])
    if news_cfg.get("devto", {}).get("enabled", True):
        _collect_news("devto", devto, news_cfg["devto"])
    if news_cfg.get("reddit", {}).get("enabled", True):
        _collect_news("reddit", reddit, news_cfg["reddit"])
    if news_cfg.get("rss_feeds", {}).get("enabled", True):
        _collect_news("rss_feeds", rss_feeds, news_cfg["rss_feeds"])
    if news_cfg.get("github_releases", {}).get("enabled", True):
        _collect_news("github_releases", github_releases, news_cfg["github_releases"])

    log.info("Total raw news items: %d", len(raw_news))

    # ── 2. Dedupe news ─────────────────────────────────────────────────────
    raw_news = dedup_batch(raw_news)
    new_news = [
        item for item in raw_news
        if not is_news_seen(conn, item["id"])
        and passes_keyword_filter(item, kw_filter)
    ]
    log.info("New news items (after dedupe + keyword filter): %d", len(new_news))

    # ── 3. Score news ──────────────────────────────────────────────────────
    if new_news:
        new_news = score_news_batch(
            new_news,
            model=llm_cfg.get("model"),
            batch_size=batch_size,
        )

    # ── 4. Persist news ────────────────────────────────────────────────────
    news_inserted = 0
    with transaction(conn):
        for item in new_news:
            if upsert_news(conn, item):
                news_inserted += 1
    log.info("News persisted: %d new, %d total processed", news_inserted, len(new_news))

    # ── 5. Collect jobs ────────────────────────────────────────────────────
    raw_jobs: list[dict] = []

    def _collect_jobs(name: str, module, src_cfg: dict) -> None:
        # Pass job-level keywords into each collector
        merged_cfg = {**src_cfg, "keywords": job_keywords}
        try:
            items = module.collect(merged_cfg)
            raw_jobs.extend(items)
            source_health[name] = "ok"
        except Exception as exc:
            log.error("Jobs source '%s' failed: %s", name, exc)
            errors.append(f"jobs:{name}: {exc}")
            source_health[name] = "error"

    if jobs_cfg.get("remoteok", {}).get("enabled", True):
        _collect_jobs("remoteok", remoteok, jobs_cfg["remoteok"])
    if jobs_cfg.get("remotive", {}).get("enabled", True):
        _collect_jobs("remotive", remotive, jobs_cfg["remotive"])
    if jobs_cfg.get("weworkremotely", {}).get("enabled", True):
        _collect_jobs("weworkremotely", weworkremotely_rss, jobs_cfg["weworkremotely"])
    if jobs_cfg.get("arbeitnow", {}).get("enabled", True):
        _collect_jobs("arbeitnow", arbeitnow, jobs_cfg["arbeitnow"])
    if jobs_cfg.get("hn_whoishiring", {}).get("enabled", True):
        _collect_jobs("hn_whoishiring", hn_whoishiring, jobs_cfg["hn_whoishiring"])
    if jobs_cfg.get("greenhouse", {}).get("enabled", True):
        _collect_jobs("greenhouse", greenhouse, jobs_cfg["greenhouse"])
    if jobs_cfg.get("lever", {}).get("enabled", True):
        _collect_jobs("lever", lever, jobs_cfg["lever"])

    log.info("Total raw job items: %d", len(raw_jobs))

    # ── 6. Dedupe jobs ─────────────────────────────────────────────────────
    raw_jobs = dedup_batch(raw_jobs)
    new_jobs = [
        item for item in raw_jobs
        if not is_job_seen(conn, item["id"])
    ]
    log.info("New job items (after dedupe): %d", len(new_jobs))

    # ── 7. Score jobs ──────────────────────────────────────────────────────
    if new_jobs:
        new_jobs = score_jobs_batch(
            new_jobs,
            model=llm_cfg.get("model"),
            batch_size=batch_size,
        )

    # ── 8. Persist jobs ────────────────────────────────────────────────────
    jobs_inserted = 0
    with transaction(conn):
        for item in new_jobs:
            if upsert_job(conn, item):
                jobs_inserted += 1
    log.info("Jobs persisted: %d new, %d total processed", jobs_inserted, len(new_jobs))

    # ── 9. Export JSON ─────────────────────────────────────────────────────
    output_dir = repo_root / "docs" / "data"
    counts = export_all(
        conn,
        output_dir=output_dir,
        retention_days=retention,
        source_health=source_health,
    )

    # ── 10. Finish run log ─────────────────────────────────────────────────
    finish_run(
        conn,
        run_id,
        news_collected=counts["news"],
        jobs_collected=counts["jobs"],
        errors=errors,
    )

    # ── 11. Publish ────────────────────────────────────────────────────────
    if not dry_run:
        git_publish(repo_root)
    else:
        log.info("DRY_RUN=true — skipping git publish")

    log.info(
        "Run %s complete. News: %d total / %d new. Jobs: %d total / %d new. Errors: %d",
        run_id, counts["news"], news_inserted,
        counts["jobs"], jobs_inserted, len(errors),
    )


if __name__ == "__main__":
    run()
