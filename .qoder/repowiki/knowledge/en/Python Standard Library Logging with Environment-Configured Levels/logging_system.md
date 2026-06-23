## Overview

This repository uses Python's built-in `logging` module as its sole logging framework. There is no third-party structured logging library (e.g., structlog, loguru) — all logging is done through the standard library's `Logger` API.

## Configuration and Initialization

Logging is configured once at application startup in `worker/main.py`:

```python
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
```

Key characteristics:
- **Log level** is controlled via the `LOG_LEVEL` environment variable (default: `INFO`). This is propagated through `.env.example`, `docker-compose.yml`, and GitHub Actions workflows.
- **Output destination** is always `stdout` — suitable for containerized environments where stdout is captured by the orchestrator.
- **Timestamp format** uses ISO 8601-style formatting (`%Y-%m-%dT%H:%M:%S`) without timezone or milliseconds.
- **Format string** includes: timestamp, left-padded log level (8 chars), logger name, and message.

## Logger Naming Convention

Every module follows the same pattern for obtaining a logger:

```python
import logging
log = logging.getLogger(__name__)
```

This produces hierarchical logger names that mirror the package structure, e.g.:
- `main` (from `worker/main.py`)
- `collectors.news.hn_algolia`
- `collectors.jobs.remoteok`
- `scoring.llm_relevance`
- `storage.db`
- `notify.smtp_alert`

The logger name appears in every log line, enabling easy filtering by source module.

## Log Level Usage Patterns

The codebase uses four log levels consistently:

| Level | Usage |
|-------|-------|
| `DEBUG` | Fuzzy deduplication matches (`dedupe.py`), per-board job counts (`greenhouse.py`, `lever.py`) |
| `INFO` | Collection summaries ("collected N items"), pipeline milestones (run start/complete, persistence counts), SMTP digest sent, DB initialization |
| `WARNING` | Missing API keys (`OPENROUTER_API_KEY`), missing configuration (`SMTP not fully configured`), expected-but-not-found resources (404 boards, missing HN thread), RSS bozo errors |
| `ERROR` | Collector failures (network errors, API failures), LLM batch failures, Git publish failures, SMTP send failures |

Notable patterns:
- **Errors are caught, logged, and swallowed** in collector modules to prevent one failing source from stopping the entire pipeline. Errors are accumulated in a list and persisted to the `run_log` table.
- **LLM scoring gracefully degrades**: if `OPENROUTER_API_KEY` is not set, a `WARNING` is logged and items pass through unscored rather than causing a crash.
- **No `CRITICAL` level** is used anywhere in the codebase.

## Structured Fields

There is **no structured/JSON logging**. All log output is plain text using the format string defined in `basicConfig`. Contextual data (item counts, run IDs, source names) is interpolated into messages using `%`-style formatting:

```python
log.info("Run %s started (dry_run=%s)", run_id, dry_run)
log.error("News source '%s' failed: %s", name, exc)
```

The only semi-structured logging artifact is the `run_log` SQLite table, which stores per-run metadata including an `errors` column containing a JSON array of error strings.

## Key Files

- `worker/main.py` — Central logging configuration via `logging.basicConfig()`; orchestrator-level INFO/ERROR logs for pipeline stages.
- `worker/collectors/news/*.py` — Per-source collectors using `log.error()` for failures and `log.info()` for collection counts.
- `worker/collectors/jobs/*.py` — Same pattern as news collectors.
- `worker/scoring/llm_relevance.py` — Uses `log.warning()` when API key is missing, `log.error()` for LLM batch failures.
- `worker/scoring/dedupe.py` — Uses `log.debug()` for fuzzy match details, `log.info()` for dedup summary.
- `worker/storage/db.py` — Single `log.info()` call on DB initialization.
- `worker/notify/smtp_alert.py` — Uses `log.warning()` for misconfiguration, `log.info()` for successful sends, `log.error()` for failures.

## Developer Conventions

1. **Always use `logging.getLogger(__name__)`** — never create loggers with hardcoded names.
2. **Use `%`-style interpolation** in log calls (not f-strings) to avoid unnecessary string construction when the message is below the active log level.
3. **Catch and log exceptions in collectors** — do not let individual source failures crash the pipeline. Append error strings to the `errors` list for persistence.
4. **Log collection counts at INFO level** — every collector ends with `log.info("<Source>: collected %d items", count)`.
5. **Use WARNING for recoverable/expected issues** (missing config, 404s, empty results) and ERROR for unexpected failures (network errors, parsing failures).
6. **Do not add new logging frameworks** — the project intentionally uses only the standard library to minimize dependencies.
7. **Control verbosity via `LOG_LEVEL` env var** — valid values are `DEBUG`, `INFO`, `WARNING`, `ERROR`.