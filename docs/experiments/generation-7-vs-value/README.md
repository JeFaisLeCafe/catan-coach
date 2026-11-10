# Generation 7 loses against this Opponent Population

Generation 7 with four search simulations won **12 of 2,000 games (0.60%)** against three
Catanatron `ValueFunctionPlayer` opponents. The 95% Wilson interval is **0.3436%–1.0458%**.
The preregistered decision is **loses**: both the completed-game upper bound and the
attrition-as-wins upper bound are below 25%. All 2,000 games completed, with zero drops,
technical failures, or missing games, so both attrition extremes equal the completed result.

This establishes weak play against this declared Opponent Population under this plan. It does
not establish performance against humans or other Policies. The installed model is unchanged;
Calibration remains its adoption gate. Policy improvement is the next step before generating
more self-play from generation 7; see [issue 10](../../../.scratch/strategy-lab/issues/10-improve-policy-after-strength-audit.md).

## Artifacts and provenance

- [plan.json](./plan.json): portable copy of the preregistered configuration, committed before play.
- [report.json](./report.json): full Strength Report, including every Behavior Profile aggregate.
- [report.md](./report.md): deterministic CLI report; percentages there are rounded for display.
- [verification.json](./verification.json): decision, environment, elapsed time, engine pin,
  source/model/sidecar hashes, artifact hashes, and independent verification results.

The source tree was clean at **26378264ba6681fa675bf14765f03c0d020af92c**.
Eight workers completed the run in **618 seconds** on macOS arm64 with Python 3.11.6,
Catanatron 3.3.0 at its pinned commit, LightGBM 4.7.0, and NumPy 2.4.6.
The plan uses seeds **20000–21999**, outside known Corpus seeds 0–7999, and assigns exactly
500 games to each candidate Seat. Each four-game block contains every Seat once.

Two earlier 2,000-game attempts failed fresh-process replay checks and are excluded from this
strength decision. Their counts, local locations, and the correction frozen before the final run
are disclosed in the [replay correction note](../generation-7-replay-correction.md) and
`verification.json`. The final source sorts set-backed legal Actions before baseline tie-breaking
and seeded search sampling. No strategic setting was tuned from the discarded outcomes.

A separate four-game runtime pilot used seeds 22000–22003, one game per Seat, and finished
in approximately three seconds with four workers. Only completion and runtime were inspected
before the full run; pilot outcomes did not change the plan and are excluded from this report.
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
uv run catan-coach lab run .scratch/strategy-lab/plans/08-generation-7.json \
  --out data/experiments/generation-7-vs-value --workers 8
```

The local raw artifacts remain in untracked `data/experiments/generation-7-vs-value/`:
a frozen `plan.json`, 2,000 game documents under `games/`, and no failure documents.
The log is `data/experiments/generation-7-vs-value.log`. The frozen plan contains resolved
local model paths; its byte hash therefore depends on the checkout location. Game/result
identities use model content hashes rather than those paths.

Regenerate the JSON and Markdown directly from stored results, without playing:

```bash
uv run catan-coach lab report data/experiments/generation-7-vs-value \
  --json docs/experiments/generation-7-vs-value/report.json \
  --markdown docs/experiments/generation-7-vs-value/report.md
```

A second report generation was byte-for-byte identical. Independent checks verified all seeds,
Seat counts and scheduling blocks, source commits, engine pins, Policy/model/sidecar identities,
winner counts, Seat denominators, and all three Wilson intervals. All four games in the first
scheduling block were replayed in a fresh process with hash seed 1 and matched the complete
stored game documents from the eight-worker run with hash seed 0. The raw-artifact SHA-256 in
`verification.json` hashes sorted relative file names, a NUL byte, then the file bytes, covering
`plan.json`, `games/*.json`, and `failures/**/*.json`. Raw files stay local rather than expanding
the repository; independent reanalysis elsewhere requires regenerating or obtaining those files.

## Interpretation and limitations

Candidate wins by Seat were **4, 4, 1, 3** out of 500 games each. These are secondary diagnostics;
no Seat-specific significance claim is made. There is no attrition to concentrate by Policy or Seat.

In its 1,988 losses the candidate built an average of 0.06 post-setup settlements and 1.20 cities,
compared with 2.70 settlements and 1.75 cities per opponent Seat across all completed games.
These are descriptive associations. They motivate inspecting Action selection and expansion,
but do not show why the Policy lost. The 12-win subgroup is too small for strategic inference.

This is one simulated Opponent Population, one engine, one model generation, one search budget,
and one trading implementation. There is no human-game validation, no universal strength rating,
and no causal claim from Behavior Profiles. No strategic preference, search setting, or model was
retuned after inspecting outcomes. The separate zero-search settlement/city experiment remains
unrun and must not be compared as though only a preference changed.
