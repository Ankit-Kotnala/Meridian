[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Test-PrimaryStackReady {
    try {
        $RawRows = @(docker compose ps --all --format json)
        $Rows = @($RawRows | ForEach-Object { $_ | ConvertFrom-Json })
    }
    catch {
        return $false
    }

    $ExpectedHealthyServices = @(
        "postgres",
        "redis",
        "minio",
        "clamav",
        "mailpit",
        "api",
        "worker",
        "worker-scheduler",
        "web",
        "web-edge"
    )
    foreach ($Service in $ExpectedHealthyServices) {
        $Row = $Rows | Where-Object { $_.Service -eq $Service } | Select-Object -First 1
        if ($null -eq $Row -or $Row.State -ne "running" -or $Row.Health -ne "healthy") {
            return $false
        }
    }

    $Init = $Rows | Where-Object { $_.Service -eq "minio-init" } | Select-Object -First 1
    return (
        $null -ne $Init -and
        $Init.State -eq "exited" -and
        [int]$Init.ExitCode -eq 0
    )
}

function Wait-PrimaryStackReady {
    param(
        [int]$MaxAttempts = 10,
        [int]$DelaySeconds = 3
    )

    for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
        if (Test-PrimaryStackReady) {
            return $true
        }
        if ($Attempt -lt $MaxAttempts) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    return $false
}

function Restore-PrimaryStack {
    param(
        [int]$MaxAttempts = 5
    )

    $LastExitCode = 1
    for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
        docker compose up --detach --wait --wait-timeout 300
        $LastExitCode = $LASTEXITCODE
        if ($LastExitCode -eq 0 -or (Wait-PrimaryStackReady)) {
            return
        }
        if ($Attempt -lt $MaxAttempts) {
            $DelaySeconds = [Math]::Min(5 * $Attempt, 20)
            Write-Warning (
                "Primary Compose recovery attempt $Attempt/$MaxAttempts failed " +
                "with exit code $LastExitCode; retrying in $DelaySeconds seconds."
            )
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    throw "Primary Compose stack recovery failed with exit code $LastExitCode."
}

& "$PSScriptRoot/verify.ps1"
if ($LASTEXITCODE -ne 0) {
    throw "CareerOS platform verification failed with exit code $LASTEXITCODE."
}

$PrimaryStackPaused = $false
try {
    docker compose stop --timeout 30
    if ($LASTEXITCODE -ne 0) {
        throw "Primary Compose stack pause failed with exit code $LASTEXITCODE."
    }
    $PrimaryStackPaused = $true

    & "$PSScriptRoot/test-e2e-stack.ps1" -Phase 9
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 9 isolated career workspace workflow failed with exit code $LASTEXITCODE."
    }
}
finally {
    if ($PrimaryStackPaused) {
        Restore-PrimaryStack
    }
}

Write-Host "CareerOS Phase 9 verification passed."
