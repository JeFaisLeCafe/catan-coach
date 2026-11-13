# 07 — Run the first league

**What to build:** the first preregistered league and its published report.

**Blocked by:** 01, 05

**Status:** ready-for-agent

Field: generation 7, value-table, production-features (each at search 0 and 4),
`ValueFunctionPlayer`, `AlphaBetaPlayer` (depth chosen in a committed screen before the plan),
random. Seeds from `200000`. Commit the plan before play; publish `docs/experiments/league-1/`.
Pick games per Entrant from a timing pilot on seeds outside the plan's range, before committing.
