$ErrorActionPreference = "Stop"

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "Platform verification failed with exit code $LASTEXITCODE."
}

& "$PSScriptRoot/test-e2e-stack.ps1" -Phase 8
if ($LASTEXITCODE -ne 0) {
    throw "Phase 8 isolated Application Workspace workflow failed with exit code $LASTEXITCODE."
}

Write-Host "Rezumi Phase 8 verification passed."
