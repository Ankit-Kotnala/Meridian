# @rezumi/contracts

This package is the TypeScript view of the FastAPI wire contract. The source
chain is intentionally one-way:

```text
backend/api Pydantic responses
  -> shared/contracts/openapi/rezumi.openapi.json
  -> shared/contracts/src/generated/schema.ts
  -> typed openapi-fetch client
```

Run `npm run contracts:generate` at the repository root after an intentional API
schema change. Run `npm run contracts:check` to fail on OpenAPI or generated-type
drift. Do not hand-edit `src/generated/` or introduce parallel handwritten API
models. Event schemas will be added only when the first real integration event
exists.
