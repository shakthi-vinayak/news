This repository uses a standard Python dependency management approach centered around `requirements.txt` and `pip`. Dependencies are declared in `worker/requirements.txt` with minimum version constraints (e.g., `requests>=2.31.0`). 

### Key Components
- **Manifest**: `worker/requirements.txt` lists all third-party libraries required by the worker application.
- **Installation**: Dependencies are installed via `pip install -r requirements.txt` in both local Docker builds and GitHub Actions CI workflows.
- **Caching**: GitHub Actions utilizes `actions/setup-python` with `cache: pip` and `cache-dependency-path: worker/requirements.txt` to speed up dependency installation.

### Conventions
- **Versioning**: Uses `>=` for version constraints, allowing minor/patch updates while ensuring a minimum baseline.
- **No Lockfile**: There is no `requirements.lock` or `poetry.lock`, meaning builds are not strictly reproducible at the patch level unless cached layers are preserved.
- **Containerization**: The `worker/Dockerfile` copies `requirements.txt` first to leverage Docker layer caching for dependency installation.

### Developer Guidelines
- Add new dependencies to `worker/requirements.txt` with a minimum version.
- Do not commit virtual environment files or local cache directories.
- Rely on GitHub Actions caching for faster CI runs; local builds should use Docker to ensure consistency.