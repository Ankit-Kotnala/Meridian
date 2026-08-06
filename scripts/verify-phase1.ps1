$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Phase 1 full-stack browser journey failed with exit code $LASTEXITCODE."
}

Write-Host "Rezumi Phase 1 verification passed."
