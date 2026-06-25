The project employs a containerized build and deployment strategy centered around **GitHub Actions** for automation and **Docker** for consistent runtime environments. The system is designed as a scheduled data pipeline that aggregates, processes, and publishes content to a static site.

### Build & Runtime Environment
- **Dockerization**: The core worker application resides in the `worker/` directory and is containerized using a multi-stage `Dockerfile` based on `python:3.12-slim`. It installs dependencies from `requirements.txt`, copies source code, and configures a non-root user (`worker`) for security. The entry point is `python main.py`, designed to run once per invocation.
- **Local Development & Testing**: A `docker-compose.yml` file orchestrates local execution. It defines a `worker` service that mounts the SQLite database (`worker/db`) and output directory (`docs/data`) as volumes, allowing persistent state and immediate feedback during development. An optional `preview` service uses `nginx:alpine` to serve the static `docs/` folder on port 8080.

### CI/CD Pipelines (GitHub Actions)
The repository uses two distinct workflows to manage the lifecycle of the application and its output:

1. **Data Refresh Pipeline (`worker-schedule.yml`)**:
   - **Trigger**: Runs on a cron schedule (`0 */2 * * *`, every 2 hours), on pushes to `worker/` code, or manually via `workflow_dispatch`.
   - **Execution**: Instead of building a Docker image, this workflow sets up a Python 3.12 environment directly on the GitHub runner. It installs dependencies via `pip`, runs the worker script (`python main.py`) with secrets injected as environment variables, and validates the output JSON schema using `pytest`.
   - **Deployment**: Upon successful execution and validation, the workflow commits and pushes the updated `docs/data/*.json` files back to the `main` branch using the `GITHUB_TOKEN`. This "GitOps" approach treats the generated data as version-controlled artifacts.

2. **Static Site Deployment (`pages-deploy.yml`)**:
   - **Trigger**: Activated when changes are pushed to the `docs/` directory (typically after the data refresh workflow commits new JSON) or via manual dispatch.
   - **Execution**: Uses the official `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages` actions to build and deploy the static HTML/CSS/JS site to **GitHub Pages**.
   - **Concurrency**: Configured to allow only one concurrent deployment to prevent race conditions.

### Dependency Management
- **Python Dependencies**: Managed via `worker/requirements.txt` with pinned minimum versions for libraries like `requests`, `beautifulsoup4`, `openai`, and `rapidfuzz`.
- **Caching**: The CI pipeline leverages `actions/setup-python` with `cache: pip` to speed up dependency installation.

### Key Conventions
- **Ephemeral Workers**: The worker container/script is designed to run once and exit. Scheduling is handled externally by GitHub Actions Cron or host-level cron jobs, not by internal daemon loops.
- **Volume Mounting for Data Persistence**: In local Docker setups, data persistence is achieved through volume mounts rather than storing data inside the container image.
- **Separation of Concerns**: Data generation (Worker) and Site Hosting (Pages) are decoupled into separate workflows, linked only by the commit of generated JSON files to the `docs/` directory.