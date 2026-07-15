$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

pnpm format:check
Assert-LastExitCode "Prettier check"
uv lock --check
Assert-LastExitCode "Python workspace lock check"
pnpm contracts:check
Assert-LastExitCode "Generated contract drift check"
pnpm lint
Assert-LastExitCode "JavaScript lint"
pnpm typecheck
Assert-LastExitCode "TypeScript check"
pnpm test
Assert-LastExitCode "JavaScript tests"
pnpm build
Assert-LastExitCode "JavaScript build"

Push-Location "packages/backend"
try {
    uv run --package careeros-backend ruff format --check .
    Assert-LastExitCode "Backend format check"
    uv run --package careeros-backend ruff check .
    Assert-LastExitCode "Backend lint"
    uv run --package careeros-backend mypy
    Assert-LastExitCode "Backend type check"
    uv run --package careeros-backend pytest tests/architecture tests/unit
    Assert-LastExitCode "Backend unit and architecture tests"
}
finally {
    Pop-Location
}

Push-Location "apps/api"
try {
    uv run ruff format --check .
    Assert-LastExitCode "API format check"
    uv run ruff check .
    Assert-LastExitCode "API lint"
    uv run mypy
    Assert-LastExitCode "API type check"
    uv run pytest
    Assert-LastExitCode "API tests"
}
finally {
    Pop-Location
}

Push-Location "apps/worker"
try {
    uv run ruff format --check .
    Assert-LastExitCode "Worker format check"
    uv run ruff check .
    Assert-LastExitCode "Worker lint"
    uv run mypy
    Assert-LastExitCode "Worker type check"
    uv run pytest
    Assert-LastExitCode "Worker tests"
}
finally {
    Pop-Location
}

uv run --package careeros-api ruff format --config apps/api/pyproject.toml --check packages/contracts/scripts/export_openapi.py
Assert-LastExitCode "OpenAPI exporter format check"
uv run --package careeros-api ruff check --config apps/api/pyproject.toml packages/contracts/scripts/export_openapi.py
Assert-LastExitCode "OpenAPI exporter lint"

docker compose config --quiet
Assert-LastExitCode "Compose configuration"
docker compose build api worker web
Assert-LastExitCode "Application image build"
docker compose up --detach --wait --wait-timeout 180
Assert-LastExitCode "Application stack startup"
docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
Assert-LastExitCode "Container migration"
docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
Assert-LastExitCode "Idempotent container migration"
docker compose run --rm --no-deps api alembic -c packages/backend/alembic.ini current
Assert-LastExitCode "Container migration state"

$Endpoints = @(
    "http://127.0.0.1:3000/api/health",
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8000/ready",
    "http://127.0.0.1:8000/api/v1/meta",
    "http://127.0.0.1:8025/api/v1/info"
)
foreach ($Endpoint in $Endpoints) {
    $Response = Invoke-WebRequest -Uri $Endpoint -UseBasicParsing
    if ($Response.StatusCode -ne 200) {
        throw "Runtime probe failed for $Endpoint with status $($Response.StatusCode)."
    }
}

docker compose exec -T worker celery --app careeros_worker.app:celery_app inspect ping --timeout 5
Assert-LastExitCode "Worker broker round trip"
Write-Host "CareerOS Phase 0 verification passed."
