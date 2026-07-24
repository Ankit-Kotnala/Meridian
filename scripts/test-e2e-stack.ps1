[CmdletBinding()]
param(
    [ValidateSet(2, 3, 4, 5, 6, 7, 8)]
    [int]$Phase = 2
)

$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Assert-MigrationHeadOutput {
    param(
        [object[]]$Output,
        [string]$ExpectedRevision,
        [string]$Step
    )

    $ExpectedLine = "$ExpectedRevision (head)"
    $HeadLines = @(
        $Output |
            ForEach-Object { [string]$_ } |
            Where-Object { $_ -match '^[^\s]+ \(head\)$' }
    )
    if ($HeadLines.Count -ne 1 -or $HeadLines[0] -ne $ExpectedLine) {
        $RenderedOutput = (($Output | Out-String).Trim())
        throw "$Step reported an unexpected migration head. Expected '$ExpectedLine'; received '$RenderedOutput'."
    }
}

function Wait-ComposeServiceHealthy {
    param(
        [string]$Service,
        [int]$TimeoutSeconds = 900,
        [int]$PollSeconds = 10
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $LastStatus = "missing"
    while ((Get-Date) -lt $Deadline) {
        $Container = docker compose --project-name $ProjectName ps --quiet $Service
        Assert-LastExitCode "$Service container lookup"
        if ($Container) {
            $LastStatus = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' $Container
            Assert-LastExitCode "$Service health inspection"
            if ($LastStatus -eq "healthy") {
                return
            }
        }
        Start-Sleep -Seconds $PollSeconds
    }

    throw "$Service did not become healthy within $TimeoutSeconds seconds; last health status was '$LastStatus'."
}

$ExpectedMigrationHead = if ($env:CAREEROS_EXPECTED_MIGRATION_HEAD) {
    $env:CAREEROS_EXPECTED_MIGRATION_HEAD
}
else {
    "20260724_0009"
}

if ($Phase -eq 8) {
    $RollbackRevision = "20260719_0008"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts",
        "e2e/career-record-journey.spec.ts",
        "e2e/role-readiness-journey.spec.ts",
        "e2e/job-match-journey.spec.ts",
        "e2e/change-studio-journey.spec.ts",
        "e2e/resume-builder-journey.spec.ts",
        "e2e/application-workspace-journey.spec.ts"
    )
}
elseif ($Phase -eq 7) {
    $RollbackRevision = "20260719_0007"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts",
        "e2e/career-record-journey.spec.ts",
        "e2e/role-readiness-journey.spec.ts",
        "e2e/job-match-journey.spec.ts",
        "e2e/change-studio-journey.spec.ts",
        "e2e/resume-builder-journey.spec.ts"
    )
}
elseif ($Phase -eq 6) {
    $RollbackRevision = "20260719_0006"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts",
        "e2e/career-record-journey.spec.ts",
        "e2e/role-readiness-journey.spec.ts",
        "e2e/job-match-journey.spec.ts",
        "e2e/change-studio-journey.spec.ts"
    )
}
elseif ($Phase -eq 5) {
    $RollbackRevision = "20260719_0005"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts",
        "e2e/career-record-journey.spec.ts",
        "e2e/role-readiness-journey.spec.ts",
        "e2e/job-match-journey.spec.ts"
    )
}
elseif ($Phase -eq 4) {
    $RollbackRevision = "20260715_0004"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts",
        "e2e/career-record-journey.spec.ts",
        "e2e/role-readiness-journey.spec.ts"
    )
}
elseif ($Phase -eq 3) {
    $RollbackRevision = "20260715_0003"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts",
        "e2e/career-record-journey.spec.ts"
    )
}
else {
    $RollbackRevision = "20260715_0002"
    $JourneySpecs = @(
        "e2e/auth-journey.spec.ts",
        "e2e/resume-health-journey.spec.ts"
    )
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ProjectName = if ($env:CAREEROS_E2E_PROJECT_NAME) {
    $env:CAREEROS_E2E_PROJECT_NAME
}
else {
    "careeros-e2e-$PID"
}
if ($ProjectName -notmatch '^careeros-e2e-[a-z0-9][a-z0-9_-]*$') {
    throw "CAREEROS_E2E_PROJECT_NAME must begin with careeros-e2e- and contain only lowercase letters, digits, underscores, or hyphens."
}
$Overrides = [ordered]@{
    COMPOSE_PROJECT_NAME       = $ProjectName
    POSTGRES_PORT              = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "55433" }
    REDIS_PORT                 = if ($env:REDIS_PORT) { $env:REDIS_PORT } else { "6380" }
    MINIO_API_PORT             = if ($env:MINIO_API_PORT) { $env:MINIO_API_PORT } else { "19000" }
    MINIO_CONSOLE_PORT         = if ($env:MINIO_CONSOLE_PORT) { $env:MINIO_CONSOLE_PORT } else { "19001" }
    CLAMAV_PORT                = if ($env:CLAMAV_PORT) { $env:CLAMAV_PORT } else { "13310" }
    CLAMAV_PORT_INTERNAL       = "3310"
    MAILPIT_SMTP_PORT          = if ($env:MAILPIT_SMTP_PORT) { $env:MAILPIT_SMTP_PORT } else { "11025" }
    MAILPIT_HTTP_PORT          = if ($env:MAILPIT_HTTP_PORT) { $env:MAILPIT_HTTP_PORT } else { "18025" }
    API_PORT                   = if ($env:API_PORT) { $env:API_PORT } else { "18000" }
    WEB_PORT                   = if ($env:WEB_PORT) { $env:WEB_PORT } else { "13000" }
    ENVIRONMENT                = "development"
    POSTGRES_USER              = "careeros"
    POSTGRES_PASSWORD          = "change-me-local-only"
    POSTGRES_DB                = "careeros"
    DATABASE_URL               = "postgresql+asyncpg://careeros:change-me-local-only@postgres:5432/careeros"
    REDIS_URL                  = "redis://redis:6379/0"
    CELERY_BROKER_URL          = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND      = "redis://redis:6379/1"
    MINIO_ROOT_USER            = "careeros-local"
    MINIO_ROOT_PASSWORD        = "change-me-local-only"
    S3_ENDPOINT_URL            = "http://minio:9000"
    S3_REGION                  = "us-east-1"
    S3_BUCKET                  = "careeros-documents"
    S3_APP_ACCESS_KEY_ID       = "careeros-e2e-app"
    S3_APP_SECRET_ACCESS_KEY   = "change-me-local-only-e2e-storage-secret"
    S3_USE_SSL                 = "false"
    MALWARE_SCANNER_PROVIDER   = "clamav"
    CLAMAV_HOST                = "clamav"
    CLAMAV_TIMEOUT_SECONDS     = "30"
    DOCUMENT_TEMP_ROOT         = "/tmp/careeros"
    DOCUMENT_MAX_BYTES         = "10485760"
    DOCUMENT_MAX_PAGES         = "20"
    DOCUMENT_MAX_ARCHIVE_ENTRIES = "256"
    DOCUMENT_MAX_UNCOMPRESSED_BYTES = "52428800"
    DOCUMENT_MAX_COMPRESSION_RATIO = "100"
    DOCUMENT_MAX_EXTRACTED_CHARACTERS = "500000"
    DOCUMENT_MAX_EXTRACTED_BLOCKS = "5000"
    DOCUMENT_MAX_SERIALIZED_ARTIFACT_BYTES = "2097152"
    RESUME_JOB_RECONCILIATION_INTERVAL_SECONDS = "60"
    RESUME_JOB_RECONCILIATION_STALE_SECONDS = "300"
    DOCUMENT_PROCESSING_TIMEOUT_SECONDS = "120"
    API_BASE_URL               = "http://api:8000"
    AUTH_TOKEN_PEPPER          = if ($env:CAREEROS_E2E_AUTH_TOKEN_PEPPER) { $env:CAREEROS_E2E_AUTH_TOKEN_PEPPER } else { "change-me-local-only-e2e-auth-token-pepper" }
    RESUME_CAPABILITY_PEPPER   = "change-me-local-only-e2e-resume-capability-pepper"
    BFF_CLIENT_SIGNAL_SECRET   = "change-me-local-only-e2e-bff-client-signal-secret"
    API_BFF_CLIENT_SIGNAL_SECRET = "change-me-local-only-e2e-bff-client-signal-secret"
    COOKIE_SECURE              = "false"
    EMAIL_PROVIDER             = "smtp"
    EMAIL_FROM_ADDRESS         = "no-reply@careeros.local"
    SMTP_HOST                  = "mailpit"
    SMTP_PORT                  = "1025"
    SMTP_USERNAME              = ""
    SMTP_PASSWORD              = ""
    SMTP_START_TLS             = "false"
    GOOGLE_OAUTH_ENABLED       = "false"
    GOOGLE_CLIENT_ID           = ""
    GOOGLE_CLIENT_SECRET       = ""
    AI_PROVIDER                = "deterministic"
    PLAYWRIGHT_EXTERNAL_SERVER = "1"
    PLAYWRIGHT_E2E_MODE        = "full-stack"
}

