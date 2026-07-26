SHELL := /bin/sh

.PHONY: help setup dev stop format format-check lint typecheck test contracts-check test-integration test-e2e test-e2e-stack-phase1 test-e2e-stack test-e2e-stack-phase3 test-e2e-stack-phase4 test-e2e-stack-phase5 test-e2e-stack-phase6 test-e2e-stack-phase7 test-e2e-stack-phase8 test-e2e-stack-phase9 build security-scan seed migrate reset-db compose-config verify verify-phase1 verify-phase2 verify-phase3 verify-phase4 verify-phase5 verify-phase6 verify-phase7 verify-phase8 verify-phase9

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
	corepack prepare pnpm@11.13.0 --activate
	pnpm install --frozen-lockfile
	uv sync --frozen --all-packages --all-groups

dev:
	docker compose up --build

stop:
	docker compose down --remove-orphans

format:
	pnpm format
	cd packages/backend && uv run --package careeros-backend ruff format .
	cd apps/api && uv run ruff format .
	cd apps/worker && uv run ruff format .
	uv run --package careeros-api ruff format --config apps/api/pyproject.toml packages/contracts/scripts/export_openapi.py

format-check:
	pnpm format:check
	cd packages/backend && uv run --package careeros-backend ruff format --check .
	cd apps/api && uv run ruff format --check .
	cd apps/worker && uv run ruff format --check .
	uv run --package careeros-api ruff format --config apps/api/pyproject.toml --check packages/contracts/scripts/export_openapi.py

lint:
	pnpm lint
	cd packages/backend && uv run --package careeros-backend ruff check .
	cd apps/api && uv run ruff check .
	cd apps/worker && uv run ruff check .
	uv run --package careeros-api ruff check --config apps/api/pyproject.toml packages/contracts/scripts/export_openapi.py

typecheck:
	pnpm typecheck
	cd packages/backend && uv run --package careeros-backend mypy
	cd apps/api && uv run mypy
	cd apps/worker && uv run mypy

test:
	pnpm test
	cd packages/backend && uv run --package careeros-backend pytest tests/architecture tests/unit
	cd apps/api && uv run pytest
	cd apps/worker && uv run pytest

contracts-check:
	uv lock --check
	pnpm contracts:check

test-integration:
	docker compose up --build --detach --wait --wait-timeout 300
	docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
	docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
	docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini current
	curl --fail --silent --show-error http://localhost:3000/api/health
	curl --fail --silent --show-error http://localhost:8000/health
	curl --fail --silent --show-error http://localhost:8000/ready
	curl --fail --silent --show-error http://localhost:8000/api/v1/meta
	curl --fail --silent --show-error http://localhost:8025/api/v1/info
	docker compose exec -T worker celery --app careeros_worker.app:celery_app inspect ping --timeout 5

test-e2e:
	pnpm test:e2e

test-e2e-stack-phase1:
	CAREEROS_E2E_PHASE=1 sh tests/e2e/run-compose.sh

test-e2e-stack:
	CAREEROS_E2E_PHASE=2 sh tests/e2e/run-compose.sh

test-e2e-stack-phase3:
	CAREEROS_E2E_PHASE=3 sh tests/e2e/run-compose.sh

test-e2e-stack-phase4:
	CAREEROS_E2E_PHASE=4 sh tests/e2e/run-compose.sh

test-e2e-stack-phase5:
	CAREEROS_E2E_PHASE=5 sh tests/e2e/run-compose.sh

test-e2e-stack-phase6:
	CAREEROS_E2E_PHASE=6 sh tests/e2e/run-compose.sh

test-e2e-stack-phase7:
	CAREEROS_E2E_PHASE=7 sh tests/e2e/run-compose.sh

test-e2e-stack-phase8:
	CAREEROS_E2E_PHASE=8 sh tests/e2e/run-compose.sh

test-e2e-stack-phase9:
	CAREEROS_E2E_PHASE=9 sh tests/e2e/run-compose.sh

build:
	pnpm build
	docker compose build api worker web web-edge

security-scan:
	docker run --rm --volume "$(CURDIR):/repo:ro" ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f dir /repo --config /repo/.gitleaks.toml --redact --exit-code 1
	pnpm audit --audit-level high
	uv sync --frozen --all-packages --all-groups
	uv run --package careeros-api --with pip-audit==2.10.1 pip-audit
	docker compose build api worker web web-edge
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume careeros-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-api:latest --config /etc/grype.yaml --fail-on high --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume careeros-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-worker:latest --config /etc/grype.yaml --fail-on high --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume careeros-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-web:latest --config /etc/grype.yaml --fail-on high --only-fixed
	docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock --volume "$(CURDIR)/.grype.yaml:/etc/grype.yaml:ro" --volume careeros-grype-cache:/root/.cache/grype anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d careeros-web-edge:latest --config /etc/grype.yaml --fail-on high --only-fixed

seed:
	docker compose up --detach --wait postgres minio minio-init
	docker compose build api
	docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
	CAREEROS_ALLOW_LOCAL_SEED=fictional-careeros-local-seed-v1 docker compose --profile tools run --rm --no-deps local-seed

migrate:
	docker compose run --rm api alembic -c packages/backend/alembic.ini upgrade head

reset-db:
	docker compose down --volumes --remove-orphans
	docker compose up -d postgres redis minio minio-init

compose-config:
	docker compose config --quiet

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
