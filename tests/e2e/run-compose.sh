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

export COMPOSE_PROJECT_NAME="$project_name"
export POSTGRES_PORT="${POSTGRES_PORT:-55433}"
export REDIS_PORT="${REDIS_PORT:-6380}"
export MINIO_API_PORT="${MINIO_API_PORT:-19000}"
export MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-19001}"
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
export S3_ACCESS_KEY_ID=careeros-local
export S3_SECRET_ACCESS_KEY=change-me-local-only
export S3_USE_SSL=false
export API_BASE_URL=http://api:8000
export PUBLIC_APP_URL="http://127.0.0.1:${WEB_PORT}"
export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:${API_PORT}"
export ALLOWED_ORIGINS="[\"$PUBLIC_APP_URL\"]"
export CORS_ORIGINS="[\"$PUBLIC_APP_URL\"]"
export AUTH_TOKEN_PEPPER="${CAREEROS_E2E_AUTH_TOKEN_PEPPER:-change-me-local-only-e2e-auth-token-pepper}"
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

cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
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
docker compose --project-name "$project_name" up --detach --wait --wait-timeout 180 postgres redis minio mailpit
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
docker compose --project-name "$project_name" run --rm --no-deps api alembic -c packages/backend/alembic.ini upgrade head
(cd packages/backend && uv run --package careeros-backend pytest tests/integration)
docker compose --project-name "$project_name" up --detach --wait --wait-timeout 180 --no-deps api worker web
pnpm test:e2e
