$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1" -Phase 4
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4 isolated Role Explorer workflow failed with exit code $LASTEXITCODE."
}

Write-Host "CareerOS Phase 4 verification passed."
