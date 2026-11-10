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

## Play locally

Requires Node.js 24 and npm 11 in addition to the Python setup.

```bash
uv run catan-coach play
```

This builds the browser app, starts the local server, and opens Catan Coach. Games are
saved in `~/.catan-coach/games.sqlite` and can be resumed from the home page.

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

Catan Coach is a working local coaching app. It can:

- play a browser game against bots, autosave it, resume it, and replay it;
- switch between Challenge Mode and live Coach Mode;
- rank every legal Action with the installed model;
- refine an Analysis with progressive search and show representative continuations;
- review a completed game and order decisions by Loss;
- generate resumable self-play Corpora, train candidates, calibrate them, and gate adoption.

The Strategy Lab compares a named Policy with an Opponent Population and reports seat-balanced
win rates, uncertainty, and descriptive behavior. A small example plan is
[`docs/examples/strategy-lab.json`](./docs/examples/strategy-lab.json). The completed
[generation-7 audit](./docs/experiments/generation-7-vs-value/README.md) found 12 wins in 2,000
games against three `ValueFunctionPlayer` opponents. The settlement/city intervention is specified
in [`docs/experiments/README.md`](./docs/experiments/README.md) and remains unrun.

```bash
uv run catan-coach lab run docs/examples/strategy-lab.json --out data/experiments/smoke
uv run catan-coach lab report data/experiments/smoke
uv run catan-coach lab compare data/experiments/reference data/experiments/variant
```

The bundled model is generation 7. Its provenance, held-out result, and reproduction command are
recorded in [docs/model.md](./docs/model.md).

## Model workflow

```bash
uv run catan-coach corpus --games 1000 --players model --model model.txt --out data/corpus-next
uv run catan-coach train --corpus data/corpus-next --out data/model-next.txt
uv run catan-coach calibrate \
  --model data/model-next.txt \
  --corpus data/corpus-next \
  --installed model.txt \
  --out model.txt
```

`calibrate` fits a monotone probability map on one set of held-out games and evaluates it on
different held-out games. It replaces the installed model only when Brier skill beats
`constant(1/4)`, `vp-share`, and the installed model.
