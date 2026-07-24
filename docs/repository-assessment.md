# Repository assessment

Assessment date: 2026-07-14  
Workspace inspected: `G:\Resumi`

## Initial state

The workspace was empty when implementation began. A recursive file inventory
returned no files, and `.git` was absent. In particular, there were no:

- README or agent instructions;
- package manifests, lockfiles, source, or build configuration;
- environment templates, Compose files, or infrastructure;
- migrations, database models, fixtures, or seed data;
- tests, CI workflows, formatting, lint, or type-check configuration;
- existing product behavior to preserve.

This is a greenfield repository assessment, not an assertion that later
worktrees remain empty. `PLANS.md` records the current Phase 0 state.

## Inspection evidence

The initial read-only inspection used the equivalent of:

```powershell
Get-ChildItem -Force
rg --files -uu
Test-Path .git
```

`rg --files -uu` produced no paths, and `Test-Path .git` was false. The complete
attached brief (2,076 lines) was read in bounded sections so terminal truncation
did not omit requirements.

The subsequent repository-architecture addendum (1,457 lines) was also read in
full on 2026-07-14. It made a shared Python backend, one root uv workspace,
generated frontend contracts, thin deployable boundaries, and executable
dependency checks part of the minimum foundation. The repository is aligning to
that decision now; the earlier Phase 0 verification predates it.

## Specification conflicts and tensions

At the initial empty-repository assessment, no existing code conflicted with the
original specification. The specification itself has several tensions that
require explicit interpretation:

| Tension                                                                                        | Resolution                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The brief describes the complete product, then requires stopping after one major phase         | Build and verify only Phase 0 now; retain later work as contracts and plans, not simulated functionality                                                         |
| The reference image contains names, scores, jobs, and detailed module states                   | Use it for layout and visual hierarchy only; all preview content is isolated, fictional, and labeled                                                             |
| Phase 0 says “Database,” while the complete entity model spans later features                  | Run a healthy PostgreSQL/pgvector service and establish connection/migration infrastructure; add domain migrations with the owning feature phase                 |
| Local malware scanning is described as optional, but upload safety requires malware protection | A scanner container may be optional in Phase 0 because there is no upload; Phase 2 production upload must scan or quarantine/fail closed                         |
| “Current stable” dependencies can undermine reproducibility                                    | Select conservative stable compatible versions and commit exact pnpm/uv lockfiles                                                                                |
| Organizations are future work, yet tenant isolation is mandatory now                           | Make ownership explicit from the first persisted user table; preserve an organization/tenant extension point without forcing individuals into fake organizations |
| Guest upload has no authenticated owner                                                        | Use a short-lived opaque capability, minimal report, strict rate/size limits, and short configurable retention in Phase 2                                        |
| Semantic retrieval is suggested, while scoring must be deterministic                           | Embeddings may retrieve candidates; deterministic, versioned rules decide numeric scores and grounding eligibility                                               |
| A production LLM adapter is required, but credentials may be absent                            | Define provider interfaces and deterministic fake/local behavior; production adapters are environment-selected and never needed for tests                        |
| The dashboard preview is public in Phase 0, while the final dashboard is protected             | Keep a conspicuous fictional-preview banner and no persisted/private data; protect it in Phase 1                                                                 |

## Selected foundation architecture

- pnpm 11.13.0 workspace on the Node.js 24 LTS line.
- Next.js 16.2.11 App Router, React 19.2.7, strict TypeScript 5.9.3, and Tailwind
  CSS 4.3.2.
- Python 3.13 with uv 0.11.21; FastAPI 0.138.2, Pydantic, async
  SQLAlchemy/asyncpg, and Alembic infrastructure in one root workspace and lock.
- A shared `packages/backend` modular monolith used by thin API and worker
  applications; stable Phase 0 database, migration, configuration, and logging
  primitives live in its foundation layer.
- Celery 5.6.3 using Redis for the local broker and result backend.
- PostgreSQL with pgvector, Redis, and MinIO through Docker Compose.
- API-owned authentication in Phase 1: Argon2id, server-side sessions and rotating
  hashed refresh tokens in secure HTTP-only cookies, with a Google OAuth adapter.
- OpenAPI as the wire-contract authority, with a normalized committed artifact,
  generated TypeScript types, and a typed client wrapper beginning in Phase 0.

Major choices and their consequences are recorded in `docs/adr/`.

## Phase 0 deliverable boundary

Phase 0 establishes a runnable and testable platform seam:

- repository/package structure and pinned toolchains;
- web, API, and worker skeletons with real health behavior;
- local PostgreSQL, Redis, and MinIO;
- environment contract, Make targets, Compose, CI, and initial test runners;
- shared backend/contracts/UI/design-token/configuration/fixture boundaries;
- architecture checks for backend and frontend dependency direction;
- product, architecture, API, scoring, AI, security, test, and governance docs.

Phase 0 does not claim registration, upload, parsing, scoring, generation,
evidence persistence, export, tracking, billing, administration, or production
deployment. Even when a target or interface is reserved for those capabilities,
it is not an implemented feature.

## Assumptions

1. The product is private, pre-production, and single-region during foundation
   work; regional residency is a production design input, not a decided policy.
2. Local credentials are disposable and non-production. Production secrets will
   come from a managed secret store.
3. No real person's private data is needed for development or tests. Fixtures are
   fictional and clearly marked.
4. Object storage is private by default. The browser will use short-lived,
   operation-scoped signed URLs rather than public objects.
5. PostgreSQL is the system of record; Redis is ephemeral coordination/cache and
   never the sole durable copy of career data.
6. The worker can be deployed with stricter network and resource policy than the
   API, even though local Compose shares a development network.
7. WCAG 2.2 AA applies to public and authenticated product surfaces.
8. English is the initial product language, while schemas preserve locale and
   regional resume conventions for later work.
9. Pricing amounts, quotas, retention periods, score weights, and model choices
   are configuration/versioned records, not scattered constants.
10. Production email, OAuth, AI, billing, malware scanning, OCR, taxonomy, and
    monitoring providers have not been selected.

## Risks discovered at foundation time

- There was no baseline against which to detect regressions.
- A broad roadmap creates pressure to expose placeholder pages as complete.
- Python 3.13 and Node 24 require dependency/container compatibility checks on
  every lockfile update.
- Redis as a local Celery broker is simple but does not settle production queue
  durability requirements.
- A healthy Compose stack proves local integration only; it does not prove tenant
  isolation, hostile-file safety, grounding, export fidelity, restore, or scale.
- The product will handle highly sensitive career and contact data, making logs,
  backups, provider payloads, and administrator access part of the security
  boundary.

The mitigations and owners are maintained in `PLANS.md` and
`docs/security-threat-model.md`.

## Required verification

The assessment itself is verified by the inventories above. The following checks
passed for the earlier foundation baseline and are preserved in `PLANS.md` as
historical evidence:

```sh
make setup
make dev
docker compose config --quiet
docker compose ps
make format-check
make lint
make typecheck
make test
make verify
```

Health probes covered the web, API, worker, PostgreSQL, Redis, and MinIO. A missing
tool, skipped suite, placeholder target, or failed health dependency must reopen
the affected phase.

The aligned working tree passes those checks together with the root uv workspace,
forbidden-import architecture tests, normalized OpenAPI/generated-schema drift
checks, single-head migration verification, and root-context application image
builds. Hosted CI run `29360385761` verified Phase 0 implementation commit
`9558f33`, satisfying the prerequisite for Phase 1.
