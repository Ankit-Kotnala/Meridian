#!/bin/sh
set -eu

job_delivery_provider="${REZUMI_JOB_DELIVERY_PROVIDER:-${JOB_DELIVERY_PROVIDER:-celery}}"

if [ "$job_delivery_provider" = "qstash" ]; then
  exec python -m uvicorn rezumi_worker.server:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log
fi

exec celery \
  --app rezumi_worker.app:celery_app \
  worker \
  --loglevel=INFO \
  --queues=default,resume-health,resume-builder,career-record,maintenance
