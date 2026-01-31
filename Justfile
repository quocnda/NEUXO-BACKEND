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
[group('Manage dependencies')]
install:
    uv sync --all-packages
    prek install --install-hooks

# Upgrade all dependencies
[group('Manage dependencies')]
upgrade:
    uv lock --upgrade
    prek auto-update

# ---------------------
# Run Harmonic services
# ---------------------

# Run Harmonic API
# [group('Run Harmonic services')]
# dev-api:
#     uv run fastapi dev ./harmonic-api/src/harmonic_api/api/main.py


# --------------------------
# Lint, format and run tests
# --------------------------

# Format Python source files
[group('Lint, format and run tests')]
format:
    uv run ruff check --fix .
    uv run ruff format .

# Lint Python source files
[group('Lint, format and run tests')]
lint:
    uv run ruff check .
    uv run ruff format --check .

# Perform type checking
[group('Lint, format and run tests')]
typecheck:
    uv run mypy .

# Run unit tests
[group('Lint, format and run tests')]
test:
    uv run pytest

# Run the standard set of checks (format, lint, and unit tests)
[group('Lint, format and run tests')]
all: lint typecheck test

# ------------------
# Run advanced tests
# ------------------

# Run slow tests
[group('Run advanced tests')]
test-slow:
    uv run pytest -m "slow"

# Run benchmarks
[group('Run advanced tests')]
test-benchmark:
    uv run pytest --benchmark-only

# ----------------------
# Manage docker services
# ----------------------

# Start docker services
[group('Manage docker services')]
[working-directory('docker')]
up *SERVICES:
    docker compose --file compose.yaml --env-file .env.dev up --remove-orphans {{ SERVICES }}

# Stop all docker services
[group('Manage docker services')]
[working-directory('docker')]
down:
    docker compose --file compose.yaml --env-file .env.dev down --remove-orphans

# Wrapper to interact with docker compose
[group('Manage docker services')]
[working-directory('docker')]
docker *FLAGS:
    docker compose --file compose.yaml --env-file .env.dev {{ FLAGS }}

# -----------
# Deployments
# -----------

# Build docker images
[group('Deployments')]
build FILE:
    #!/usr/bin/sh
    image_name="harmonic-ai-v2:latest"
    echo "Building ${image_name}..."
    echo
    docker build --no-cache --tag ${image_name} --file docker/{{ FILE }}.Dockerfile .

# --------
# Clean up
# --------

# Clear local caches and build artifacts
[group('Clean up')]
clean:
    rm -rf dist
    rm -rf .cache
    rm -rf .hypothesis
    rm -rf `find . -name __pycache__`
    rm -f `find . -type f -name '*.py[co]'`
