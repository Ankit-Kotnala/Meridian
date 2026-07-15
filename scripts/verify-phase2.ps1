$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Phase 2 isolated document workflow failed with exit code $LASTEXITCODE."
}

Write-Host "CareerOS Phase 2 verification passed."
