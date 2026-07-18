#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
project_name=${CAREEROS_E2E_PROJECT_NAME:-careeros-e2e-$$}
case "$project_name" in
  careeros-e2e-*) ;;
  *)
    echo "CAREEROS_E2E_PROJECT_NAME must begin with careeros-e2e-." >&2
    exit 2
    ;;
esac

verification_phase=${CAREEROS_E2E_PHASE:-2}
case "$verification_phase" in
  2)
    rollback_revision=20260715_0002
    expected_migration_head=
    ;;
  3)
    rollback_revision=20260715_0003
    expected_migration_head=20260715_0004
    ;;
  *)
    echo "CAREEROS_E2E_PHASE must be either 2 or 3." >&2
    exit 2
    ;;
esac

export COMPOSE_PROJECT_NAME="$project_name"
export POSTGRES_PORT="${POSTGRES_PORT:-55433}"
export REDIS_PORT="${REDIS_PORT:-6380}"
export MINIO_API_PORT="${MINIO_API_PORT:-19000}"
export MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-19001}"
export CLAMAV_PORT="${CLAMAV_PORT:-13310}"
export CLAMAV_PORT_INTERNAL=3310
export MAILPIT_SMTP_PORT="${MAILPIT_SMTP_PORT:-11025}"
export MAILPIT_HTTP_PORT="${MAILPIT_HTTP_PORT:-18025}"
export API_PORT="${API_PORT:-18000}"
export WEB_PORT="${WEB_PORT:-13000}"
export ENVIRONMENT=development
export POSTGRES_USER=careeros
export POSTGRES_PASSWORD=change-me-local-only
export POSTGRES_DB=careeros
export DATABASE_URL=postgresql+asyncpg://careeros:change-me-local-only@postgres:5432/careeros
export REDIS_URL=redis://redis:6379/0
export CELERY_BROKER_URL=redis://redis:6379/0
export CELERY_RESULT_BACKEND=redis://redis:6379/1
export MINIO_ROOT_USER=careeros-local
export MINIO_ROOT_PASSWORD=change-me-local-only
export S3_ENDPOINT_URL=http://minio:9000
export S3_REGION=us-east-1
export S3_BUCKET=careeros-documents
export S3_APP_ACCESS_KEY_ID=careeros-e2e-app
export S3_APP_SECRET_ACCESS_KEY=change-me-local-only-e2e-storage-secret
export S3_USE_SSL=false
export MALWARE_SCANNER_PROVIDER=clamav
export CLAMAV_HOST=clamav
export CLAMAV_TIMEOUT_SECONDS=30
export DOCUMENT_TEMP_ROOT=/tmp/careeros
export DOCUMENT_MAX_BYTES=10485760
export DOCUMENT_MAX_PAGES=20
export DOCUMENT_MAX_ARCHIVE_ENTRIES=256
export DOCUMENT_MAX_UNCOMPRESSED_BYTES=52428800
export DOCUMENT_MAX_COMPRESSION_RATIO=100
export DOCUMENT_MAX_EXTRACTED_CHARACTERS=500000
export DOCUMENT_MAX_EXTRACTED_BLOCKS=5000
export DOCUMENT_MAX_SERIALIZED_ARTIFACT_BYTES=2097152
export RESUME_JOB_RECONCILIATION_INTERVAL_SECONDS=60
export RESUME_JOB_RECONCILIATION_STALE_SECONDS=300
export DOCUMENT_PROCESSING_TIMEOUT_SECONDS=120
export API_BASE_URL=http://api:8000
export PUBLIC_APP_URL="http://127.0.0.1:${WEB_PORT}"
export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:${API_PORT}"
export S3_PUBLIC_ENDPOINT_URL="http://127.0.0.1:${MINIO_API_PORT}"
export S3_ALLOWED_ORIGIN="$PUBLIC_APP_URL"
export NEXT_PUBLIC_UPLOAD_ORIGIN="$S3_PUBLIC_ENDPOINT_URL"
export ALLOWED_ORIGINS="[\"$PUBLIC_APP_URL\"]"
export CORS_ORIGINS="[\"$PUBLIC_APP_URL\"]"
export AUTH_TOKEN_PEPPER="${CAREEROS_E2E_AUTH_TOKEN_PEPPER:-change-me-local-only-e2e-auth-token-pepper}"
export RESUME_CAPABILITY_PEPPER=change-me-local-only-e2e-resume-capability-pepper
export BFF_CLIENT_SIGNAL_SECRET=change-me-local-only-e2e-bff-client-signal-secret
export API_BFF_CLIENT_SIGNAL_SECRET=change-me-local-only-e2e-bff-client-signal-secret
export COOKIE_SECURE=false
export EMAIL_PROVIDER=smtp
export EMAIL_FROM_ADDRESS=no-reply@careeros.local
export SMTP_HOST=mailpit
export SMTP_PORT=1025
export SMTP_USERNAME=
export SMTP_PASSWORD=
export SMTP_START_TLS=false
export GOOGLE_OAUTH_ENABLED=false
export GOOGLE_CLIENT_ID=
export GOOGLE_CLIENT_SECRET=
export GOOGLE_REDIRECT_URI="${PUBLIC_APP_URL}/api/v1/auth/google/callback"
export PLAYWRIGHT_EXTERNAL_SERVER=1
export PLAYWRIGHT_E2E_MODE=full-stack
export PLAYWRIGHT_BASE_URL="$PUBLIC_APP_URL"
export PLAYWRIGHT_MAILPIT_URL="http://127.0.0.1:${MAILPIT_HTTP_PORT}"
export CAREEROS_TEST_DATABASE_URL="postgresql+asyncpg://careeros:change-me-local-only@127.0.0.1:${POSTGRES_PORT}/careeros"
export CAREEROS_TEST_REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/15"
export CAREEROS_TEST_S3_ENDPOINT_URL="$S3_PUBLIC_ENDPOINT_URL"
export CAREEROS_TEST_S3_REGION="$S3_REGION"
export CAREEROS_TEST_S3_BUCKET="$S3_BUCKET"
export CAREEROS_TEST_S3_ACCESS_KEY_ID="$S3_APP_ACCESS_KEY_ID"
export CAREEROS_TEST_S3_SECRET_ACCESS_KEY="$S3_APP_SECRET_ACCESS_KEY"
export CAREEROS_TEST_CLAMAV_HOST=127.0.0.1
export CAREEROS_TEST_CLAMAV_PORT="$CLAMAV_PORT"

