# CareerOS Worker

Celery worker backed by Redis for isolated Resume Health document processing,
private Career Record evidence attachments, durable outbox delivery, cleanup,
and non-sensitive health checks. Broker payloads contain identifiers only;
document bytes and extracted content remain in private storage and PostgreSQL.

## Local commands

```bash
uv sync --frozen --all-packages --all-groups
cd apps/worker
uv run celery --app careeros_worker.app:celery_app worker --loglevel=INFO --queues=default,resume-health,career-record,maintenance
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Broker configuration is resolved in this order:

- Broker: `CELERY_BROKER_URL`, then `REDIS_URL`, then the local default.
- Result backend: `CELERY_RESULT_BACKEND`, then `RESULT_BACKEND`, then
  `REDIS_URL`, then the local default.

URLs use Pydantic secret values so they are redacted from settings
representations. Production mode rejects the known local Redis default.

The task `careeros.worker.health.ping` returns static service liveness metadata.
The container health check uses Celery's remote-control ping so it verifies a
running worker can communicate through the broker.
