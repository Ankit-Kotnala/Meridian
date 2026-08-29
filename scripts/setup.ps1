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
corepack prepare npm@11.8.0 --activate
Assert-LastExitCode "npm activation"
npm ci
Assert-LastExitCode "npm install"

uv sync --project backend --frozen --all-packages --all-groups
Assert-LastExitCode "Python workspace dependency sync"

Write-Host "Rezumi Phase 0 dependencies are ready."
Write-Host ""
Write-Host "Start the full local stack with:  npm run local:up"
Write-Host "Or web hot-reload against Docker backend:  npm run dev:web"
Write-Host "API only (host process):  npm run dev:api"
