# Opening-production Policy loses against this Opponent Population

Generation 7 with four search simulations, and with each initial settlement chosen by production
pips, won **65 of 2,000 games (3.25%)** against three Catanatron `ValueFunctionPlayer`
opponents. The 95% Wilson interval is **2.5581%–4.1212%**. The preregistered decision is
**loses**: both the completed-game upper bound and the attrition-as-wins upper bound are below
25%. All 2,000 games completed, with zero drops, technical failures, or missing games, so both
attrition extremes equal the completed result.

This is the changed Policy named in
[issue 10](../../../.scratch/strategy-lab/issues/10-improve-policy-after-strength-audit.md).
Roads and every later Action still follow the installed model. The installed model is unchanged;
Calibration remains its adoption gate. A strength result does not adopt a model.

The earlier [generation-7 audit](../generation-7-vs-value/README.md) used seeds 20000–21999 and
the unmodified Policy. This run uses seeds 40000–41999. The two win counts are separate
experiments. Their difference is not a paired estimate of the opening rule.

## Artifacts and provenance

- [plan.json](./plan.json): portable copy of the preregistered configuration, committed before play.
- [report.json](./report.json): full Strength Report, including every Behavior Profile aggregate.
- [report.md](./report.md): deterministic CLI report; percentages there are rounded for display.
- [verification.json](./verification.json): decision, environment, elapsed time, engine pin,
  source/model/sidecar hashes, artifact hashes, and independent verification results.

The source tree was clean at **38b05bea0e560c56e340a208b7d50dce59e4b9a1**.
Eight workers completed the run in **697 seconds** on macOS arm64 with Python 3.11.6,
Catanatron 3.3.0 at its pinned commit, LightGBM 4.7.0, and NumPy 2.4.6.
The plan uses seeds **40000–41999**, outside corpus seeds 0–7999, the generation-7 audit
20000–21999, and the reserved Intervention range 30000–33999. It assigns exactly 500 games to
each candidate Seat. Each four-game block contains every Seat once.

A four-game runtime pilot used seeds 42000–42003 and finished in 4 seconds on 4 workers, with
4 completions and no terminal failures. Only completion and runtime were recorded before this
run. Pilot win outcomes were not read, did not change the plan, and are excluded from this report.
No interim win outcomes from the final run were inspected, and no early stopping occurred.

## Reproduce

Run from the repository root at the source commit above with a clean tree:

```bash
export PYTHONHASHSEED=0
uv sync
uv run pytest -m "not engine"
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy
npm --prefix web ci
npm --prefix web test -- --run
npm --prefix web run build
uv run catan-coach lab run .scratch/strategy-lab/plans/10-opening-production.json \
  --out data/experiments/generation-7-opening-production --workers 8
```

The local raw artifacts remain in untracked `data/experiments/generation-7-opening-production/`:
a frozen `plan.json`, 2,000 game documents under `games/`, and no failure documents.
The frozen plan contains resolved local model paths; its byte hash therefore depends on the
checkout location. Game and result identities use model content hashes rather than those paths.

Regenerate the JSON and Markdown directly from stored results, without playing:

```bash
uv run catan-coach lab report data/experiments/generation-7-opening-production \
  --json docs/experiments/generation-7-opening-production/report.json \
  --markdown docs/experiments/generation-7-opening-production/report.md
```

A second report generation was byte-for-byte identical. Independent checks verified all seeds,
Seat counts and scheduling blocks, source commits, engine pins, Policy and model identities,
winner counts, Seat denominators, and the Wilson interval. All four games in the first scheduling
block, one per Seat, were replayed in a fresh process with hash seed 1 and matched the complete
stored game documents from the eight-worker run with hash seed 0. The raw-artifact SHA-256 in
`verification.json` hashes sorted relative file names, a NUL byte, then the file bytes, covering
`plan.json`, `games/*.json`, and `failures/**/*.json`. Raw files stay local.

## Interpretation and limitations

Candidate wins by Seat were **18, 18, 15, 14** out of 500 games each. These are secondary
diagnostics; no Seat-specific significance claim is made. There is no attrition to concentrate
by Policy or Seat.

In its 1,935 losses the candidate's opening production was 21.90 pips and 3.52 distinct
resources, with an adjacent port in 4.65% of those games. It built an average of 0.20 post-setup
settlements and 1.38 cities. Across all completed games the opponents averaged 19.81 opening
pips, 4.72 distinct resources, an adjacent port on 7.57% of Seats, 2.66 post-setup settlements,
and 1.76 cities. The 65 wins had 21.89 opening pips, 4.38 distinct resources, and an adjacent
port in 3.08% of games. The report's settlement counts are post-setup; the two setup settlements
are recorded as opening pips, resources, and port adjacency.

These are descriptive associations from this sample. Opening pips are higher than the opponents'
in both the wins and the losses, which is what the settlement rule selects. Distinct resources
and port adjacency stay lower in the losses. Post-setup expansion stays rare in the losses.
None of these profiles identifies why the Policy lost, and the win subgroup is too small for a
strategic rule.

This is one simulated Opponent Population, one engine, one model generation, one search budget,
and one opening rule. There is no human-game validation and no universal strength rating.
No search setting or model was retuned after inspecting outcomes. The settlement/city experiment
remains unrun and must not be compared as though only a preference changed.
