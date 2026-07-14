$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from the development template. Change local credentials if this machine is shared."
}

corepack enable
corepack prepare pnpm@11.13.0 --activate
pnpm install --frozen-lockfile

Push-Location "apps/api"
uv sync --frozen --all-extras --dev
Pop-Location

Push-Location "apps/worker"
uv sync --frozen --all-extras --dev
Pop-Location

Write-Host "CareerOS Phase 0 dependencies are ready."
