## Overview

This Python-based content aggregation pipeline uses a **logging-centric, non-exceptional** error handling approach. Rather than defining custom exception types or propagating errors up call stacks, the codebase catches exceptions at module boundaries, logs them, and continues execution with degraded functionality. This is appropriate for a scheduled batch pipeline where partial failures should not abort the entire run.

## Core Patterns

### 1. Try/Except at Collector Boundaries

Every external data source collector (news and jobs) wraps its entire `collect()` function body in a bare `except Exception` block:

```python
try:
    # HTTP requests, parsing, etc.
except Exception as exc:
    log.error("Source '%s' failed: %s", name, exc)
```

Key characteristics:
- **No re-raising**: Errors are swallowed after logging; collectors return empty lists on failure.
- **Bare `Exception`**: No distinction between network errors, parse errors, or API errors — all treated uniformly.
- **Caller-level tracking**: The orchestrator (`main.py`) maintains an `errors: list[str]` that accumulates formatted error strings like `"news:hacker_news: ConnectionError..."` for later persistence to the `run_log` table.

### 2. Orchestrator-Level Error Aggregation

In `worker/main.py`, each collector invocation is wrapped in a helper (`_collect_news`, `_collect_jobs`) that:
- Catches any exception from the collector
- Logs via `log.error()`
- Appends a structured error string to the `errors` list
- Records source health status (`"ok"` or `"error"`) in a `source_health` dict

The aggregated errors are persisted to SQLite via `finish_run()` and included in the final log summary.

### 3. Transaction Rollback Pattern

`worker/storage/db.py` provides a context manager for database transactions:

```python
@contextmanager
def transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise  # Re-raises to caller
```

This is one of the few places where exceptions are **re-raised**, allowing the orchestrator to handle DB-level failures explicitly.

### 4. LLM Scoring Graceful Degradation

In `worker/scoring/llm_relevance.py`, LLM batch scoring failures are handled by:
- Catching exceptions during `_chat()` calls
- Logging the error
- Falling back to unscored items (`out.extend(batch)`)

This ensures the pipeline never drops items due to LLM API failures — they simply retain their default score of `0.0`.

### 5. SMTP Notification Error Propagation

`worker/notify/smtp_alert.py` is notable for **re-raising** after logging:

```python
except Exception as exc:
    log.error("SMTP send failed: %s", exc)
    raise
```

However, the caller in `main.py` wraps this in its own `try/except`, so the re-raise has no practical effect — the error is still caught and logged at the orchestrator level.

### 6. Git Publish Failure Isolation

The `git_publish()` function in `main.py` catches all exceptions internally and only logs — it never propagates. A git failure does not prevent the run from completing or being recorded.

## Key Files

| File | Role |
|------|------|
| `worker/main.py` | Orchestrator; aggregates errors from all sources, persists to `run_log` |
| `worker/storage/db.py` | DB transaction management with rollback; error persistence via `finish_run()` |
| `worker/scoring/llm_relevance.py` | LLM scoring with graceful degradation on API failure |
| `worker/notify/smtp_alert.py` | SMTP digest with conditional skip and error logging |
| `worker/collectors/jobs/*.py` | Individual job collectors, each with bare `except Exception` |
| `worker/collectors/news/*.py` | Individual news collectors, same pattern |

## Conventions Developers Should Follow

1. **Collectors must never raise**: Every `collect()` function should catch all exceptions internally, log them, and return whatever items were successfully gathered (possibly an empty list).

2. **Use `log.error()` for operational failures**: All external-facing errors (HTTP, API, parsing) should be logged at ERROR level with sufficient context (source name, exception message).

3. **Track errors in the orchestrator**: The `errors` list in `main.py` is the single source of truth for run-level error reporting. Always append structured strings like `f"{category}:{source}: {exc}"`.

4. **Graceful degradation over hard failures**: When optional services fail (LLM scoring, SMTP, git push), log and continue. The pipeline should always complete and produce output even if some enrichment steps are skipped.

5. **No custom exception types**: The codebase does not define any custom exception classes. All error differentiation is done via log messages and error string prefixes.

6. **Database transactions use the context manager**: Always wrap multi-statement DB operations in `with transaction(conn):` to ensure atomicity and automatic rollback on failure.

## What Is Not Present

- No custom exception hierarchy or error codes
- No retry logic with exponential backoff (collectors make single attempts)
- No circuit breaker or rate-limiting beyond simple `time.sleep()` calls
- No structured error objects — errors are plain strings
- No error monitoring/integration (e.g., Sentry, Datadog)
- No panic/recover pattern (Python does not have panics; no `sys.excepthook` override)