# 12 — Reach a 30% win rate against three ValueFunctionPlayer Seats

**Status:** in-progress

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
