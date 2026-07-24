$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1" -Phase 7
if ($LASTEXITCODE -ne 0) {
    throw "Phase 7 isolated Resume Builder workflow failed with exit code $LASTEXITCODE."
}

Write-Host "CareerOS Phase 7 verification passed."
