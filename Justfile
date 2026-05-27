set dotenv-load := true

# export COVERAGE_CORE := "sysmon"

export PYTHONDONTWRITEBYTECODE := "1"

# Show this help message and exit
default:
    @just --list --unsorted

# -------------------
# Manage dependencies
# -------------------

# Install dependencies and set up pre-commit hooks for local development
# [group('Manage dependencies')]
install:
    uv sync --all-packages
    uv run pre-commit install --install-hooks
    uv run pre-commit install --hook-type pre-push

# Upgrade all dependencies
# [group('Manage dependencies')]
upgrade:
    uv lock --upgrade
    uv run pre-commit autoupdate

# Dev environment
dev:
    uv run -- python neuxo/manage.py runserver 0.0.0.0:8091

# Run Celery worker for the Django app in neuxo
run-celery:
    cd neuxo && uv run celery -A neuxo worker -l info

# --------------------------
# Lint, format and run tests
# --------------------------

# Format Python source files
# [group('Lint, format and run tests')]
format:
    uv run ruff check --fix .
    uv run ruff format .

# Lint Python source files
# [group('Lint, format and run tests')]
lint:
    uv run ruff check .
    uv run ruff format --check .

# Perform type checking
# [group('Lint, format and run tests')]
typecheck:
    uv run mypy .

# --------
# Clean up
# --------

# Clear local caches and build artifacts
# [group('Clean up')]
clean:
    rm -rf dist
    rm -rf .cache
    rm -rf .hypothesis
    rm -rf `find . -name __pycache__`
    rm -f `find . -type f -name '*.py[co]'`
