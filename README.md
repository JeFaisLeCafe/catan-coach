# Catan Coach

Scores every legal action in a Settlers of Catan position by win probability, so you can see
what you should have played and by how much.

Start with [CONTEXT.md](./CONTEXT.md) for the vocabulary and [docs/adr/](./docs/adr/) for why
the project is shaped the way it is.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync
uv run pytest
```

The first sync builds catanatron from a pinned git commit and takes a couple of minutes.

## Layout

```
src/catan_coach/
├── domain/      pure; knows nothing about catanatron
│   ├── calibration.py   the ruler: Brier, log loss, reliability bins, ECE
│   └── prediction.py    the WinProbabilityModel port
├── engine/      the only package that imports catanatron
│   └── features.py      positions to numbers, feature name resolution
└── models/      implementations of the port
    └── baselines.py     the bars a real model has to clear
```

`engine/` is a deliberate seam. Replacing the game engine means rewriting that package and
nothing else.

## Tests

```bash
uv run pytest                      # everything, ~10s
uv run pytest -m "not engine"      # pure domain tests only, instant
uv run pytest -m engine            # plays real games; also verifies the catanatron pin
```

## Status

Foundations only. The calibration harness and its baselines exist; the corpus, the learned
model, and the analyzer do not yet.

Current baselines over 788 sampled positions from 24 self-play games:

| model            | brier  | log loss | ece    |
| ---------------- | ------ | -------- | ------ |
| `constant(1/4)`  | 0.2084 | 0.6083   | 0.0419 |
| `vp-share(T=2)`  | 0.1697 | 0.5101   | 0.0979 |

Brier skill of `vp-share` over `constant`: **+0.186**.

Note that `vp-share` has the better Brier score but the *worse* ECE. `constant` is well
calibrated and completely undiscriminating; `vp-share` discriminates but is badly underconfident
(when it says 44% the player actually wins 95%). This is exactly why both numbers are reported,
and it is the trap a single metric would hide.