$PublicAppUrl = "http://127.0.0.1:$($Overrides.WEB_PORT)"
$Overrides.PUBLIC_APP_URL = $PublicAppUrl
$Overrides.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$($Overrides.API_PORT)"
$Overrides.S3_PUBLIC_ENDPOINT_URL = "http://127.0.0.1:$($Overrides.MINIO_API_PORT)"
$Overrides.S3_ALLOWED_ORIGIN = $PublicAppUrl
$Overrides.NEXT_PUBLIC_UPLOAD_ORIGIN = $Overrides.S3_PUBLIC_ENDPOINT_URL
$Overrides.ALLOWED_ORIGINS = "[`"$PublicAppUrl`"]"
$Overrides.CORS_ORIGINS = "[`"$PublicAppUrl`"]"
$Overrides.GOOGLE_REDIRECT_URI = "$PublicAppUrl/api/v1/auth/google/callback"
$Overrides.PLAYWRIGHT_BASE_URL = $PublicAppUrl
$Overrides.PLAYWRIGHT_MAILPIT_URL = "http://127.0.0.1:$($Overrides.MAILPIT_HTTP_PORT)"
$Overrides.CAREEROS_TEST_DATABASE_URL = "postgresql+asyncpg://careeros:change-me-local-only@127.0.0.1:$($Overrides.POSTGRES_PORT)/careeros"
$Overrides.CAREEROS_TEST_REDIS_URL = "redis://127.0.0.1:$($Overrides.REDIS_PORT)/15"
$Overrides.CAREEROS_TEST_S3_ENDPOINT_URL = $Overrides.S3_PUBLIC_ENDPOINT_URL
$Overrides.CAREEROS_TEST_S3_REGION = $Overrides.S3_REGION
$Overrides.CAREEROS_TEST_S3_BUCKET = $Overrides.S3_BUCKET
$Overrides.CAREEROS_TEST_S3_ACCESS_KEY_ID = $Overrides.S3_APP_ACCESS_KEY_ID
$Overrides.CAREEROS_TEST_S3_SECRET_ACCESS_KEY = $Overrides.S3_APP_SECRET_ACCESS_KEY
$Overrides.CAREEROS_TEST_CLAMAV_HOST = "127.0.0.1"
$Overrides.CAREEROS_TEST_CLAMAV_PORT = $Overrides.CLAMAV_PORT

