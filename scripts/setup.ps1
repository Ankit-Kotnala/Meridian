$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from the development template. Change local credentials if this machine is shared."
}

corepack enable
Assert-LastExitCode "Corepack enable"
corepack prepare pnpm@11.13.0 --activate
Assert-LastExitCode "pnpm activation"
pnpm install --frozen-lockfile
Assert-LastExitCode "pnpm install"

Push-Location "apps/api"
try {
    uv sync --frozen --all-extras --dev
    Assert-LastExitCode "API dependency sync"
}
finally {
    Pop-Location
}

Push-Location "apps/worker"
try {
    uv sync --frozen --all-extras --dev
    Assert-LastExitCode "Worker dependency sync"
}
finally {
    Pop-Location
}

Write-Host "CareerOS Phase 0 dependencies are ready."
