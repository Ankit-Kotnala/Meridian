#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
project_name=${REZUMI_E2E_PROJECT_NAME:-rezumi-e2e-$$}
case "$project_name" in
  rezumi-e2e-*) ;;
  *)
    echo "REZUMI_E2E_PROJECT_NAME must begin with rezumi-e2e-." >&2
    exit 2
    ;;
esac

verification_phase=${REZUMI_E2E_PHASE:-1}
expected_migration_head=${REZUMI_EXPECTED_MIGRATION_HEAD:-20260823_0017}
case "$verification_phase" in
  1)
    rollback_revision=20260714_0001
    ;;
  2)
    rollback_revision=20260715_0002
    ;;
  3)
    rollback_revision=20260715_0003
    ;;
  4)
    rollback_revision=20260715_0004
    ;;
  5)
    rollback_revision=20260719_0005
    ;;
  6)
    rollback_revision=20260719_0006
    ;;
  7)
    rollback_revision=20260719_0007
    ;;
  8)
    rollback_revision=20260719_0008
    ;;
  9)
    rollback_revision=20260724_0009
    ;;
  *)
    echo "REZUMI_E2E_PHASE must be 1, 2, 3, 4, 5, 6, 7, 8, or 9." >&2
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
export POSTGRES_USER=rezumi
export POSTGRES_PASSWORD=change-me-local-only
export POSTGRES_DB=rezumi
export DATABASE_URL=postgresql+asyncpg://rezumi:change-me-local-only@postgres:5432/rezumi
export REDIS_URL=redis://redis:6379/0
export CELERY_BROKER_URL=redis://redis:6379/0
export CELERY_RESULT_BACKEND=redis://redis:6379/1
export MINIO_ROOT_USER=rezumi-local
export MINIO_ROOT_PASSWORD=change-me-local-only
export S3_ENDPOINT_URL=http://minio:9000
export S3_REGION=us-east-1
export S3_BUCKET=rezumi-documents
export S3_APP_ACCESS_KEY_ID=rezumi-e2e-app
export S3_APP_SECRET_ACCESS_KEY=change-me-local-only-e2e-storage-secret
export S3_USE_SSL=false
export MALWARE_SCANNER_PROVIDER=clamav
export CLAMAV_HOST=clamav
export CLAMAV_TIMEOUT_SECONDS=30
export DOCUMENT_TEMP_ROOT=/tmp/rezumi
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
export AUTH_TOKEN_PEPPER="${REZUMI_E2E_AUTH_TOKEN_PEPPER:-change-me-local-only-e2e-auth-token-pepper}"
export RESUME_CAPABILITY_PEPPER=change-me-local-only-e2e-resume-capability-pepper
export BFF_CLIENT_SIGNAL_SECRET=change-me-local-only-e2e-bff-client-signal-secret
export API_BFF_CLIENT_SIGNAL_SECRET=change-me-local-only-e2e-bff-client-signal-secret
export COOKIE_SECURE=false
export EMAIL_PROVIDER=smtp
export EMAIL_FROM_ADDRESS=no-reply@rezumi.local
export SMTP_HOST=mailpit
export SMTP_PORT=1025
export SMTP_USERNAME=
export SMTP_PASSWORD=
export SMTP_START_TLS=false
export GOOGLE_OAUTH_ENABLED=false
export GOOGLE_CLIENT_ID=
export GOOGLE_CLIENT_SECRET=
export GOOGLE_REDIRECT_URI="${PUBLIC_APP_URL}/api/v1/auth/google/callback"
export AI_PROVIDER=deterministic
export PLAYWRIGHT_EXTERNAL_SERVER=1
export PLAYWRIGHT_E2E_MODE=full-stack
export PLAYWRIGHT_BASE_URL="$PUBLIC_APP_URL"
export PLAYWRIGHT_MAILPIT_URL="http://127.0.0.1:${MAILPIT_HTTP_PORT}"
export MONGODB_ENABLED=false
export REZUMI_MONGODB_ENABLED=false
export REZUMI_TEST_DATABASE_URL="postgresql+asyncpg://rezumi:change-me-local-only@127.0.0.1:${POSTGRES_PORT}/rezumi"
export REZUMI_TEST_REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/15"
export REZUMI_TEST_S3_ENDPOINT_URL="$S3_PUBLIC_ENDPOINT_URL"
export REZUMI_TEST_S3_REGION="$S3_REGION"
export REZUMI_TEST_S3_BUCKET="$S3_BUCKET"
export REZUMI_TEST_S3_ACCESS_KEY_ID="$S3_APP_ACCESS_KEY_ID"
export REZUMI_TEST_S3_SECRET_ACCESS_KEY="$S3_APP_SECRET_ACCESS_KEY"
export REZUMI_TEST_CLAMAV_HOST=127.0.0.1
export REZUMI_TEST_CLAMAV_PORT="$CLAMAV_PORT"

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

