# Container infrastructure

Application Dockerfiles live beside each service so their build contexts stay small. The root `docker-compose.yml` composes PostgreSQL with pgvector, Redis, MinIO, the API, worker, and web application. Mailpit and ClamAV are opt-in profiles.

Production images must use immutable tags or digests, drop privileges, and receive secrets from the deployment platform. Compose defaults are local-only.
