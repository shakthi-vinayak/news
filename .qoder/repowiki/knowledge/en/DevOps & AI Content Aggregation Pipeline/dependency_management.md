The repository uses a standard Python dependency management strategy centered around `pip` and a single `requirements.txt` file. There is no use of advanced dependency managers like Poetry, Pipenv, or Conda, nor are there any lockfiles (e.g., `requirements.lock`, `Pipfile.lock`) to pin transitive dependencies deterministically.

### Key Components
- **Manifest File**: `worker/requirements.txt` declares all direct third-party libraries with minimum version constraints (e.g., `requests>=2.31.0`).
- **Installation Contexts**:
  - **Local/Docker**: The `worker/Dockerfile` copies `requirements.txt` and runs `pip install --no-cache-dir -r requirements.txt` during the image build process.
  - **CI/CD**: The GitHub Actions workflow `.github/workflows/worker-schedule.yml` sets up Python 3.12 and installs dependencies using `pip install -r worker/requirements.txt`. It leverages GitHub Actions' built-in `cache: pip` feature, keyed on `worker/requirements.txt`, to speed up subsequent runs.

### Conventions & Rules
1. **Single Source of Truth**: All Python dependencies for the worker service are maintained in `worker/requirements.txt`. No other dependency manifests exist for the Python code.
2. **Versioning Strategy**: Dependencies use "greater than or equal to" (`>=`) version specifiers. This allows for automatic patch/minor updates but may introduce non-deterministic builds if upstream libraries release breaking changes within the allowed range. 
3. **No Vendoring**: Dependencies are fetched from PyPI at build/runtime; there is no vendor directory or offline package cache committed to the repo.
4. **Environment Isolation**: Dependencies are installed into the system Python environment within the Docker container or the GitHub Actions runner. No virtual environment (`venv`) management is explicitly scripted in the CI or Dockerfile, relying on the container's isolation instead.

### Recommendations for Developers
- When adding a new library, append it to `worker/requirements.txt` with a reasonable minimum version.
- Be aware that without a lockfile, builds may pull newer versions of dependencies over time. If reproducibility becomes critical, consider generating a `requirements.lock` file using `pip-tools` or switching to a manager like Poetry.