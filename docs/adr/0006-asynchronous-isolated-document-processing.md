# ADR 0006: Asynchronous, isolated document processing

- Status: Accepted
- Date: 2026-07-14
- Deciders: Security and Engineering

## Context

Malware scanning, PDF/DOCX parsing, OCR, analysis, model calls, rendering, and
round-trip verification are slow, failure-prone, potentially expensive, and
exposed to hostile content. Running them in an HTTP request or web process would
increase timeout, denial-of-service, and remote-code-execution blast radius.

## Decision

Run long-running or hostile work through Celery workers and durable processing-job
records. Local development uses Redis as broker/result backend and MinIO private
objects. Each job has user/tenant ownership, idempotency key, explicit state,
timeout, bounded classified retry, dead-letter behavior, trace ID, progress where
useful, and provider usage/cost metadata.

Production file workers run as non-root, disposable, resource-limited processes
with a read-only base filesystem, randomized temporary directory, cleanup on all
paths, and no unnecessary network. Uploaded content is never executed. Admission
validates signature/type/size/page/expansion and malware state before parsing.

The API enqueues references to durable authorized records, not raw credentials or
entire documents. A worker reloads ownership/state. Generated files are linked to
an immutable input version, hashed, parsed again, and blocked or warned according
to verification policy.

## Consequences

### Positive

- HTTP latency is bounded and progress/failure can be represented honestly.
- Parser/render/provider failures are isolated and observable.
- Idempotency and durable state control duplicates, retries, and cost.
- Worker network/resource policy can be stricter than the API.

### Costs and risks

- Distributed state, outbox/enqueue consistency, cancellation, retry
  classification, and dead-letter operations add complexity.
- Redis local behavior does not establish production durability guarantees.
- Parser sandboxing reduces but does not eliminate zero-day risk.
- Temporary/object/provider artifacts complicate complete deletion.

## Alternatives considered

- **Process synchronously in the API:** rejected for hostile-input blast radius,
  timeouts, and resource contention.
- **Run parsing in the browser:** rejected for inconsistent libraries, privacy,
  inability to enforce scanning, and lack of authoritative round-trip verification.
- **Serverless function per task from Phase 0:** potentially useful later but
  premature without duration/resource/region requirements; provider abstraction
  and job records keep that path open.

## Implementation notes

Phase 0 implements only worker connectivity/health. Phase 2 implements upload,
quarantine, scan/parse/OCR/analyze states and hostile fixtures. Phases 5–8 add job
import, AI, render, verification, email, and aggregation tasks. Production queue,
sandbox, egress, autoscaling, and dead-letter operations are Phase 10 release
decisions with load/failure tests.
