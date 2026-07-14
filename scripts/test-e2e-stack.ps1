$ErrorActionPreference = "Stop"

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
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
    S3_ACCESS_KEY_ID           = "careeros-local"
    S3_SECRET_ACCESS_KEY       = "change-me-local-only"
    S3_USE_SSL                 = "false"
    API_BASE_URL               = "http://api:8000"
    AUTH_TOKEN_PEPPER          = if ($env:CAREEROS_E2E_AUTH_TOKEN_PEPPER) { $env:CAREEROS_E2E_AUTH_TOKEN_PEPPER } else { "change-me-local-only-e2e-auth-token-pepper" }
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
    PLAYWRIGHT_EXTERNAL_SERVER = "1"
    PLAYWRIGHT_E2E_MODE        = "full-stack"
}

$PublicAppUrl = "http://127.0.0.1:$($Overrides.WEB_PORT)"
$Overrides.PUBLIC_APP_URL = $PublicAppUrl
$Overrides.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$($Overrides.API_PORT)"
$Overrides.ALLOWED_ORIGINS = "[`"$PublicAppUrl`"]"
$Overrides.CORS_ORIGINS = "[`"$PublicAppUrl`"]"
$Overrides.GOOGLE_REDIRECT_URI = "$PublicAppUrl/api/v1/auth/google/callback"
$Overrides.PLAYWRIGHT_BASE_URL = $PublicAppUrl
$Overrides.PLAYWRIGHT_MAILPIT_URL = "http://127.0.0.1:$($Overrides.MAILPIT_HTTP_PORT)"
$Overrides.CAREEROS_TEST_DATABASE_URL = "postgresql+asyncpg://careeros:change-me-local-only@127.0.0.1:$($Overrides.POSTGRES_PORT)/careeros"
$Overrides.CAREEROS_TEST_REDIS_URL = "redis://127.0.0.1:$($Overrides.REDIS_PORT)/15"

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
    docker compose --project-name $ProjectName build api worker web
    Assert-LastExitCode "Isolated application image build"
    docker compose --project-name $ProjectName up --detach --wait --wait-timeout 180 postgres redis minio mailpit
    Assert-LastExitCode "Isolated dependency startup"
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
    docker compose --project-name $ProjectName run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
    Assert-LastExitCode "Isolated database migration"
    Push-Location "packages/backend"
    try {
        uv run --package careeros-backend pytest tests/integration
        Assert-LastExitCode "PostgreSQL and Redis identity integration tests"
    }
    finally {
        Pop-Location
    }
    docker compose --project-name $ProjectName up --detach --wait --wait-timeout 180 --no-deps api worker web
    Assert-LastExitCode "Isolated application startup"
    pnpm test:e2e
    Assert-LastExitCode "Full-stack browser journey"
    $MainSucceeded = $true
}
finally {
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

Write-Host "CareerOS isolated full-stack browser journey passed and all test state was removed."
