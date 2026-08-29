# Container infrastructure

The [`compose.yaml`](../compose.yaml) file is the supported Phase 0 local
integration entry point. It composes PostgreSQL with pgvector, Redis, MinIO, the
API, worker, and web application. Optional development or security profiles are
not evidence that a later upload or email feature is implemented.

API and worker images are built from the repository root because both deployables
install the shared `backend/core` workspace package. Their Dockerfiles may
remain beside the applications while this dependency is explicit in the build
context; moving them into this directory is structural cleanup, not a reason to
duplicate package files. Runtime images intentionally omit uv and development
dependencies, so migrations use the installed Alembic executable rather than
`uv run`.

Production images must use immutable tags or digests, drop privileges, and
receive secrets from the deployment platform. Compose defaults are local-only.
Production topology, Terraform, policies, scanner images, and operational
artifacts remain Phase 10 or feature-owned work and must not be represented by
empty scaffolding.
