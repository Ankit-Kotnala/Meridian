$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

pnpm format:check
Assert-LastExitCode "Prettier check"
pnpm lint
Assert-LastExitCode "JavaScript lint"
pnpm typecheck
Assert-LastExitCode "TypeScript check"
pnpm test
Assert-LastExitCode "JavaScript tests"
pnpm build
Assert-LastExitCode "JavaScript build"

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

docker compose config --quiet
Assert-LastExitCode "Compose configuration"
docker compose build api worker web
Assert-LastExitCode "Application image build"
Write-Host "CareerOS Phase 0 verification passed."
