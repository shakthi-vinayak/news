The application employs a **two-layer configuration system** that strictly separates static application settings from runtime secrets and environment-specific toggles, adhering to the [12-factor app](https://12factor.net/config) methodology.

### 1. System Approach
- **Layer 1 (Static Settings):** Managed via `worker/config.yaml`. This file contains structural and behavioral configurations such as enabled data sources, keyword filters, LLM model parameters, and data retention policies. It is version-controlled and safe to commit.
- **Layer 2 (Secrets & Runtime Toggles):** Managed via environment variables. Secrets (API keys, tokens) and runtime flags (log levels, dry-run modes) are loaded using `python-dotenv` from a `.env` file (local development) or injected directly by the CI/CD pipeline and Docker Compose.

### 2. Key Files and Packages
- **`worker/config.yaml`**: The central manifest for application behavior. It defines all news and job sources, their specific parameters (e.g., tags, max items), and global filters.
- **`.env.example`**: A template file tracking required environment variables with placeholder values. Developers copy this to `.env` for local setup.
- **`worker/main.py`**: The orchestration entry point. It loads `config.yaml` using `yaml.safe_load()` and initializes environment variables via `load_dotenv()`, supporting both repo-root and worker-directory execution contexts.
- **`docker-compose.yml`**: Uses the `env_file` directive to inject `.env` variables into the worker container, ensuring consistent configuration across local and containerized environments.

### 3. Architecture and Conventions
- **Dual-Path Loading:** The application attempts to load `.env` from both the `worker/` directory and the repository root, providing flexibility for different execution contexts.
- **Module-Level vs. Function-Level Reads:** 
  - Critical secrets like `OPENROUTER_API_KEY` are often read at module import time (e.g., in `scoring/llm_relevance.py`), freezing their values for the process lifetime.
  - Optional features (like SMTP notifications) read variables inside functions using `os.getenv()`, allowing for more dynamic checks.
- **Graceful Degradation:** The system validates required secrets at startup (`_check_secrets()`) and fails fast if they are missing, preventing silent failures during data collection.
- **Source Management:** All data collectors (news and jobs) are toggled via `enabled: true/false` flags in `config.yaml`, allowing operators to adjust the pipeline scope without code changes.

### 4. Rules for Developers
- **Never Commit Secrets:** The `.env` file is gitignored. Only `.env.example` should be tracked. Real credentials must never appear in `config.yaml` or source code.
- **Settings vs. Secrets:** Add new behavioral parameters (e.g., batch sizes, new source URLs) to `config.yaml`. Add new credentials (API keys, passwords) to `.env.example` and access them via `os.getenv()`.
- **Use Defaults:** Always provide sensible defaults in `os.getenv(key, default)` to prevent crashes when optional variables are unset.
- **Dry Run for Testing:** Use the `DRY_RUN=true` environment variable to test collection and scoring logic without triggering git pushes or external notifications.
- **Keyword Filtering:** Maintain the `keyword_filter` list in `config.yaml` to pre-filter items before LLM scoring, optimizing API costs and relevance.