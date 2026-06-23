## Build System Overview

This project uses a **container-first, CI-driven build system** centered on Docker for packaging the data aggregation worker and GitHub Actions for automated scheduling, testing, and deployment. There is no traditional Makefile or shell-based build script; instead, `docker-compose.yml` orchestrates local development while GitHub Workflows handle production execution.

---

## Core Components

### 1. Docker-Based Worker Packaging

The worker application (Python 3.12) is containerized via a **multi-stage Dockerfile** (`worker/Dockerfile`) that:
- Uses `python:3.12-slim` as the base image for minimal footprint
- Creates a non-root `worker` user for security isolation
- Leverages layer caching by installing dependencies (`requirements.txt`) before copying source code
- Sets `ENTRYPOINT ["python", "main.py"]` so the container runs once per invocation (scheduling is external)
- Ensures the `/app/db` directory exists and is writable by the non-root user

Dependencies are managed via `worker/requirements.txt`, listing 10 Python packages including `requests`, `beautifulsoup4`, `openai`, and `gitpython`.

### 2. Local Development with Docker Compose

`docker-compose.yml` defines two services:

- **`worker`**: Builds from `./worker/Dockerfile`, mounts volumes for persistent SQLite database (`./worker/db`) and output JSON files (`./docs/data`). Configured with `restart: "no"` to run once and exit, aligning with the cron-driven execution model. An optional cron sidecar command is commented out for in-container scheduling.

- **`preview`** (optional profile): Runs an `nginx:alpine` container serving the static `docs/` directory on port 8080 for local preview. Activated via `docker compose --profile preview up preview`.

Environment variables are loaded from `.env` (copied from `.env.example`), supporting configuration of API keys, SMTP settings, and log levels.

### 3. GitHub Actions CI/CD Pipelines

Two workflows orchestrate the full lifecycle:

#### `worker-schedule.yml` — Data Refresh Pipeline
- **Trigger**: Cron schedule (`0 */2 * * *`, every 2 hours) + manual dispatch
- **Execution flow**:
  1. Checks out repository with write permissions
  2. Sets up Python 3.12 with pip caching (cache key based on `worker/requirements.txt`)
  3. Installs dependencies directly via `pip install -r worker/requirements.txt` (bypasses Docker for speed in CI)
  4. Runs `python main.py` from the `worker/` directory with secrets injected as environment variables (`OPENROUTER_API_KEY`, SMTP credentials, etc.)
  5. Validates generated JSON output via `pytest tests/test_schema.py`
  6. Commits and pushes updated `docs/data/*.json` files using `devops-news-bot` identity, with `[skip ci]` in commit message to prevent recursive triggers

#### `pages-deploy.yml` — Static Site Deployment
- **Trigger**: Push to `main` branch affecting `docs/**` paths + manual dispatch
- **Execution flow**:
  1. Checks out repository
  2. Configures GitHub Pages via `actions/configure-pages@v5`
  3. Uploads `docs/` directory as artifact via `actions/upload-pages-artifact@v3`
  4. Deploys to GitHub Pages via `actions/deploy-pages@v4`
- Uses concurrency control (`group: "pages"`) to serialize deployments
- Requires `contents: read`, `pages: write`, and `id-token: write` permissions

### 4. Schema Validation Testing

A single test file (`tests/test_schema.py`) validates the structure of generated JSON files (`news.json`, `jobs.json`, `meta.json`) using pytest. Tests verify:
- Required top-level keys exist
- Item arrays contain required fields (`id`, `title`, `url`, `source`, timestamps)
- `relevance_score` values are floats in range [0, 1]
- No duplicate IDs within each dataset
- `meta.json` contains non-negative counts and valid `source_health` dict

This test runs as a gate in the `worker-schedule.yml` pipeline before committing data changes.

---

## Architecture & Conventions

### Separation of Concerns
- **Worker** (`worker/`): Self-contained Python application with its own `Dockerfile`, `requirements.txt`, and `config.yaml`
- **Documentation** (`docs/`): Static HTML/CSS/JS site consuming JSON data produced by the worker
- **Tests** (`tests/`): Schema validation only; no unit tests for collector logic
- **CI/CD** (`.github/workflows/`): Two independent workflows triggered by different events but chained via git commits

### Configuration Strategy
- Runtime configuration lives in `worker/config.yaml` (sources, keywords, retention policy, LLM settings)
- Secrets and environment-specific values use `.env` / GitHub Secrets
- The config file supports enabling/disabling individual sources without code changes

### Execution Model
- The worker is **stateless per run**: it collects, scores, deduplicates, writes JSON, then exits
- State persistence relies on:
  - SQLite database (`worker/db/`) mounted as a volume for deduplication across runs
  - Git-tracked JSON files (`docs/data/`) for published output
- Scheduling is **external**: either GitHub Actions cron or host-level cron invoking `docker compose up --build worker`

### Deployment Flow
1. Worker runs → updates `docs/data/*.json`
2. Git commit triggers `pages-deploy.yml`
3. GitHub Pages serves updated static site

This creates a **push-based deployment** where data changes automatically trigger site redeployment.

---

## Rules for Developers

1. **Dependency Management**: Add new Python packages to `worker/requirements.txt` with version constraints. The CI pipeline caches dependencies based on this file's hash.

2. **Configuration Changes**: Modify `worker/config.yaml` to add/remove news sources, job boards, or keyword filters. No code changes needed for most source adjustments.

3. **Schema Compliance**: Any change to the worker's JSON output format must be reflected in `tests/test_schema.py`. The schema validation test blocks deployment if output structure is invalid.

4. **Secrets Handling**: New API keys or credentials must be added as GitHub Secrets (Settings → Secrets → Actions). Document required secrets in workflow YAML comments.

5. **Local Testing**: Use `docker compose up --build worker` for end-to-end local runs. Use `docker compose --profile preview up preview` for local site preview.

6. **Commit Convention**: The worker's auto-commits use `[skip ci]` to prevent infinite loops. Manual commits affecting `docs/data/` will trigger page deployment.

7. **No Makefile**: There is no `Makefile` or `build.sh`. All build/run commands go through `docker compose` or direct `python`/`pip` invocations.

8. **Python Version**: The project targets Python 3.12 explicitly in both the Dockerfile and GitHub Actions setup. Do not downgrade.
