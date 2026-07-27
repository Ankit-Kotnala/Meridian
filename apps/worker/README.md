# CareerOS Worker

Celery worker backed by Redis for isolated Resume Health document processing,
private Career Record evidence attachments, durable outbox delivery, cleanup,
Phase 9 Career Analytics refresh/outbox/reconciliation, local-only Networking
reminder materialization/reconciliation, and non-sensitive health checks. Broker
payloads contain identifiers only; document bytes, extracted content, evidence,
contact data, notes, and generated text remain in private storage and
PostgreSQL.

## Local commands

Run these from the repository root:

```bash
pnpm dev:worker    # dependency containers plus a host Celery worker
pnpm test:worker   # focused worker tests
make format-check
make lint
make typecheck
```

Registered task adapters live under
`src/careeros_worker/tasks/<bounded_context>.py`; cross-context execution fencing
and identifier-only result contracts have specifically named modules in the same
package. Runtime/provider composition remains in `runtime.py`. See
`docs/local-development.md` for the full repository map and Docker workflows.

Broker configuration is resolved in this order:

- Broker: `CELERY_BROKER_URL`, then `REDIS_URL`, then the local default.
- Result backend: `CELERY_RESULT_BACKEND`, then `RESULT_BACKEND`, then
  `REDIS_URL`, then the local default.

URLs use Pydantic secret values so they are redacted from settings
representations. Production mode rejects the known local Redis default.

The task `careeros.worker.health.ping` returns static service liveness metadata.
The container health check uses Celery's remote-control ping so it verifies a
running worker can communicate through the broker.

## Phase 7 tasks

- `careeros.worker.resume_builder.process_export` renders or deletes one
  owner-scoped export from an identifier-only message and a fenced database
  lease.
- `careeros.worker.resume_builder.dispatch_outbox` publishes bounded
  operation-typed render/delete work from the transactional outbox.
- `careeros.worker.resume_builder.reconcile_exports` recovers lost deliveries
  and expired leases, then processes due attempt-object cleanup backstops. A
  backstop is committed before each object write, cancelled atomically only for
  the verified winner, and otherwise retried or dead-lettered with safe audit
  codes.

## Phase 9 tasks

- `careeros.worker.career_analytics.process_refresh` processes one persisted
  owner-scoped refresh by UUID. It rechecks source watermarks, verifies leases,
  and never receives source content through the broker. The worker reads the
  persisted trace before logging and uses the same owned Resume Health and
  clean-attachment eligibility adapters as the API composition root.
- `careeros.worker.career_analytics.dispatch_outbox` publishes bounded
  transactional-outbox batches with UUID-only messages.
- `careeros.worker.career_analytics.reconcile` recovers expired leases and lost
  due deliveries without duplicating a completed snapshot.
- `careeros.worker.networking.process_local_reminders` advances persisted local
  reminder occurrences only. It has no email, message, URL-fetch, calendar, or
  push provider. Each occurrence and outbox row carries the originating
  validated trace ID into worker audit and structured-log context.
- `careeros.worker.networking.reconcile_local_reminders` recovers expired local
  reminder leases through content-free identifiers.

Celery Beat schedules analytics outbox/reconciliation and local-reminder
processing/reconciliation. Safe local defaults and bounds are documented in
`.env.example`: analytics attempts, lease, retry, outbox interval and
reconciliation interval; and Networking reminder lease, retry, processing
interval and reconciliation interval. The analytics lease must remain longer
than the worker hard time limit. Logs contain safe codes/counts rather than raw
career or contact content. Recurring reminders prune only safely terminal
acknowledged/cancelled occurrence and processed/cancelled outbox pairs to a
bounded retained history; retryable, leased, scheduled, and dead-letter state is
not erased to make room, and recurrence stops when the hard bound cannot be
recovered safely.
