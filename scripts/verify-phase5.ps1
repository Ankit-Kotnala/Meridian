$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1" -Phase 5
if ($LASTEXITCODE -ne 0) {
    throw "Phase 5 isolated Job Match workflow failed with exit code $LASTEXITCODE."
}

Write-Host "Rezumi Phase 5 verification passed."