wait_service_healthy() {
  service=$1
  timeout_seconds=${2:-900}
  poll_seconds=${3:-10}
  deadline=$(( $(date +%s) + timeout_seconds ))
  last_status=missing

  while [ "$(date +%s)" -lt "$deadline" ]; do
    container=$(docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" ps --quiet "$service")
    if [ -n "$container" ]; then
      last_status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container")
      if [ "$last_status" = healthy ]; then
        return 0
      fi
    fi
    sleep "$poll_seconds"
  done

  echo "$service did not become healthy within ${timeout_seconds}s; last health status was '$last_status'." >&2
  return 1
}

wait_container_exit_code() {
  container_id=$1
  attempts=${2:-10}
  delay_seconds=${3:-2}
  attempt=1
  last_failure="no response"

  while [ "$attempt" -le "$attempts" ]; do
    if wait_output=$(docker wait "$container_id" 2>&1); then
      printf '%s\n' "$wait_output"
      return 0
    fi
    last_failure=$wait_output
    if [ "$attempt" -lt "$attempts" ]; then
      sleep "$delay_seconds"
    fi
    attempt=$((attempt + 1))
  done

  echo "Container wait failed after $attempts attempts: $last_failure" >&2
  return 1
}

run_browser_journeys() {
  case "$verification_phase" in
    1)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts
      ;;
    2)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts
      ;;
    3)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts
      ;;
    4)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts \
        e2e/role-readiness-journey.spec.ts
      ;;
    5)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts \
        e2e/role-readiness-journey.spec.ts \
        e2e/job-match-journey.spec.ts
      ;;
    6)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts \
        e2e/role-readiness-journey.spec.ts \
        e2e/job-match-journey.spec.ts \
        e2e/change-studio-journey.spec.ts
      ;;
    7)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts \
        e2e/role-readiness-journey.spec.ts \
        e2e/job-match-journey.spec.ts \
        e2e/change-studio-journey.spec.ts \
        e2e/resume-builder-journey.spec.ts
      ;;
    8)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts \
        e2e/role-readiness-journey.spec.ts \
        e2e/job-match-journey.spec.ts \
        e2e/change-studio-journey.spec.ts \
        e2e/resume-builder-journey.spec.ts \
        e2e/application-workspace-journey.spec.ts
      ;;
    9)
      npm exec --workspace=@rezumi/web -- playwright test \
        e2e/auth-journey.spec.ts \
        e2e/resume-health-journey.spec.ts \
        e2e/career-record-journey.spec.ts \
        e2e/role-readiness-journey.spec.ts \
        e2e/job-match-journey.spec.ts \
        e2e/change-studio-journey.spec.ts \
        e2e/resume-builder-journey.spec.ts \
        e2e/application-workspace-journey.spec.ts \
        e2e/phase9-career-workspace-journey.spec.ts
      ;;
  esac
}

cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
  if [ "$status" -ne 0 ]; then
    docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" ps --all || true
    docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" logs --no-color --tail 200 || true
  fi
  if ! docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" down --volumes --remove-orphans --rmi local; then
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

docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" config --quiet
for service in api worker web web-edge; do
  docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" build "$service"
done
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" up --detach --wait --wait-timeout 900 postgres redis minio mailpit clamav
wait_service_healthy clamav 900 10
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" up --detach minio-init
init_container=$(docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" ps --all --quiet minio-init)
if [ -z "$init_container" ]; then
  echo "Compose did not create the object-storage initializer." >&2
  exit 1
fi
init_exit=$(wait_container_exit_code "$init_container")
if [ "$init_exit" -ne 0 ]; then
  echo "Object-storage initialization failed with exit code $init_exit." >&2
  exit "$init_exit"
fi
if [ -n "$expected_migration_head" ]; then
  migration_heads=$(docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" run --rm --no-deps api alembic -c backend/core/alembic.ini heads)
  printf '%s\n' "$migration_heads"
  assert_migration_head_output "$migration_heads" "$expected_migration_head" "Phase $verification_phase migration-head lookup"
fi
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" run --rm --no-deps api alembic -c backend/core/alembic.ini downgrade "$rollback_revision"
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" run --rm --no-deps api alembic -c backend/core/alembic.ini upgrade head
if [ -n "$expected_migration_head" ]; then
  current_migration=$(docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" run --rm --no-deps api alembic -c backend/core/alembic.ini current)
  printf '%s\n' "$current_migration"
  assert_migration_head_output "$current_migration" "$expected_migration_head" "Phase $verification_phase current-migration lookup"
fi
(cd backend/core && uv run --package rezumi-backend pytest tests/integration)
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" up --detach --wait --wait-timeout 180 --no-deps api worker worker-scheduler web web-edge
worker_container=$(docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" ps --quiet worker)
if [ -z "$worker_container" ]; then
  echo "Compose did not create the document worker." >&2
  exit 1
fi
scheduler_container=$(docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" ps --quiet worker-scheduler)
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
worker_pages=$(docker exec "$worker_container" python -c 'from rezumi_worker.config import get_settings; print(get_settings().document_max_pages)')
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
if ! docker inspect --format '{{json .HostConfig.Tmpfs}}' "$worker_container" | grep -q '"/tmp/rezumi"'; then
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
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" stop postgres
not_ready_status=$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:${API_PORT}/ready")
if [ "$not_ready_status" != "503" ]; then
  echo "API readiness returned HTTP $not_ready_status while PostgreSQL was unavailable." >&2
  exit 1
fi
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" start postgres
docker compose -f infra/compose.yaml --project-directory . --project-name "$project_name" up --detach --wait --wait-timeout 120 postgres
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
