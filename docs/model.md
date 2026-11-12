# Installed model

`model.txt` is the value-table model: LightGBM trees trained on the games where
`ValueFunctionPlayer` beat generation 7. `model.calibration.json` is its monotone probability map.
It replaced generation 7 on 2026-11-12 through the calibration gate in
[issue 11](../.scratch/strategy-lab/issues/11-learn-from-value-function-games.md).

## Provenance

- Trees and map: `data/value-table-candidate/` (sha256 `4ff465c8…9222` and `fe0aa483…5aa2`)
- Corpus: `data/corpora/value-table`, a `mixed` manifest at source `0a9ed6c`
- Games: the 2,000 stored [opening-production games](./experiments/generation-7-opening-production/README.md),
  seeds 40,000–41,999, replayed and matched game by game on winner, candidate Seat, Plies, and Turns
- Players: generation 7 with production-pip openings, four search simulations, and exploration
  off in one Seat; `ValueFunctionPlayer` in the other three
- Sampling: every Seat every 12 Plies, labelled with whether that Seat won; 251,628 rows
- Training: train split only, 1,576 games, the unchanged LightGBM recipe and 80 rounds
- Calibration: 201 validation games
- Adoption report: a different 223 validation games

[Corpus check, training output, and calibration report](./experiments/value-table-candidate/).

## Adoption result

| model | Brier | log loss | ECE | candidate minus model, game-level 95% |
| --- | ---: | ---: | ---: | --- |
| `constant(1/4)` | 0.1875 | 0.5623 | 0.0000 | −0.0593 [−0.0666, −0.0519] |
| `vp-share(T=2)` | 0.1434 | 0.4456 | 0.0474 | −0.0152 [−0.0189, −0.0113] |
| generation 7 | — | — | — | −0.0170 [−0.0227, −0.0113] |
| value-table | 0.1282 | 0.3994 | 0.0126 | |

Every interval is below zero, so the candidate cleared the gate. ECE is reported but is not a
veto. Generation 7 is judged here on games it partly played but never trained on; the gate says
the new model forecasts this Opponent Population better, not that it plays better.

## Reproduce the gate

```bash
export PYTHONHASHSEED=0
uv run catan-coach corpus --replay data/experiments/generation-7-opening-production \
  --model model.txt --out data/corpora/value-table --workers 8   # generation 7 installed
uv run catan-coach train --corpus data/corpora/value-table \
  --out data/value-table-candidate/model.txt --installed model.txt
uv run catan-coach calibrate --model data/value-table-candidate/model.txt \
  --corpus data/corpora/value-table --installed model.txt --out model.txt --keep-candidate-map
```

Generation 7 is `git show 04aa05a:model.txt` with `04aa05a:model.calibration.json`.

## Playing strength

The [generation-7 strength audit](./experiments/generation-7-vs-value/README.md) found 12 wins
in 2,000 games against three `ValueFunctionPlayer` opponents with four search simulations and
exploration disabled. Generation 7 loses under that preregistered plan. The opening-pip Policy
then won 65 of 2,000 on different seeds and loses under the same rule. Held-out Calibration
does not establish strong play. The value-table model learned from those value-function games, as specified in
[issue 11](../.scratch/strategy-lab/issues/11-learn-from-value-function-games.md), rather than
from another self-play Corpus of this Policy. Its preregistered strength run is on seeds
50000–51999.
