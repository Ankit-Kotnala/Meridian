$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1" -Phase 3
if ($LASTEXITCODE -ne 0) {
    throw "Phase 3 isolated Career Record workflow failed with exit code $LASTEXITCODE."
}

Write-Host "Rezumi Phase 3 verification passed."
