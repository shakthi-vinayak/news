## Overview

The application uses a **two-layer configuration approach**:

1. **`config.yaml`** — Static application settings (sources, keywords, retention, LLM parameters) that rarely change and are safe to commit.
2. **Environment variables via `.env`** — Secrets and runtime toggles (API keys, SMTP credentials, git tokens, feature flags) loaded with `python-dotenv`.

This separation follows the [12-factor app](https://12factor.net/config) principle of keeping config that varies between deploys strictly in the environment, while keeping structural/behavioral config in version-controlled files.

---

## Key Files

| File | Purpose |
|------|---------|
| `worker/config.yaml` | Primary application configuration — defines all news/job sources, keyword filters, LLM model settings, retention policy |
| `.env.example` | Template for required environment variables; developers copy to `.env` and fill in real values |
| `worker/main.py` | Loads both config layers: `yaml.safe_load()` for `config.yaml`, `load_dotenv()` for `.env` (with fallback to repo root) |
| `docker-compose.yml` | Injects `.env` into the worker container via `env_file` directive |
| `worker/scoring/llm_relevance.py` | Reads OpenRouter API credentials directly from `os.getenv()` at module load time |
| `worker/notify/smtp_alert.py` | Reads SMTP credentials from `os.getenv()` at call time |

---

## Architecture and Conventions

### Layer 1: YAML Configuration (`config.yaml`)

- **Location**: `worker/config.yaml`
- **Loaded by**: `load_config()` in `worker/main.py` using `yaml.safe_load()`
- **Contents**:
  - `retention_days`: Data retention window (default 30 days)
  - `llm`: Model selection, batch size, token limits, temperature, pre-filter keywords
  - `keyword_filter`: Global keyword gate applied before LLM scoring (case-insensitive match)
  - `news.*`: Per-source settings (enabled flag, tags/subreddits/feeds/repos, max items, rate-limit delays)
  - `jobs.*`: Per-source settings (enabled flag, keywords/tags/categories/board slugs)
- **Design decision**: All source enable/disable toggles and collection parameters live here so operators can adjust behavior without code changes.

### Layer 2: Environment Variables (`.env`)

- **Loading strategy** in `worker/main.py`:
  ```python
  load_dotenv(Path(__file__).parent / ".env")       # worker/.env
  load_dotenv(Path(__file__).parent.parent / ".env") # repo-root .env fallback
  ```
  This dual-path loading supports running from either the `worker/` directory or the repo root.

- **Categories of env vars**:
  - **Secrets**: `OPENROUTER_API_KEY`, `SMTP_PASSWORD`, `GH_PAT`
  - **Endpoints/URLs**: `OPENROUTER_BASE_URL`, `GIT_REPO_URL`
  - **Runtime toggles**: `LOG_LEVEL`, `DRY_RUN`, `SMTP_ENABLED`
  - **Identity**: `GIT_USER_NAME`, `GIT_USER_EMAIL`, `SMTP_FROM`

- **Module-level env reads**: `worker/scoring/llm_relevance.py` reads `OPENROUTER_*` vars at import time as module-level constants. This means the values are frozen when the module is first imported.

- **Function-level env reads**: `worker/notify/smtp_alert.py` and `worker/main.py` read env vars inside functions via `os.getenv()`, allowing potential runtime overrides (though in practice the process runs once per invocation).

### Docker Integration

- `docker-compose.yml` uses `env_file: - .env` to inject all environment variables into the worker container.
- The SQLite database path (`./worker/db`) and output JSON path (`./docs/data`) are mounted as volumes, making persistence external to the container.
- `LOG_LEVEL` can be overridden at compose time via `${LOG_LEVEL:-INFO}` interpolation.

### CI/CD Configuration

- GitHub Actions workflows (`.github/workflows/`) use `GITHUB_TOKEN` automatically for git pushes, bypassing the need for `GH_PAT` in the hosted runner environment.
- The `.env` file is **never committed** (listed in `.gitignore`); only `.env.example` is tracked.

---

## Rules Developers Should Follow

1. **Never commit `.env`** — Only `.env.example` is tracked. Copy it with `cp .env.example .env` and fill in real values locally.

2. **Add new non-secret settings to `config.yaml`** — Source lists, keyword filters, retention windows, batch sizes, and other behavioral parameters belong in YAML, not as environment variables.

3. **Add new secrets as environment variables** — API keys, passwords, tokens, and any credential must come from `os.getenv()`. Add a corresponding entry in `.env.example` with a placeholder value.

4. **Use `os.getenv(key, default)` with sensible defaults** — All env var reads should provide a fallback to prevent crashes when a variable is unset. For optional features (like SMTP), check for completeness before proceeding.

5. **Prefer function-level `os.getenv()` over module-level constants for optional features** — Module-level reads (as in `llm_relevance.py`) freeze values at import time. For features that may be conditionally enabled, read inside the function.

6. **Enable/disable sources via `config.yaml`** — Each news and job source has an `enabled: true/false` flag. Toggle this instead of commenting out code.

7. **Use `DRY_RUN=true` for testing** — Set this env var to skip git push and SMTP sending during development or debugging.

8. **Keyword filter is a pre-LLM gate** — Items must match at least one keyword in `keyword_filter` before being sent to the LLM for scoring. Keep this list focused to control API costs.
