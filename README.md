# NEUXO Backend

Backend API for the NEUXO platform, built with Django, Django REST Framework, and Channels. This service powers the core API, background jobs (Celery), and realtime features.

## Requirements

- Python >= 3.11
- uv (dependency manager)
- just (task runner; uses Justfile)
- Redis (Channels + Celery broker/backing)
- MySQL (driver: mysqlclient)

## Quick Start

### Step-by-step

1) Clone the project

```bash
git clone <repo_url>
cd NEUXO-BACKEND
```

2) Check required tools

```bash
python --version
uv --version
just --version
```

If `just` is not installed, install it from https://github.com/casey/just or your package manager.

3) Install dependencies

```bash
just install
```

4) Activate venv

```bash
source .venv/bin/activate
```

## Run in Development

```bash
just dev
```

The app will be available at `http://0.0.0.0:8091`.

### Run Celery Worker

```bash
just run-celery
```

## Developer Commands

```bash
just format
just lint
just typecheck
```

## Environment Configuration

- Use a `.env` file for local environment variables (loaded by `just`).
- Configure MySQL, Redis, SMTP, and API keys as needed.

## Project Structure

- `neuxo/` Django app
- `neuxo/manage.py` management entrypoint (migrate, runserver, ...)
- `tests/` test suite

## API Docs

- OpenAPI/Swagger is provided via `drf-spectacular` (see project routes).

## Notes

- After changing dependencies, run `just upgrade` to refresh the lockfile.
- Ensure Redis and MySQL are running before starting the API or Celery.
