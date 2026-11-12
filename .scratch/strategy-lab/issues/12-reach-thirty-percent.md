# 12 — Reach a 30% win rate against three ValueFunctionPlayer Seats

**Status:** resolved

**Blocked by:** 11 (resolved)

## Goal

A Policy built on an installed Win Probability model wins at least 30% of seat-balanced games
against three Catanatron `ValueFunctionPlayer` opponents, confirmed by a preregistered run.

## Rules for iterating

- **Screening** uses seeds `70000–79999` only, 200 games (50 per Seat), from the CLI
  (`catan-coach lab run ... --allow-dirty` is allowed). Screens choose what to try next. They never
  support a strength claim, and their plans live in untracked `data/screens/`.
- **Confirmation** is a 2,000-game plan committed before play, on fresh seeds from `80000` upward,
  with the issue-08 decision rule against `0.30` instead of `0.25`, run from a clean tree.
- A model is installed only through the calibration gate. Strength never installs a model.
- Each iteration is committed and logged below.

## Reference screens (seeds 70000–70199)

| candidate | wins / 200 |
| --- | ---: |
| value-table model, search 4 | 9 |
| value-table model, search 0 | 6 |
| `ValueFunctionPlayer` itself | 43 |

## Diagnosis

Over six games, a shadow `ValueFunctionPlayer` agreed with the model Policy on 29 of 180
own-turn decisions. The model most often ended its turn where the value function built a road
(66 times) or a city (4). The two successor Positions differ in `P0_HAS_ROLLED`: after End Turn
the next Seat has not rolled, while after a build the turn is still running. The model compares
Positions in different turn phases. It also has no production features: the Observation is
player counts plus raw node, edge, and tile occupancy, while the value function scores effective
production, reachable production, and ports.

## Iteration log

### Iteration 1 — public production features, phase columns hidden

- Observation: the 1,002 Catanatron sample columns, unchanged, plus 188 public columns:
  effective production, reachability at two roads, expansion, and port distance (`b86dead`).
  Older models read only their first columns (`fe492e9`).
- Corpus `data/corpora/vfp-v2`: 10,000 `ValueFunctionPlayer` self-play games, seeds
  100000–109999, stride 12, no drops, 1,102,316 rows, source `b86dead`.
- Training: train split, turn-phase columns zeroed, 400 rounds, 63 leaves (`7e8a97c`).
  Validation Brier 0.1292 against vp-share 0.1515 (skill +0.147). Not calibrated or installed.
- Screen, seeds 70000–70199, search 0: **53/200 (26.5%)**, against 6/200 for the installed
  model and 43/200 for `ValueFunctionPlayer` in the candidate Seat.
- Screen, same seeds, search 4: **86/200 (43.0%, Wilson 36.3%–49.9%)**.
- Calibration gate on 961 untouched `vfp-v2` validation games
  ([report](../../../docs/experiments/production-features/calibration.txt)): Brier difference
  against constant −0.0565 [−0.0611, −0.0519], vp-share −0.0220 [−0.0251, −0.0188], installed
  value-table −0.0151 [−0.0177, −0.0125]. Installed as `model.txt` (`c4fa251`).

## Preregistered confirmation 1

Frozen before any game is played. Plan:
[`.scratch/strategy-lab/plans/12-production-features.json`](../plans/12-production-features.json).

- Candidate: the installed production-features model and map, pip openings, four search
  simulations, exploration off.
- Opponent: `ValueFunctionPlayer` in the other three Seats.
- Seeds `80000–81999`, 500 games per Seat. Pilot `82000–82003`, runtime only, outcomes unread.
- Same map, rules, and attrition rules as issue 08. Decision against `0.30`: **reaches 30%**
  when the completed-game and attrition-as-losses Wilson lower bounds are both above 0.30;
  **below 30%** when the attrition-as-wins upper bound is below 0.30; otherwise inconclusive.
- No retuning after outcomes. The model stays installed either way; calibration installed it.

### Confirmation 1 result — 2026-11-12

[Artifacts and reproduction](../../../docs/experiments/production-features/README.md).
Clean source `dd48efe`, eight workers, 1,958 seconds. Pilot 4/4 in 14 seconds, outcomes unread.
**1,025 of 2,000 wins (51.25%, 95% Wilson 49.09%–53.40%)**, no attrition. Seats 280, 256, 243,
246. Decision: **reaches 30%**. All issue-08 checks, byte-identical report regeneration, and a
fresh-process hash-seed-1 replay of the first block passed.

Catan Coach may now claim: the production-features model with production-pip openings, four
search simulations, and exploration disabled won 1,025 of 2,000 games (51.25%, 95% Wilson
49.09%–53.40%) against three Catanatron `ValueFunctionPlayer` opponents on seeds 80000–81999.
