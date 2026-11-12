# Production-features model wins half its games against ValueFunctionPlayer

The production-features model, with production-pip openings, four search simulations, and
exploration off, won **1,025 of 2,000 games (51.25%)** against three Catanatron
`ValueFunctionPlayer` opponents on seeds 80000–81999. The 95% Wilson interval is
**49.09%–53.40%**. The preregistered decision in
[issue 12](../../../.scratch/strategy-lab/issues/12-reach-thirty-percent.md) is
**reaches 30%**: the completed-game and attrition-as-losses lower bounds are both above 0.30.
All 2,000 games completed, with no drops, technical failures, or missing games. A seat-balanced
fair share at this table is 25%.

## What changed

Earlier models compared Positions in different turn phases and could not see production. Their
Policy ended its turn where `ValueFunctionPlayer` built (issue 12, Diagnosis).

- The Observation keeps Catanatron's 1,002 sample columns and appends 188 public columns:
  effective production, reachability at two roads, expansion, and port distance.
- Training zeroes the turn-phase columns, so no tree splits on them.
- Corpus: 10,000 `ValueFunctionPlayer` self-play games, seeds 100000–109999, 1,102,316 rows.
- Training: train split only, 400 rounds of 63 leaves.

The model was installed through the calibration gate ([calibration.txt](./calibration.txt)): on
961 untouched validation games every game-level 95% Brier interval was below zero against
`constant(1/4)`, `vp-share`, and the previous value-table model.

## Artifacts and provenance

- [plan.json](./plan.json): the preregistered configuration, committed in `dd48efe` before play.
- [report.json](./report.json) and [report.md](./report.md): the Strength Report.
- [verification.json](./verification.json): decision, environment, hashes, and checks.

The source tree was clean at **dd48efe0b48db63b6f36bf469819b8cef9120c2c**. Eight workers took
**1,958 seconds** on macOS arm64, Python 3.11.6, Catanatron 3.3.0 at its pinned commit,
LightGBM 4.7.0, NumPy 2.4.6. A four-game pilot on seeds 82000–82003 completed 4/4 in 14 seconds;
its outcomes were not read. No interim outcomes were inspected and nothing was retuned.

Independent checks verified the seeds, 500 games per Seat, all Seats in each four-game block,
Policy identities, source commit, engine pin, model and sidecar hashes, winner counts, Seat
denominators, and the Wilson interval. A second report generation was byte-identical. The first
scheduling block replayed identically in a fresh process with hash seed 1.

## Reproduce

```bash
export PYTHONHASHSEED=0
uv run catan-coach lab run .scratch/strategy-lab/plans/12-production-features.json \
  --out data/experiments/production-features-vs-value --workers 8
uv run catan-coach lab report data/experiments/production-features-vs-value \
  --json docs/experiments/production-features/report.json \
  --markdown docs/experiments/production-features/report.md
```

Rebuild the model with:

```bash
uv run catan-coach corpus --games 10000 --seed 100000 --players value \
  --out data/corpora/vfp-v2 --workers 6
uv run catan-coach train --corpus data/corpora/vfp-v2 --out data/iter1/model.txt \
  --mask-phase --rounds 400 --leaves 63
uv run catan-coach calibrate --model data/iter1/model.txt --corpus data/corpora/vfp-v2 \
  --installed <previous model.txt> --out model.txt --keep-candidate-map
```

## Interpretation and limitations

Candidate wins by Seat were 280, 256, 243, and 246 of 500; diagnostics only. In wins the
candidate built 2.43 post-setup settlements and 3.18 cities; opponents averaged 2.14 and 1.44.
These are descriptive.

The 200-game screen on seeds 70000–70199 gave 86 wins (43%) with the uncalibrated trees. The
confirmed run used the calibrated map, which changes search averages. The screen did not
support any claim. This is one Opponent Population, one engine, and one search budget, with no
human-game validation. The search tests and play are slower than before: each Observation now
costs about 1.5 ms more.
