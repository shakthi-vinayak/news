The application uses Python's built-in `logging` module for all logging needs, avoiding third-party frameworks like `loguru` or `structlog`. 

### Configuration and Initialization
Logging is configured once in the application entrypoint (`worker/main.py`) using `logging.basicConfig`. The configuration is driven by the `LOG_LEVEL` environment variable (defaulting to `INFO`), allowing operators to adjust verbosity without code changes. 

- **Format**: `%(asctime)s %(levelname)-8s %(name)s: %(message)s`
- **Date Format**: ISO 8601 style (`%Y-%m-%dT%H:%M:%S`)
- **Output**: Standard output (`sys.stdout`), suitable for containerized environments and CI/CD pipelines.

### Logger Usage Patterns
Modules follow a consistent convention for obtaining logger instances:
```python
import logging
log = logging.getLogger(__name__)
```
This ensures that log messages are namespaced by their module path (e.g., `collectors.news.devto`, `scoring.llm_relevance`), making it easy to filter logs by source during debugging.

### Log Levels and Conventions
- **INFO**: Used for high-level workflow milestones (e.g., "Run started", "Collected X items", "Persisted Y records") and summary statistics.
- **ERROR**: Used when a specific data source fails (e.g., network error, API failure) but the overall pipeline continues. This supports the application's "graceful degradation" strategy, where one failing source doesn't stop the entire collection cycle.
- **WARNING**: Used for non-critical issues, such as missing API keys that disable optional features (e.g., LLM scoring).

### Key Files
- `worker/main.py`: Central logging configuration and root logger usage.
- `worker/collectors/**/*.py`: Individual collectors use module-level loggers to report source-specific status.
- `worker/scoring/llm_relevance.py`: Uses logging to report LLM API errors and fallback behavior.
- `.env.example`: Documents the `LOG_LEVEL` environment variable.