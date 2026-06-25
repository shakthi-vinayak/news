This Python-based content aggregation pipeline employs a **logging-centric, non-exceptional** error handling strategy. Rather than defining custom exception types or propagating errors up the call stack, the system isolates failures at the component level (collectors, LLM scorers, Git publisher) and uses `try/except` blocks to catch all exceptions, log them, and continue execution. This ensures that a failure in one data source (e.g., Dev.to API down) does not halt the entire pipeline, allowing other sources to be processed and the final JSON export to still occur.

### Core Approach: Isolate, Log, Continue
The primary pattern is **graceful degradation**. Each external interaction (HTTP requests, database transactions, Git operations) is wrapped in a `try/except Exception` block. When an error occurs:
1. It is logged using `logging.error()` or `logging.warning()` with context (e.g., source name).
2. The error is optionally recorded in a local `errors` list for later reporting in the `run_log` table.
3. Execution continues with the next item or source.

### Key Components & Patterns

#### 1. Collector Isolation (`worker/main.py`, `worker/collectors/`)
Each news and job collector is invoked within a helper function (`_collect_news`, `_collect_jobs`) that catches any exception. If a collector fails, its status is marked as "error" in `source_health`, and the error message is appended to the `errors` list. The collector itself (e.g., `devto.py`) also contains internal `try/except` blocks to handle individual tag failures without crashing the whole collector.

```python
def _collect_news(name: str, module, src_cfg: dict) -> None:
    try:
        items = module.collect(src_cfg)
        # ... process items ...
    except Exception as exc:
        log.error("News source '%s' failed: %s", name, exc)
        errors.append(f"news:{name}: {exc}")
```

#### 2. LLM Scoring Fallback (`worker/scoring/llm_relevance.py`)
LLM calls are batched and wrapped in `try/except`. If a batch fails (e.g., API rate limit, network error), the system logs the error and **returns the unscored items** rather than dropping them. This prevents data loss due to transient AI service issues.

```python
except Exception as exc:
    log.error("LLM news batch %d failed: %s", i // batch_size, exc)
    out.extend(batch)  # keep unscored items rather than dropping them
```

#### 3. Database Transaction Safety (`worker/storage/db.py`)
Database writes use a context manager `transaction()` that automatically rolls back on any exception. This ensures atomicity for batch inserts/updates.

```python
@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise  # Re-raise to be caught by the caller (main.py)
```

#### 4. Startup Validation (`worker/main.py`)
The `_check_secrets()` function performs a "fail-fast" check for required environment variables. If secrets are missing, it prints a clear error message and calls `sys.exit()`, preventing the pipeline from running in a broken state.

### Conventions for Developers
- **No Custom Exceptions**: The codebase does not define custom exception classes. Standard Python exceptions (`Exception`, `RuntimeError`) are used.
- **Catch Broadly at Boundaries**: Use `except Exception` at the boundaries of external interactions (API calls, file I/O) to prevent crashes.
- **Log Contextually**: Always include identifying information (source name, batch index) in log messages.
- **Never Swallow Silently**: Every `except` block must log the error or take explicit action (like rolling back a transaction).
- **Graceful Degradation**: Prefer returning partial results or skipping failed items over crashing the entire process.