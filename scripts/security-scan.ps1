$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepositoryRoot

try {
    docker run --rm --volume "${RepositoryRoot}:/repo:ro" `
        ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f `
        dir /repo --config /repo/.gitleaks.toml --redact --exit-code 1
    Assert-LastExitCode "Gitleaks"

    pnpm audit --audit-level high
    Assert-LastExitCode "pnpm audit"

    uv run --project apps/api --with pip-audit pip-audit
    Assert-LastExitCode "API pip-audit"

    uv run --project apps/worker --with pip-audit pip-audit
    Assert-LastExitCode "Worker pip-audit"

    docker compose build api worker web
    Assert-LastExitCode "Application image build"

    $Images = @("careeros-api:latest", "careeros-worker:latest", "careeros-web:latest")
    foreach ($Image in $Images) {
        docker run --rm --volume "/var/run/docker.sock:/var/run/docker.sock" `
            anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d `
            $Image --fail-on critical --only-fixed
        Assert-LastExitCode "Grype scan for $Image"
    }

    Write-Host "CareerOS security scans passed."
}
finally {
    Pop-Location
}
