# @careeros/contracts

This package is the TypeScript view of the FastAPI wire contract. The source
chain is intentionally one-way:

```text
apps/api Pydantic responses
  -> packages/contracts/openapi/careeros.openapi.json
  -> packages/contracts/src/generated/schema.d.ts
  -> typed openapi-fetch client
```

Run `pnpm contracts:generate` at the repository root after an intentional API
schema change. Run `pnpm contracts:check` to fail on OpenAPI or generated-type
drift. Do not hand-edit `src/generated/` or introduce parallel handwritten API
models. Event schemas will be added only when the first real integration event
exists.
