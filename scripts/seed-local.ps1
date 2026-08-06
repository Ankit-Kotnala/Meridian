$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$originalConfirmation = $env:REZUMI_ALLOW_LOCAL_SEED

try {
    docker compose up --detach --wait postgres minio minio-init
    if ($LASTEXITCODE -ne 0) {
        throw "Local PostgreSQL/MinIO startup failed."
    }

    docker compose build api
    if ($LASTEXITCODE -ne 0) {
        throw "API tooling image build failed."
    }

    docker compose run --rm --no-deps api `
        alembic -c packages/backend/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Local database migration failed."
    }

    $env:REZUMI_ALLOW_LOCAL_SEED = "fictional-rezumi-local-seed-v1"
    docker compose --profile tools run --rm --no-deps local-seed
    if ($LASTEXITCODE -ne 0) {
        throw "Fictional local seed failed."
    }
}
finally {
    if ($null -eq $originalConfirmation) {
        Remove-Item Env:REZUMI_ALLOW_LOCAL_SEED -ErrorAction SilentlyContinue
    }
    else {
        $env:REZUMI_ALLOW_LOCAL_SEED = $originalConfirmation
    }
}