assert_migration_head_output() {
  output=$1
  expected_revision=$2
  step=$3
  head_lines=$(printf '%s\n' "$output" | sed -n '/^[^[:space:]][^[:space:]]* (head)$/p')
  expected_line="$expected_revision (head)"
  if [ "$head_lines" != "$expected_line" ]; then
    echo "$step reported an unexpected migration head. Expected '$expected_line'; received '$output'." >&2
    return 1
  fi
}

run_browser_journeys() {
  case "$verification_phase" in
    2)
      pnpm --filter @careeros/web exec playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts
      ;;
    3)
      pnpm --filter @careeros/web exec playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts
      ;;
  esac
}

cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
  if [ "$status" -ne 0 ]; then
    docker compose --project-name "$project_name" ps --all || true
    docker compose --project-name "$project_name" logs --no-color --tail 200 || true
  fi
  if ! docker compose --project-name "$project_name" down --volumes --remove-orphans --rmi local; then
    echo "Isolated E2E cleanup failed for Compose project $project_name." >&2
    if [ "$status" -eq 0 ]; then
      status=1
    fi
  fi
  exit "$status"
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
cd "$repository_root"

docker compose --project-name "$project_name" config --quiet
docker compose --project-name "$project_name" build api worker web
docker compose --project-name "$project_name" up --detach --wait --wait-timeout 300 postgres redis minio mailpit clamav
docker compose --project-name "$project_name" up --detach minio-init
init_container=$(docker compose --project-name "$project_name" ps --all --quiet minio-init)
if [ -z "$init_container" ]; then
  echo "Compose did not create the object-storage initializer." >&2
  exit 1
fi
init_exit=$(docker wait "$init_container")
if [ "$init_exit" -ne 0 ]; then
  echo "Object-storage initialization failed with exit code $init_exit." >&2
  exit "$init_exit"
fi
if [ -n "$expected_migration_head" ]; then
  migration_heads=$(docker compose --project-name "$project_name" run --rm --no-deps api alembic -c packages/backend/alembic.ini heads)
  printf '%s\n' "$migration_heads"
  assert_migration_head_output "$migration_heads" "$expected_migration_head" "Phase $verification_phase migration-head lookup"
fi
docker compose --project-name "$project_name" run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
docker compose --project-name "$project_name" run --rm --no-deps api alembic -c packages/backend/alembic.ini downgrade "$rollback_revision"
docker compose --project-name "$project_name" run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
if [ -n "$expected_migration_head" ]; then
  current_migration=$(docker compose --project-name "$project_name" run --rm --no-deps api alembic -c packages/backend/alembic.ini current)
  printf '%s\n' "$current_migration"
  assert_migration_head_output "$current_migration" "$expected_migration_head" "Phase $verification_phase current-migration lookup"
