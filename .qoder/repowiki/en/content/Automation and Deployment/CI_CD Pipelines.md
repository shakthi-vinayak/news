# CI/CD Pipelines

<cite>
**Referenced Files in This Document**
- [pages-deploy.yml](file://.github/workflows/pages-deploy.yml)
- [worker-schedule.yml](file://.github/workflows/worker-schedule.yml)
- [Dockerfile](file://worker/Dockerfile)
- [docker-compose.yml](file://docker-compose.yml)
- [requirements.txt](file://worker/requirements.txt)
- [config.yaml](file://worker/config.yaml)
- [main.py](file://worker/main.py)
- [export_json.py](file://worker/storage/export_json.py)
- [db.py](file://worker/storage/db.py)
- [smtp_alert.py](file://worker/notify/smtp_alert.py)
- [.dockerignore](file://worker/.dockerignore)
- [test_schema.py](file://tests/test_schema.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction
This document explains the end-to-end CI/CD automation for the project, covering GitHub Actions workflows, Docker-based builds, and deployment to GitHub Pages. It documents the pipeline that:
- Builds a Python worker container
- Runs scheduled data collection and enrichment
- Validates outputs with automated tests
- Commits updated JSON artifacts to the repository
- Triggers a Pages deployment to publish the static site

It also covers environment management, secrets, quality gates, deployment validation, rollback strategies, monitoring, and multi-stage deployment workflows.

## Project Structure
The repository is organized around two primary automation paths:
- GitHub Actions workflows for scheduling and publishing
- Docker-based containerization for repeatable builds and local/VM runs

```mermaid
graph TB
subgraph "GitHub Workflows"
A[".github/workflows/worker-schedule.yml"]
B[".github/workflows/pages-deploy.yml"]
end
subgraph "Worker Container"
C["worker/Dockerfile"]
D["worker/requirements.txt"]
E["worker/.dockerignore"]
end
subgraph "Runtime Orchestration"
F["docker-compose.yml"]
end
subgraph "Application"
G["worker/main.py"]
H["worker/config.yaml"]
I["worker/storage/db.py"]
J["worker/storage/export_json.py"]
K["worker/notify/smtp_alert.py"]
end
subgraph "Validation"
L["tests/test_schema.py"]
end
A --> C
C --> G
G --> I
G --> J
G --> K
A --> L
B --> J
F --> C
```

**Diagram sources**
- [pages-deploy.yml:1-42](file://.github/workflows/pages-deploy.yml#L1-L42)
- [worker-schedule.yml:1-70](file://.github/workflows/worker-schedule.yml#L1-L70)
- [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- [docker-compose.yml:1-47](file://docker-compose.yml#L1-L47)
- [requirements.txt:1-11](file://worker/requirements.txt#L1-L11)
- [.dockerignore:1-6](file://worker/.dockerignore#L1-L6)
- [main.py:1-297](file://worker/main.py#L1-L297)
- [config.yaml:1-244](file://worker/config.yaml#L1-L244)
- [db.py:1-278](file://worker/storage/db.py#L1-L278)
- [export_json.py:1-93](file://worker/storage/export_json.py#L1-L93)
- [smtp_alert.py:1-105](file://worker/notify/smtp_alert.py#L1-L105)
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)

**Section sources**
- [pages-deploy.yml:1-42](file://.github/workflows/pages-deploy.yml#L1-L42)
- [worker-schedule.yml:1-70](file://.github/workflows/worker-schedule.yml#L1-L70)
- [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- [docker-compose.yml:1-47](file://docker-compose.yml#L1-L47)
- [requirements.txt:1-11](file://worker/requirements.txt#L1-L11)
- [.dockerignore:1-6](file://worker/.dockerignore#L1-L6)
- [main.py:1-297](file://worker/main.py#L1-L297)
- [config.yaml:1-244](file://worker/config.yaml#L1-L244)
- [db.py:1-278](file://worker/storage/db.py#L1-L278)
- [export_json.py:1-93](file://worker/storage/export_json.py#L1-L93)
- [smtp_alert.py:1-105](file://worker/notify/smtp_alert.py#L1-L105)
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)

## Core Components
- GitHub Actions “Refresh Data” workflow: schedules periodic runs, installs Python dependencies, executes the worker, validates JSON outputs, and commits/pushes updates.
- GitHub Actions “Deploy to GitHub Pages” workflow: publishes the docs directory as a static site.
- Dockerized worker: reproducible build with a non-root user, layered dependency caching, and entrypoint for single-run execution.
- Compose orchestration: optional local/VM runtime with persistent DB and mounted data volume.
- Application pipeline: collects, deduplicates, scores, persists to SQLite, exports JSON, optionally emails a digest, and publishes via Git.

**Section sources**
- [worker-schedule.yml:1-70](file://.github/workflows/worker-schedule.yml#L1-L70)
- [pages-deploy.yml:1-42](file://.github/workflows/pages-deploy.yml#L1-L42)
- [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- [docker-compose.yml:1-47](file://docker-compose.yml#L1-L47)
- [main.py:1-297](file://worker/main.py#L1-L297)

## Architecture Overview
The CI/CD architecture comprises three stages:
1. Build and test: Python dependencies installed in a containerized environment; tests validate JSON schema.
2. Data pipeline: worker runs end-to-end ingestion, deduplication, scoring, persistence, and export.
3. Deployment: updated JSON artifacts trigger a Pages deployment.

```mermaid
sequenceDiagram
participant Cron as "Scheduler"
participant GA as "GitHub Actions Worker Workflow"
participant Py as "Python Runtime"
participant DB as "SQLite DB"
participant EXP as "JSON Export"
participant GIT as "Git Push"
participant PAGES as "GitHub Pages"
Cron->>GA : "Trigger on schedule"
GA->>Py : "Install deps and run worker"
Py->>DB : "Collect, dedupe, score, persist"
Py->>EXP : "Export news.json, jobs.json, meta.json"
EXP-->>Py : "Files written"
Py->>GIT : "Commit and push docs/data/*"
GIT-->>PAGES : "Push triggers Pages deployment"
PAGES-->>GA : "Deployment URL available"
```

**Diagram sources**
- [worker-schedule.yml:13-70](file://.github/workflows/worker-schedule.yml#L13-L70)
- [main.py:127-297](file://worker/main.py#L127-L297)
- [db.py:116-242](file://worker/storage/db.py#L116-L242)
- [export_json.py:32-93](file://worker/storage/export_json.py#L32-L93)
- [pages-deploy.yml:20-42](file://.github/workflows/pages-deploy.yml#L20-L42)

## Detailed Component Analysis

### GitHub Actions “Refresh Data” Workflow
- Schedules runs every 2 hours and supports manual dispatch.
- Checks out the repository, sets up Python 3.12 with pip cache, installs dependencies from requirements.txt, and runs the worker.
- Environment variables are supplied from GitHub Secrets and Variables.
- Validates exported JSON with pytest; if successful, commits and pushes docs/data/*.json.
- Uses GITHUB_TOKEN with write permissions to push.

```mermaid
flowchart TD
Start(["Workflow Trigger"]) --> Checkout["Checkout Repository"]
Checkout --> SetupPy["Setup Python 3.12<br/>Enable pip cache"]
SetupPy --> InstallDeps["pip install -r worker/requirements.txt"]
InstallDeps --> RunWorker["Run worker/main.py"]
RunWorker --> Validate["pytest tests/test_schema.py"]
Validate --> |Pass| Commit["git add/commit/push docs/data/*"]
Validate --> |Fail| FailFast["Fail workflow"]
Commit --> End(["Done"])
FailFast --> End
```

**Diagram sources**
- [worker-schedule.yml:13-70](file://.github/workflows/worker-schedule.yml#L13-L70)
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)

**Section sources**
- [worker-schedule.yml:1-70](file://.github/workflows/worker-schedule.yml#L1-L70)
- [requirements.txt:1-11](file://worker/requirements.txt#L1-L11)
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)

### GitHub Actions “Deploy to GitHub Pages” Workflow
- Deploys the docs directory as a static site on pushes to main that touch docs/**.
- Supports manual dispatch.
- Configures Pages, uploads the docs artifact, and deploys to GitHub Pages.

```mermaid
sequenceDiagram
participant Repo as "Repository"
participant GA as "Pages Workflow"
participant GH as "GitHub Pages"
Repo->>GA : "Push to main/docs/**"
GA->>GA : "Checkout and configure Pages"
GA->>GH : "Upload docs artifact"
GH-->>GA : "Deployment URL"
GA-->>Repo : "Environment URL set"
```

**Diagram sources**
- [pages-deploy.yml:1-42](file://.github/workflows/pages-deploy.yml#L1-L42)

**Section sources**
- [pages-deploy.yml:1-42](file://.github/workflows/pages-deploy.yml#L1-L42)

### Dockerized Worker Build
- Multi-stage base image using python:3.12-slim.
- Creates a non-root worker user and ensures /app/db ownership.
- Copies requirements.txt first for layer caching, then source.
- Sets ENTRYPOINT to run main.py on container start.
- .dockerignore excludes development artifacts and DB directory.

```mermaid
flowchart TD
Base["Base Image: python:3.12-slim"] --> AddReq["Copy requirements.txt"]
AddReq --> Pip["pip install deps"]
Pip --> CopySrc["Copy source code"]
CopySrc --> DBDir["Ensure /app/db owned by worker"]
DBDir --> Entrypoint["ENTRYPOINT python main.py"]
```

**Diagram sources**
- [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- [.dockerignore:1-6](file://worker/.dockerignore#L1-L6)

**Section sources**
- [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- [.dockerignore:1-6](file://worker/.dockerignore#L1-L6)

### Local/VM Runtime with Docker Compose
- Builds the worker image from worker/Dockerfile.
- Mounts ./docs/data into the container to write JSON directly into the repo.
- Persists SQLite DB under ./worker/db.
- Optional preview service using nginx to serve docs/.
- Environment loaded from .env via env_file.

```mermaid
graph TB
subgraph "Compose Services"
W["worker:<br/>restart=no,<br/>env_file .env,<br/>mounts docs/data and db"]
P["preview:<br/>nginx:alpine,<br/>ports 8080:80,<br/>volume docs"]
end
W --> |"Exports JSON"| Docs["docs/data/*.json"]
P --> |"Serves"| Docs
```

**Diagram sources**
- [docker-compose.yml:13-47](file://docker-compose.yml#L13-L47)

**Section sources**
- [docker-compose.yml:1-47](file://docker-compose.yml#L1-L47)

### Worker Pipeline Execution
The worker orchestrates the full pipeline:
- Loads configuration from config.yaml
- Initializes SQLite DB and starts a run log
- Collects news and jobs from enabled sources
- Deduplicates and filters items
- Scores items via LLM (OpenRouter) in batches
- Upserts items into SQLite
- Exports static JSON files to docs/data/
- Writes run metadata and optionally sends SMTP digest
- Commits and pushes changes unless DRY_RUN=true

```mermaid
flowchart TD
Start(["run()"]) --> LoadCfg["Load config.yaml"]
LoadCfg --> InitDB["Init SQLite DB"]
InitDB --> StartRun["Log run start"]
StartRun --> CollectNews["Collect news from enabled sources"]
CollectNews --> DedupNews["Deduplicate + keyword filter"]
DedupNews --> ScoreNews["Batch score via LLM"]
ScoreNews --> PersistNews["Upsert news to DB"]
PersistNews --> CollectJobs["Collect jobs from enabled sources"]
CollectJobs --> DedupJobs["Deduplicate"]
DedupJobs --> ScoreJobs["Batch score via LLM"]
ScoreJobs --> PersistJobs["Upsert jobs to DB"]
PersistJobs --> Export["Export JSON to docs/data/"]
Export --> FinishRun["Write run metadata"]
FinishRun --> Publish{"DRY_RUN?"}
Publish --> |No| GitPush["Commit + push docs/data/*"]
Publish --> |Yes| Skip["Skip publish"]
GitPush --> End(["Done"])
Skip --> End
```

**Diagram sources**
- [main.py:127-297](file://worker/main.py#L127-L297)
- [config.yaml:1-244](file://worker/config.yaml#L1-L244)
- [db.py:116-278](file://worker/storage/db.py#L116-L278)
- [export_json.py:32-93](file://worker/storage/export_json.py#L32-L93)

**Section sources**
- [main.py:1-297](file://worker/main.py#L1-L297)
- [config.yaml:1-244](file://worker/config.yaml#L1-L244)
- [db.py:1-278](file://worker/storage/db.py#L1-L278)
- [export_json.py:1-93](file://worker/storage/export_json.py#L1-L93)

### Quality Gates and Validation
- Automated schema validation of docs/data/*.json using pytest.
- Tests enforce presence of required keys, types, and value ranges for news and jobs items.
- The workflow fails fast on validation failure to prevent publishing invalid data.

```mermaid
flowchart TD
Collect["Worker exports JSON"] --> Test["pytest tests/test_schema.py"]
Test --> |Pass| Proceed["Proceed to commit/push"]
Test --> |Fail| Abort["Abort workflow"]
```

**Diagram sources**
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)
- [worker-schedule.yml:59-61](file://.github/workflows/worker-schedule.yml#L59-L61)

**Section sources**
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)
- [worker-schedule.yml:59-61](file://.github/workflows/worker-schedule.yml#L59-L61)

### Secrets Management and Environment Configuration
- GitHub Actions secrets and variables supply API keys and SMTP credentials.
- Worker loads environment from .env files via python-dotenv.
- SMTP digest is conditionally enabled and requires complete credential configuration.

Practical guidance:
- Store secrets in GitHub Actions Settings > Secrets and variables.
- Provide .env locally for docker-compose runs.
- Keep sensitive values out of the repository.

**Section sources**
- [worker-schedule.yml:44-56](file://.github/workflows/worker-schedule.yml#L44-L56)
- [main.py:23-25](file://worker/main.py#L23-L25)
- [smtp_alert.py:64-105](file://worker/notify/smtp_alert.py#L64-L105)

### Release Strategies and Deployment Validation
- The worker commits and pushes updated JSON files; subsequent push to main triggers the Pages workflow.
- Pages workflow publishes docs to GitHub Pages and exposes the URL in the environment.
- Validation occurs before pushing to ensure only valid JSON reaches the Pages site.

**Section sources**
- [worker-schedule.yml:63-70](file://.github/workflows/worker-schedule.yml#L63-L70)
- [pages-deploy.yml:20-42](file://.github/workflows/pages-deploy.yml#L20-L42)

### Rollback Procedures
- Since the worker pushes directly to main, a simple revert or cherry-pick can roll back problematic commits.
- Alternatively, tag releases and switch Pages to a previous commit SHA for rollback.

[No sources needed since this section provides general guidance]

### Monitoring Deployment Health
- Monitor GitHub Actions logs for the worker and Pages workflows.
- Verify GitHub Pages deployment status and URL availability.
- Optionally add health checks or alerts on the published site.

[No sources needed since this section provides general guidance]

### Maintaining Pipeline Reliability
- Pin Python version and cache pip dependencies.
- Use non-root containers and deterministic layering.
- Keep validation strict and fail-fast.
- Prefer idempotent operations (dedupe, upsert) to avoid duplication.

**Section sources**
- [worker-schedule.yml:34-42](file://.github/workflows/worker-schedule.yml#L34-L42)
- [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- [main.py:174-181](file://worker/main.py#L174-L181)

## Dependency Analysis
The worker depends on a small set of libraries for HTTP, parsing, YAML, environment loading, and Git operations. These are declared in requirements.txt and installed during the workflow or build process.

```mermaid
graph LR
R["requirements.txt"] --> P["Python Packages"]
P --> M["worker/main.py"]
M --> D["worker/storage/db.py"]
M --> E["worker/storage/export_json.py"]
M --> N["worker/notify/smtp_alert.py"]
```

**Diagram sources**
- [requirements.txt:1-11](file://worker/requirements.txt#L1-L11)
- [main.py:1-297](file://worker/main.py#L1-L297)
- [db.py:1-278](file://worker/storage/db.py#L1-L278)
- [export_json.py:1-93](file://worker/storage/export_json.py#L1-L93)
- [smtp_alert.py:1-105](file://worker/notify/smtp_alert.py#L1-L105)

**Section sources**
- [requirements.txt:1-11](file://worker/requirements.txt#L1-L11)
- [main.py:1-297](file://worker/main.py#L1-L297)
- [db.py:1-278](file://worker/storage/db.py#L1-L278)
- [export_json.py:1-93](file://worker/storage/export_json.py#L1-L93)
- [smtp_alert.py:1-105](file://worker/notify/smtp_alert.py#L1-L105)

## Performance Considerations
- Layered Docker build: copy requirements.txt before source to maximize cache hits.
- Batched LLM scoring reduces API calls while controlling cost and latency.
- Deduplication and keyword filtering reduce unnecessary LLM usage.
- SQLite WAL mode and indexes improve read/write performance.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Validation failures: Ensure docs/data/*.json matches the schema enforced by tests.
- Missing secrets: Confirm GitHub Secrets and Variables are set for the worker workflow.
- SMTP digest not sent: Verify SMTP credentials and that SMTP_ENABLED is true.
- Pages not updating: Check Pages workflow logs and confirm the push occurred after data refresh.
- Permission denied in container: Confirm non-root user and proper ownership of /app/db.

**Section sources**
- [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)
- [worker-schedule.yml:44-56](file://.github/workflows/worker-schedule.yml#L44-L56)
- [smtp_alert.py:64-105](file://worker/notify/smtp_alert.py#L64-L105)
- [pages-deploy.yml:20-42](file://.github/workflows/pages-deploy.yml#L20-L42)
- [Dockerfile:16-18](file://worker/Dockerfile#L16-L18)

## Conclusion
The CI/CD pipeline automates reliable data refresh and static site publishing. By combining scheduled GitHub Actions, a reproducible Docker build, strict validation, and a clear deployment flow, the system maintains data quality and site availability. Extending the pipeline with additional environments, richer monitoring, and automated rollback safeguards is straightforward given the current modular design.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Practical Examples and Reference Paths
- Worker workflow configuration: [worker-schedule.yml:1-70](file://.github/workflows/worker-schedule.yml#L1-L70)
- Pages deployment workflow: [pages-deploy.yml:1-42](file://.github/workflows/pages-deploy.yml#L1-L42)
- Container build definition: [Dockerfile:1-24](file://worker/Dockerfile#L1-L24)
- Local runtime with compose: [docker-compose.yml:1-47](file://docker-compose.yml#L1-L47)
- Dependencies list: [requirements.txt:1-11](file://worker/requirements.txt#L1-L11)
- Application entrypoint: [main.py:1-297](file://worker/main.py#L1-L297)
- Data export logic: [export_json.py:1-93](file://worker/storage/export_json.py#L1-L93)
- Database schema and helpers: [db.py:1-278](file://worker/storage/db.py#L1-L278)
- SMTP digest: [smtp_alert.py:1-105](file://worker/notify/smtp_alert.py#L1-L105)
- JSON schema validation: [test_schema.py:1-136](file://tests/test_schema.py#L1-L136)