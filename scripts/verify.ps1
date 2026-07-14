$ErrorActionPreference = "Stop"

pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build

Push-Location "apps/api"
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
Pop-Location

Push-Location "apps/worker"
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
Pop-Location

docker compose config --quiet
Write-Host "CareerOS Phase 0 verification passed."
