# CareerOS web

Next.js App Router frontend for the CareerOS Phase 0 public experience and fictional product preview.

## Commands

Run these from the repository root:

```bash
pnpm --filter @careeros/web dev
pnpm --filter @careeros/web lint
pnpm --filter @careeros/web typecheck
pnpm --filter @careeros/web test
pnpm --filter @careeros/web build
pnpm --filter @careeros/web test:e2e
```

The health endpoint is `GET /api/health`. `/dashboard` contains fictional demo fixtures only; authentication and real user data are intentionally deferred to Phase 1.

The Dockerfile expects `apps/web` as its build context:

```bash
docker build -t careeros-web apps/web
docker run --rm -p 3000:3000 careeros-web
```
