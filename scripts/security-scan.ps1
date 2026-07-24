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

    uv sync --frozen --all-packages --all-groups
    Assert-LastExitCode "Python workspace dependency sync"
    uv run --package careeros-api --with pip-audit==2.10.1 pip-audit
    Assert-LastExitCode "Python workspace pip-audit"

    docker compose build api worker web web-edge
    Assert-LastExitCode "Application image build"

    $Images = @(
        "careeros-api:latest",
        "careeros-worker:latest",
        "careeros-web:latest",
        "careeros-web-edge:latest"
    )
    foreach ($Image in $Images) {
        docker run --rm --volume "/var/run/docker.sock:/var/run/docker.sock" `
            --volume "${RepositoryRoot}/.grype.yaml:/etc/grype.yaml:ro" `
            --volume "careeros-grype-cache:/root/.cache/grype" `
            anchore/grype@sha256:391bfda62888fb4e98ff5c4c81598f7431a3c1eac3f8519d69d1ff00df247c1d `
            $Image --config /etc/grype.yaml --fail-on high --only-fixed
        Assert-LastExitCode "Grype scan for $Image"
    }

    Write-Host "CareerOS security scans passed."
}
finally {
    Pop-Location
}