$PreviousValues = @{}
foreach ($Entry in $Overrides.GetEnumerator()) {
    $PreviousValues[$Entry.Key] = [Environment]::GetEnvironmentVariable($Entry.Key, "Process")
    [Environment]::SetEnvironmentVariable($Entry.Key, [string]$Entry.Value, "Process")
}

$MainSucceeded = $false
Push-Location $RepositoryRoot
try {
    docker compose --project-name $ProjectName config --quiet
    Assert-LastExitCode "Isolated Compose configuration"
    docker compose --project-name $ProjectName build api worker web web-edge
    Assert-LastExitCode "Isolated application image build"
    docker compose --project-name $ProjectName up --detach --wait --wait-timeout 900 postgres redis minio mailpit clamav
    Assert-LastExitCode "Isolated dependency startup"
    Wait-ComposeServiceHealthy -Service "clamav" -TimeoutSeconds 900 -PollSeconds 10
    docker compose --project-name $ProjectName up --detach minio-init
    Assert-LastExitCode "Object-storage initializer startup"
    $InitContainer = docker compose --project-name $ProjectName ps --all --quiet minio-init
    Assert-LastExitCode "Object-storage initializer lookup"
    if (-not $InitContainer) {
        throw "Compose did not create the object-storage initializer."
    }
    $InitExitCode = docker wait $InitContainer
    Assert-LastExitCode "Object-storage initializer wait"
    if ([int]$InitExitCode -ne 0) {
        throw "Object-storage initialization failed with exit code $InitExitCode."
    }
    if ($ExpectedMigrationHead) {
        $MigrationHeads = @(
            docker compose --project-name $ProjectName run --rm --no-deps api alembic -c packages/backend/alembic.ini heads
        )
        Assert-LastExitCode "Phase $Phase migration-head lookup"
        $MigrationHeads | ForEach-Object { Write-Host $_ }
        Assert-MigrationHeadOutput -Output $MigrationHeads -ExpectedRevision $ExpectedMigrationHead -Step "Phase $Phase migration-head lookup"
    }
    docker compose --project-name $ProjectName run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
    Assert-LastExitCode "Isolated database migration"
    docker compose --project-name $ProjectName run --rm --no-deps api alembic -c packages/backend/alembic.ini downgrade $RollbackRevision
    Assert-LastExitCode "Phase $Phase database migration rollback"
    docker compose --project-name $ProjectName run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
    Assert-LastExitCode "Phase $Phase database migration forward repair"
    if ($ExpectedMigrationHead) {
        $CurrentMigration = @(
            docker compose --project-name $ProjectName run --rm --no-deps api alembic -c packages/backend/alembic.ini current
        )
        Assert-LastExitCode "Phase $Phase current-migration lookup"
        $CurrentMigration | ForEach-Object { Write-Host $_ }
        Assert-MigrationHeadOutput -Output $CurrentMigration -ExpectedRevision $ExpectedMigrationHead -Step "Phase $Phase current-migration lookup"
    }
    Push-Location "packages/backend"
    try {
        uv run --package careeros-backend pytest tests/integration
        Assert-LastExitCode "PostgreSQL and Redis identity integration tests"
    }
    finally {
        Pop-Location
    }
    docker compose --project-name $ProjectName up --detach --wait --wait-timeout 180 --no-deps api worker worker-scheduler web web-edge
    Assert-LastExitCode "Isolated application startup"
    $WorkerContainer = docker compose --project-name $ProjectName ps --quiet worker
    Assert-LastExitCode "Worker container lookup"
    if (-not $WorkerContainer) {
        throw "Compose did not create the document worker."
    }
    $SchedulerContainer = docker compose --project-name $ProjectName ps --quiet worker-scheduler
    Assert-LastExitCode "Worker scheduler container lookup"
    if (-not $SchedulerContainer) {
        throw "Compose did not create the worker scheduler."
    }
    $SchedulerInspect = (docker inspect $SchedulerContainer | ConvertFrom-Json)[0]
    Assert-LastExitCode "Worker scheduler health inspection"
    if ($SchedulerInspect.State.Health.Status -ne "healthy") {
        throw "Worker scheduler did not report healthy Celery Beat process state."
    }
    $AdvertisedPolicy = Invoke-RestMethod -Uri "$PublicAppUrl/api/v1/guest/resume-health/upload-policy" -Method Get
    if ([int]$AdvertisedPolicy.maxPages -ne [int]$Overrides.DOCUMENT_MAX_PAGES) {
        throw "The API advertised page limit $($AdvertisedPolicy.maxPages), expected $($Overrides.DOCUMENT_MAX_PAGES)."
    }
    $WorkerMaxPages = docker exec $WorkerContainer python -c "from careeros_worker.config import get_settings; print(get_settings().document_max_pages)"
    Assert-LastExitCode "Worker page-limit configuration probe"
    if ([int]$WorkerMaxPages -ne [int]$AdvertisedPolicy.maxPages) {
        throw "Worker page limit $WorkerMaxPages differs from the API policy $($AdvertisedPolicy.maxPages)."
    }
    $WorkerInspect = (docker inspect $WorkerContainer | ConvertFrom-Json)[0]
    Assert-LastExitCode "Worker container policy inspection"
    if (-not $WorkerInspect.HostConfig.ReadonlyRootfs) {
        throw "Document worker root filesystem is not read-only."
    }
    if ($WorkerInspect.HostConfig.CapDrop -notcontains "ALL") {
        throw "Document worker did not drop all Linux capabilities."
    }
    if (($WorkerInspect.HostConfig.SecurityOpt -notcontains "no-new-privileges:true") -and ($WorkerInspect.HostConfig.SecurityOpt -notcontains "no-new-privileges")) {
        throw "Document worker does not enforce no-new-privileges."
    }
    if ($WorkerInspect.HostConfig.PidsLimit -le 0 -or $WorkerInspect.HostConfig.Memory -le 0 -or $WorkerInspect.HostConfig.NanoCpus -le 0) {
        throw "Document worker CPU, memory, and PID limits must be explicit."
    }
    if ($WorkerInspect.HostConfig.Tmpfs.PSObject.Properties.Name -notcontains "/tmp/careeros") {
        throw "Document worker requires a bounded private temporary filesystem."
    }
    if ($WorkerInspect.NetworkSettings.Networks.PSObject.Properties.Count -ne 1) {
        throw "Document worker must attach only to the internal backend network."
    }
    $AnonymousStatus = & curl.exe --silent --output NUL --write-out "%{http_code}" "http://127.0.0.1:$($Overrides.MINIO_API_PORT)/$($Overrides.S3_BUCKET)"
    Assert-LastExitCode "Anonymous object-store access probe"
    if ($AnonymousStatus -ne "403") {
        throw "Private document bucket returned HTTP $AnonymousStatus to an anonymous request."
    }
    docker compose --project-name $ProjectName stop postgres
    Assert-LastExitCode "PostgreSQL dependency stop"
    $NotReadyStatus = & curl.exe --silent --output NUL --write-out "%{http_code}" "http://127.0.0.1:$($Overrides.API_PORT)/ready"
    Assert-LastExitCode "Readiness failure probe"
    if ($NotReadyStatus -ne "503") {
        throw "API readiness returned HTTP $NotReadyStatus while PostgreSQL was unavailable."
    }
    docker compose --project-name $ProjectName start postgres
    Assert-LastExitCode "PostgreSQL dependency restart"
    docker compose --project-name $ProjectName up --detach --wait --wait-timeout 120 postgres
    Assert-LastExitCode "PostgreSQL recovery wait"
    $Recovered = $false
    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        $RecoveredStatus = & curl.exe --silent --output NUL --write-out "%{http_code}" "http://127.0.0.1:$($Overrides.API_PORT)/ready"
        if ($RecoveredStatus -eq "200") {
            $Recovered = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $Recovered) {
        throw "API readiness did not recover after PostgreSQL restarted."
    }
    & pnpm --filter "@careeros/web" exec playwright test @JourneySpecs
    Assert-LastExitCode "Phase $Phase full-stack browser journeys"
    $MainSucceeded = $true
}
finally {
    if (-not $MainSucceeded) {
        docker compose --project-name $ProjectName ps --all
        docker compose --project-name $ProjectName logs --no-color --tail 200
    }
    docker compose --project-name $ProjectName down --volumes --remove-orphans --rmi local
    $CleanupExitCode = $LASTEXITCODE
    Pop-Location

    foreach ($Entry in $PreviousValues.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($Entry.Key, $Entry.Value, "Process")
    }

    if ($MainSucceeded -and $CleanupExitCode -ne 0) {
        throw "Isolated E2E cleanup failed with exit code $CleanupExitCode."
    }
}

Write-Host "CareerOS Phase $Phase isolated full-stack browser journeys passed and all test state was removed."
