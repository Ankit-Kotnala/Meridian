SHELL := /bin/sh

COMPOSE := docker compose -f infra/compose.yaml --project-directory .

.PHONY: help setup dev dev-web dev-api dev-worker local-up local-backend local-deps local-rebuild local-rebuild-web local-rebuild-backend local-status local-logs local-smoke local-down stop format format-check lint typecheck test test-web test-api test-worker test-backend contracts-check test-integration test-e2e test-e2e-stack-phase1 test-e2e-stack test-e2e-stack-phase3 test-e2e-stack-phase4 test-e2e-stack-phase5 test-e2e-stack-phase6 test-e2e-stack-phase7 test-e2e-stack-phase8 test-e2e-stack-phase9 build security-scan seed migrate sync-job-catalog seed-role-roadmaps reset-db compose-config verify verify-phase1 verify-phase2 verify-phase3 verify-phase4 verify-phase5 verify-phase6 verify-phase7 verify-phase8 verify-phase9

help:
	@echo "Rezumi development targets"
	@echo "  setup            Install pinned JavaScript and Python dependencies"
	@echo "  dev              Build and start the attached local Compose platform"
	@echo "  dev-web          Run the web with hot reload against backend containers"
	@echo "  dev-api          Run the API with hot reload against dependency containers"
	@echo "  dev-worker       Run a local worker against dependency containers"
	@echo "  local-up         Build and start the full stack detached"
	@echo "  local-backend    Build and start backend services detached"
	@echo "  local-deps       Start PostgreSQL, Redis, MinIO, Mailpit, and ClamAV"
	@echo "  local-rebuild-web Rebuild only web and web-edge"
	@echo "  local-rebuild-backend Rebuild API, worker, and scheduler"
	@echo "  local-status     Show local Compose service state"
	@echo "  local-logs       Follow local Compose logs"
	@echo "  local-smoke      Probe the full running local stack"
	@echo "  local-down       Stop local services and preserve volumes"
	@echo "  stop             Alias for local-down"
	@echo "  format           Apply JavaScript and Python formatters"
	@echo "  format-check     Check formatting without changes"
	@echo "  lint             Run JavaScript and Python linters"
	@echo "  typecheck        Run strict TypeScript and Python checks"
	@echo "  test             Run unit tests"
	@echo "  test-integration Start the stack and verify service health"
	@echo "  test-e2e         Run browser end-to-end tests"
	@echo "  test-e2e-stack-phase1 Run the isolated Phase 1 authentication/onboarding journey"
	@echo "  test-e2e-stack   Run the isolated Phase 2 authentication and Resume Health journeys"
	@echo "  test-e2e-stack-phase3 Run the isolated Phase 3 Career Record journey suite"
	@echo "  test-e2e-stack-phase4 Run the isolated Phase 4 Role Explorer journey suite"
	@echo "  test-e2e-stack-phase5 Run the isolated Phase 5 Job Match journey suite"
	@echo "  test-e2e-stack-phase6 Run the isolated Phase 6 Change Studio journey suite"
	@echo "  test-e2e-stack-phase7 Run the isolated Phase 7 Resume Builder journey suite"
	@echo "  test-e2e-stack-phase8 Run the isolated Phase 8 Application Workspace journey suite"
	@echo "  test-e2e-stack-phase9 Run the isolated Phase 9 career workspace journey suite"
	@echo "  build            Build workspace packages and service images"
	@echo "  security-scan    Scan source, dependencies, and application images"
	@echo "  contracts-check  Verify OpenAPI and generated TypeScript contract drift"
	@echo "  verify           Run the Phase 0 quality, contract, build, and runtime gate"
	@echo "  verify-phase1    Run the platform gate and isolated Phase 1 browser journey"
	@echo "  verify-phase2    Run all platform gates and the isolated Resume Health journey"
	@echo "  verify-phase3    Run all platform gates and the isolated Career Record journey"
	@echo "  verify-phase4    Run all platform gates and the isolated Role Explorer journey"
	@echo "  verify-phase5    Run all platform gates and the isolated Job Match journey"
	@echo "  verify-phase6    Run all platform gates and the isolated Change Studio journey"
	@echo "  verify-phase7    Run all platform gates and the isolated Resume Builder journey"
	@echo "  verify-phase8    Run all platform gates and the isolated Application Workspace journey"
	@echo "  verify-phase9    Run all platform gates and the isolated Phase 9 career workspace journey"
	@echo "  seed             Migrate and idempotently seed fictional local Phase 1-9 data"

setup:
	@test -f .env || cp .env.example .env
	corepack enable
	corepack prepare npm@11.8.0 --activate
	npm ci
	uv sync --project backend --frozen --all-packages --all-groups

dev:
	$(COMPOSE) up --build

dev-web:
	node scripts/local.mjs dev-web

dev-api:
	node scripts/local.mjs dev-api

dev-worker:
	node scripts/local.mjs dev-worker

local-up:
	node scripts/local.mjs up full

local-backend:
	node scripts/local.mjs up backend

local-deps:
	node scripts/local.mjs up dependencies

local-rebuild:
	node scripts/local.mjs rebuild all

local-rebuild-web:
	node scripts/local.mjs rebuild web

local-rebuild-backend:
	node scripts/local.mjs rebuild backend

local-status:
	node scripts/local.mjs status

local-logs:
	node scripts/local.mjs logs

local-smoke:
	node scripts/local.mjs smoke full

local-down:
	node scripts/local.mjs down

stop: local-down

