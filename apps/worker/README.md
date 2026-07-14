# CareerOS Worker

Phase 0 Celery worker foundation backed by Redis. Only a non-sensitive health
task is registered; document processing and other business jobs arrive in later
phases.

## Local commands

```bash
uv sync --frozen
uv run celery --app careeros_worker.app:celery_app worker --loglevel=INFO
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
