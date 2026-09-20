# Catan Coach

Scores every legal Action in a Catan Position by Win Probability. See [README.md](./README.md)
for setup and [CONTEXT.md](./CONTEXT.md) for the vocabulary.

## Working in this repo

- `src/catan_coach/engine/` is the only package allowed to import `catanatron`. Keep the seam.
- `src/catan_coach/domain/` must stay pure — no engine imports, no I/O.
- No model is adopted without beating a baseline through the calibration harness.
- Run `uv run pytest -m "not engine"` for the fast loop; `uv run pytest` before committing.
- `uv run ruff format . && uv run ruff check . && uv run mypy` must be clean.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, written as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