format:
	npm run format
	cd backend/core && uv run --package rezumi-backend ruff format .
	cd backend/api && uv run ruff format .
	cd backend/worker && uv run ruff format .
	uv run --project backend --package rezumi-api ruff format --config backend/api/pyproject.toml shared/contracts/scripts/export_openapi.py

format-check:
	npm run format:check
	cd backend/core && uv run --package rezumi-backend ruff format --check .
	cd backend/api && uv run ruff format --check .
	cd backend/worker && uv run ruff format --check .
	uv run --project backend --package rezumi-api ruff format --config backend/api/pyproject.toml --check shared/contracts/scripts/export_openapi.py

lint:
	npm run lint
	cd backend/core && uv run --package rezumi-backend ruff check .
	cd backend/api && uv run ruff check .
	cd backend/worker && uv run ruff check .
	uv run --project backend --package rezumi-api ruff check --config backend/api/pyproject.toml shared/contracts/scripts/export_openapi.py

typecheck:
	npm run typecheck
	cd backend/core && uv run --package rezumi-backend mypy
	cd backend/api && uv run mypy
	cd backend/worker && uv run mypy

test:
	npm run test
	cd backend/core && uv run --package rezumi-backend pytest tests/architecture tests/unit
	cd backend/api && uv run pytest
	cd backend/worker && uv run pytest

test-web:
	npm run test:web

test-api:
	npm run test:api

test-worker:
	npm run test:worker

test-backend:
	npm run test:backend

contracts-check:
	uv lock --project backend --check
	npm run contracts:check

test-integration:
	$(COMPOSE) up --build --detach --wait --wait-timeout 300
	$(COMPOSE) run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
	$(COMPOSE) run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
	$(COMPOSE) run --rm --no-deps api alembic -c backend/core/alembic.ini current
	curl --fail --silent --show-error http://localhost:3000/api/health
	curl --fail --silent --show-error http://localhost:8000/health
	curl --fail --silent --show-error http://localhost:8000/ready
	curl --fail --silent --show-error http://localhost:8000/api/v1/meta
	curl --fail --silent --show-error http://localhost:8025/api/v1/info
	$(COMPOSE) exec -T worker celery --app rezumi_worker.app:celery_app inspect ping --timeout 5

test-e2e:
	npm run test:e2e

test-e2e-stack-phase1:
	REZUMI_E2E_PHASE=1 sh tests/e2e/run-compose.sh

test-e2e-stack:
	REZUMI_E2E_PHASE=2 sh tests/e2e/run-compose.sh

test-e2e-stack-phase3:
	REZUMI_E2E_PHASE=3 sh tests/e2e/run-compose.sh

test-e2e-stack-phase4:
	REZUMI_E2E_PHASE=4 sh tests/e2e/run-compose.sh

test-e2e-stack-phase5:
	REZUMI_E2E_PHASE=5 sh tests/e2e/run-compose.sh

test-e2e-stack-phase6:
	REZUMI_E2E_PHASE=6 sh tests/e2e/run-compose.sh

test-e2e-stack-phase7:
	REZUMI_E2E_PHASE=7 sh tests/e2e/run-compose.sh

test-e2e-stack-phase8:
	REZUMI_E2E_PHASE=8 sh tests/e2e/run-compose.sh

test-e2e-stack-phase9:
	REZUMI_E2E_PHASE=9 sh tests/e2e/run-compose.sh

build:
	npm run build
	$(COMPOSE) build api worker web web-edge

security-scan:
	docker run --rm --volume "$(CURDIR):/repo:ro" ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f dir /repo --config /repo/.gitleaks.toml --redact --exit-code 1
	npm audit --audit-level=high
	uv sync --project backend --frozen --all-packages --all-groups
	uv run --project backend --package rezumi-api --with pip-audit==2.9.0 pip-audit
	$(COMPOSE) build api worker web web-edge
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume rezumi-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d rezumi-api:latest --config /etc/grype.yaml --fail-on high --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume rezumi-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d rezumi-worker:latest --config /etc/grype.yaml --fail-on high --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume rezumi-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d rezumi-web:latest --config /etc/grype.yaml --fail-on high --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume rezumi-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d rezumi-web-edge:latest --config /etc/grype.yaml --fail-on high --only-fixed

seed:
	$(COMPOSE) up --detach --wait postgres minio minio-init
	$(COMPOSE) build api
	$(COMPOSE) run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
	REZUMI_ALLOW_LOCAL_SEED=fictional-rezumi-local-seed-v1 $(COMPOSE) --profile tools run --rm --no-deps local-seed

migrate:
	$(COMPOSE) run --rm api alembic -c backend/core/alembic.ini upgrade head

sync-job-catalog:
	$(COMPOSE) exec worker python3 -m rezumi_worker.scripts.sync_job_catalog_once

seed-role-roadmaps:
	$(COMPOSE) exec worker python3 -m rezumi.development.seed_role_roadmaps

reset-db:
	$(COMPOSE) down --volumes --remove-orphans
	$(COMPOSE) up -d postgres redis minio minio-init

compose-config:
	$(COMPOSE) config --quiet

verify: contracts-check format-check lint typecheck test build compose-config test-integration

verify-phase1: verify test-e2e-stack-phase1

verify-phase2: verify test-e2e-stack

verify-phase3: verify test-e2e-stack-phase3

verify-phase4: verify test-e2e-stack-phase4

verify-phase5: verify test-e2e-stack-phase5

verify-phase6: verify test-e2e-stack-phase6

verify-phase7: verify test-e2e-stack-phase7

verify-phase8: verify test-e2e-stack-phase8

verify-phase9: verify test-e2e-stack-phase9
