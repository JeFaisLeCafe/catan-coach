# Depend on Catanatron by git SHA, not by PyPI version

The published PyPI package `catanatron` is a dead snapshot: version 3.2.1 was released in July
2022 and contains twenty files. It has no `features.py`, no `serialization.py`, no
`pygame_renderer.py`, and a `players/` directory holding only `search.py` and
`weighted_random.py` — no value function, minimax, playouts, or MCTS. Every module this project
uses exists solely on GitHub `main`, which self-reports as 3.3.0 and is unreleased.

We therefore depend on an exact commit:

```
catanatron[gym] @ git+https://github.com/bcollazo/catanatron@ecf931181b9a65bb4116a2153fb78c16f1438e00
```

The pin is mandatory rather than hygiene. A Corpus and a trained model encode catanatron's exact
feature layout, so an unnoticed upgrade would silently invalidate both while everything still
appeared to run. Upstream is low-velocity (three commits in the ninety days before adoption),
so holding a pin should be quiet.

## Consequences

`tests/test_engine.py` asserts the version and imports every module the plan depends on, so a
bad or drifted pin fails loudly and immediately. Bumping the pin is a deliberate act that
requires re-running the calibration harness against the existing Corpus before it is accepted.
`[tool.hatch.metadata] allow-direct-references` must stay enabled for the build to work.
