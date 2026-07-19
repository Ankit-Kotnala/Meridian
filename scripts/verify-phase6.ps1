$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1" -Phase 6
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6 isolated Change Studio workflow failed with exit code $LASTEXITCODE."
}

Write-Host "CareerOS Phase 6 verification passed."
