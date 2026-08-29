$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Assert-HttpEndpoint(
    [string]$Endpoint,
    [int]$Attempts = 10,
    [int]$DelaySeconds = 2
) {
    $LastFailure = "no response"
    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            $Response = Invoke-WebRequest `
                -Uri $Endpoint `
                -UseBasicParsing `
                -TimeoutSec 10 `
                -ErrorAction Stop
            if ($Response.StatusCode -eq 200) {
                return
            }
            $LastFailure = "HTTP $($Response.StatusCode)"
        }
        catch {
            $LastFailure = $_.Exception.Message
        }
        if ($Attempt -lt $Attempts) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    throw "Runtime probe failed for $Endpoint after $Attempts attempts: $LastFailure"
}

npm run format:check
Assert-LastExitCode "Prettier check"
uv lock --project backend --check
Assert-LastExitCode "Python workspace lock check"
npm run contracts:check
Assert-LastExitCode "Generated contract drift check"
npm run lint
Assert-LastExitCode "JavaScript lint"
npm run typecheck
Assert-LastExitCode "TypeScript check"
npm run test
Assert-LastExitCode "JavaScript tests"
npm run build
Assert-LastExitCode "JavaScript build"

Push-Location "backend/core"
try {
    uv run --package rezumi-backend ruff format --check .
    Assert-LastExitCode "Backend format check"
    uv run --package rezumi-backend ruff check .
    Assert-LastExitCode "Backend lint"
    uv run --package rezumi-backend mypy
    Assert-LastExitCode "Backend type check"
    uv run --package rezumi-backend pytest tests/architecture tests/unit
    Assert-LastExitCode "Backend unit and architecture tests"
}
finally {
    Pop-Location
}

Push-Location "backend/api"
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

Push-Location "backend/worker"
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

uv run --project backend --package rezumi-api ruff format --config backend/api/pyproject.toml --check shared/contracts/scripts/export_openapi.py
Assert-LastExitCode "OpenAPI exporter format check"
uv run --project backend --package rezumi-api ruff check --config backend/api/pyproject.toml shared/contracts/scripts/export_openapi.py
Assert-LastExitCode "OpenAPI exporter lint"

docker compose -f infra/compose.yaml --project-directory . config --quiet
Assert-LastExitCode "Compose configuration"
foreach ($Service in @("api", "worker", "web", "web-edge")) {
    docker compose -f infra/compose.yaml --project-directory . build $Service
    Assert-LastExitCode "Application image build for $Service"
}
docker compose -f infra/compose.yaml --project-directory . up --detach --force-recreate --wait --wait-timeout 300
Assert-LastExitCode "Application stack startup"
docker compose -f infra/compose.yaml --project-directory . run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
Assert-LastExitCode "Container migration"
docker compose -f infra/compose.yaml --project-directory . run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
Assert-LastExitCode "Idempotent container migration"
docker compose -f infra/compose.yaml --project-directory . run --rm --no-deps api alembic -c backend/core/alembic.ini current
Assert-LastExitCode "Container migration state"

$Endpoints = @(
    "http://127.0.0.1:3000/api/health",
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8000/ready",
    "http://127.0.0.1:8000/api/v1/meta",
    "http://127.0.0.1:8025/api/v1/info"
)
foreach ($Endpoint in $Endpoints) {
    Assert-HttpEndpoint -Endpoint $Endpoint
}

docker compose -f infra/compose.yaml --project-directory . exec -T worker celery --app rezumi_worker.app:celery_app inspect ping --timeout 5
Assert-LastExitCode "Worker broker round trip"
Write-Host "Rezumi Phase 0 verification passed."
