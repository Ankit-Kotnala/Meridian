SHELL := /bin/sh

.PHONY: help setup dev stop format format-check lint typecheck test test-integration test-e2e build security-scan seed migrate reset-db compose-config verify

help:
	@echo "CareerOS development targets"
	@echo "  setup            Install pinned JavaScript and Python dependencies"
	@echo "  dev              Build and start the local Compose platform"
	@echo "  stop             Stop local services and preserve volumes"
	@echo "  format           Apply JavaScript and Python formatters"
	@echo "  format-check     Check formatting without changes"
	@echo "  lint             Run JavaScript and Python linters"
	@echo "  typecheck        Run strict TypeScript and Python checks"
	@echo "  test             Run unit tests"
	@echo "  test-integration Start the stack and verify service health"
	@echo "  test-e2e         Run browser end-to-end tests"
	@echo "  build            Build workspace packages and service images"
	@echo "  security-scan    Scan source, dependencies, and application images"
	@echo "  verify           Run the non-runtime Phase 0 quality and build gate"

setup:
	@test -f .env || cp .env.example .env
	corepack enable
	corepack prepare pnpm@11.13.0 --activate
	pnpm install --frozen-lockfile
	cd apps/api && uv sync --frozen --all-extras --dev
	cd apps/worker && uv sync --frozen --all-extras --dev

dev:
	docker compose up --build

stop:
	docker compose down --remove-orphans

format:
	pnpm format
	cd apps/api && uv run ruff format .
	cd apps/worker && uv run ruff format .

format-check:
	pnpm format:check
	cd apps/api && uv run ruff format --check .
	cd apps/worker && uv run ruff format --check .

lint:
	pnpm lint
	cd apps/api && uv run ruff check .
	cd apps/worker && uv run ruff check .

typecheck:
	pnpm typecheck
	cd apps/api && uv run mypy
	cd apps/worker && uv run mypy

test:
	pnpm test
	cd apps/api && uv run pytest
	cd apps/worker && uv run pytest

test-integration:
	docker compose up --build --detach --wait
	curl --fail --silent --show-error http://localhost:3000/api/health
	curl --fail --silent --show-error http://localhost:8000/health
	curl --fail --silent --show-error http://localhost:8000/ready
	curl --fail --silent --show-error http://localhost:8000/api/v1/meta

test-e2e:
	pnpm test:e2e

build:
	pnpm build
	docker compose build api worker web

security-scan:
	docker run --rm --volume "$(CURDIR):/repo:ro" ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f dir /repo --config /repo/.gitleaks.toml --redact --exit-code 1
	pnpm audit --audit-level high
	cd apps/api && uv run --with pip-audit pip-audit
	cd apps/worker && uv run --with pip-audit pip-audit
	docker compose build api worker web
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-api:latest --fail-on critical --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-worker:latest --fail-on critical --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-web:latest --fail-on critical --only-fixed

seed:
	pnpm seed

migrate:
	docker compose run --rm api uv run alembic upgrade head

reset-db:
	docker compose down --volumes --remove-orphans
	docker compose up -d postgres redis minio minio-init

compose-config:
	docker compose config --quiet

verify: format-check lint typecheck test build compose-config