fi
(cd packages/backend && uv run --package careeros-backend pytest tests/integration)
docker compose --project-name "$project_name" up --detach --wait --wait-timeout 180 --no-deps api worker worker-scheduler web web-edge
worker_container=$(docker compose --project-name "$project_name" ps --quiet worker)
if [ -z "$worker_container" ]; then
  echo "Compose did not create the document worker." >&2
  exit 1
fi
scheduler_container=$(docker compose --project-name "$project_name" ps --quiet worker-scheduler)
if [ -z "$scheduler_container" ]; then
  echo "Compose did not create the worker scheduler." >&2
  exit 1
fi
scheduler_health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$scheduler_container")
if [ "$scheduler_health" != "healthy" ]; then
  echo "Worker scheduler health is $scheduler_health, expected healthy Celery Beat process state." >&2
  exit 1
fi
advertised_pages=$(curl --fail --silent "http://127.0.0.1:${WEB_PORT}/api/v1/guest/resume-health/upload-policy" | node -e 'let input=""; process.stdin.on("data", chunk => input += chunk); process.stdin.on("end", () => process.stdout.write(String(JSON.parse(input).maxPages)));')
worker_pages=$(docker exec "$worker_container" python -c 'from careeros_worker.config import get_settings; print(get_settings().document_max_pages)')
if [ "$advertised_pages" != "$DOCUMENT_MAX_PAGES" ] || [ "$worker_pages" != "$advertised_pages" ]; then
  echo "API/worker page-limit policy mismatch: configured=$DOCUMENT_MAX_PAGES advertised=$advertised_pages worker=$worker_pages" >&2
  exit 1
fi
if [ "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$worker_container")" != "true" ]; then
  echo "Document worker root filesystem is not read-only." >&2
  exit 1
fi
if ! docker inspect --format '{{json .HostConfig.CapDrop}}' "$worker_container" | grep -q '"ALL"'; then
  echo "Document worker did not drop all Linux capabilities." >&2
  exit 1
fi
if ! docker inspect --format '{{json .HostConfig.SecurityOpt}}' "$worker_container" | grep -q 'no-new-privileges'; then
  echo "Document worker does not enforce no-new-privileges." >&2
  exit 1
fi
if [ "$(docker inspect --format '{{.HostConfig.PidsLimit}}' "$worker_container")" -le 0 ] ||
   [ "$(docker inspect --format '{{.HostConfig.Memory}}' "$worker_container")" -le 0 ] ||
   [ "$(docker inspect --format '{{.HostConfig.NanoCpus}}' "$worker_container")" -le 0 ]; then
  echo "Document worker CPU, memory, and PID limits must be explicit." >&2
  exit 1
fi
if ! docker inspect --format '{{json .HostConfig.Tmpfs}}' "$worker_container" | grep -q '"/tmp/careeros"'; then
  echo "Document worker requires a bounded private temporary filesystem." >&2
  exit 1
fi
if [ "$(docker inspect --format '{{len .NetworkSettings.Networks}}' "$worker_container")" -ne 1 ]; then
  echo "Document worker must attach only to the internal backend network." >&2
  exit 1
fi
anonymous_status=$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:${MINIO_API_PORT}/${S3_BUCKET}")
if [ "$anonymous_status" != "403" ]; then
  echo "Private document bucket returned HTTP $anonymous_status to an anonymous request." >&2
  exit 1
fi
docker compose --project-name "$project_name" stop postgres
not_ready_status=$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:${API_PORT}/ready")
if [ "$not_ready_status" != "503" ]; then
  echo "API readiness returned HTTP $not_ready_status while PostgreSQL was unavailable." >&2
  exit 1
fi
docker compose --project-name "$project_name" start postgres
docker compose --project-name "$project_name" up --detach --wait --wait-timeout 120 postgres
recovered=false
attempt=0
while [ "$attempt" -lt 30 ]; do
  recovered_status=$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:${API_PORT}/ready")
  if [ "$recovered_status" = "200" ]; then
    recovered=true
    break
  fi
  attempt=$((attempt + 1))
  sleep 2
done
if [ "$recovered" != "true" ]; then
  echo "API readiness did not recover after PostgreSQL restarted." >&2
  exit 1
fi
run_browser_journeys
