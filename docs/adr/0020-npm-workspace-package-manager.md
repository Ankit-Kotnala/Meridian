# ADR 0020: npm as the JavaScript Workspace Package Manager

Status: Accepted; amends the JavaScript-tooling portion of
[ADR 0001](0001-monorepo-and-runtime-topology.md)
Date: 2026-08-29
Deciders: Engineering

## Context

ADR 0001 chose pnpm for the JavaScript workspace (`frontend/web`, `frontend/ui`,
`frontend/design-tokens`, `frontend/eslint-config`, `frontend/typescript-config`,
`frontend/test-fixtures`, `shared/contracts`). An explicit request to standardize
on npm requires re-evaluating everything pnpm-specific in that workspace: the
`workspace:*` protocol, `pnpm-workspace.yaml`'s `allowBuilds` install-script
allowlist, and pnpm's built-in `patchedDependencies` patch mechanism.

## Decision

Use npm workspaces, declared in the root `package.json` (`workspaces` field)
instead of `pnpm-workspace.yaml`. Internal `@rezumi/*` cross-package
dependencies use `"*"` instead of `workspace:*`; npm resolves this to the local
workspace package by name, never the public registry. `overrides` migrated
directly to npm's `package.json` `overrides` field (compatible syntax).

Patches for `minimatch@3.1.5` and the nested `@redocly/openapi-core`
`minimatch@5.1.9` now go through `patch-package` (`postinstall` script) instead
of pnpm's `patchedDependencies`. Patch files are regenerated in
`patch-package`'s format (full `node_modules/...` diff paths, `+` version
separators, `++` for nested-package paths) — pnpm's patch files are not
byte-compatible with `patch-package` despite superficially similar naming.

`package-lock.json` replaces `pnpm-lock.yaml`, regenerated fresh rather than
converted; npm's dependency resolution/hoisting can legitimately differ from
pnpm's, so pinned transitive versions were re-verified (build, lint, typecheck,
test, `npm audit`) rather than assumed equivalent.

`pnpm --filter <pkg> <script>` becomes `npm run <script> --workspace=<pkg>`;
`pnpm exec` becomes `npm exec --workspace=<pkg> --`. CI's dedicated
`pnpm/action-setup` step is removed — `actions/setup-node`'s built-in
`cache: npm` is sufficient since npm ships with Node.

## Consequences

### Positive

- One package manager (npm) ships with Node itself; no separate corepack
  activation step is conceptually required, though it is still pinned
  (`packageManager` field, `corepack prepare npm@11.8.0 --activate`) for the
  same toolchain-reproducibility reason every other pinned tool is pinned.
- Fewer bespoke pnpm-specific concepts for contributors unfamiliar with pnpm.

### Costs and risks

- **Lost supply-chain control:** pnpm's `allowBuilds` blocked install/postinstall
  scripts for every dependency except an explicit allowlist (`esbuild`, `sharp`,
  `unrs-resolver`). npm has no equivalent partial allowlist — it runs every
  package's lifecycle scripts by default. This is an accepted, explicit
  regression, not an oversight.
- `patch-package` patches are keyed to a specific physical `node_modules`
  layout (notably the nested `@redocly/openapi-core++minimatch` patch). A
  future dependency bump that changes hoisting could silently stop applying a
  patch; `npm ci`'s `postinstall` fails loudly if a listed patch cannot apply,
  which is the intended fail-safe.
- Docker image build layers lose pnpm's `--filter <pkg>...` partial-install
  optimization; `npm ci` in `frontend/web/Dockerfile`'s `dependencies` stage
  installs the full workspace dependency graph (all seven packages) rather
  than just `@rezumi/web`'s transitive slice. Final runtime image contents are
  unaffected (the `runner` stage already copied the full `node_modules`
  wholesale before this change).
- `package-lock.json` is a fresh resolve, not a mechanical format conversion;
  transitive dependency versions can differ from what pnpm had resolved.

## Verification

`npm install` completes with both patches applying
(`@redocly/openapi-core/minimatch@5.1.9` and `minimatch@3.1.5`); `npm run
lint`, `npm run typecheck`, `npm run test` (JS + edge), and `npm run build`
all pass against the regenerated lockfile. `npm audit` reports one pre-existing
moderate `postcss` advisory carried over from the pinned override (not
introduced by this change).
