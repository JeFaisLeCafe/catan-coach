# Installed model

`model.txt` is the generation-7 LightGBM model. `model.calibration.json` is its monotone
probability map.

## Provenance

- Trees: `data/model-v7.txt`
- Corpus: `data/corpus-v7`
- Games requested: 1,000, with game seeds 7,000–7,999
- Players: the then-installed generation-6 model, with near-tie exploration and four search
  simulations per Action
- Boards: deterministically varied from each game seed
- Training: train split only
- Calibration: 80 validation games
- Adoption report: a different 94 validation games

The generation-6 calibration sidecar was overwritten during the historical run, so the Corpus
cannot be regenerated bit-for-bit from the remaining artifacts. The generation-7 trees, Corpus,
calibration input, and adoption report are preserved.

## Adoption result

Revalidated on 2026-11-08 against the generation-1 model committed at `e55f292`:

| model | Brier | log loss | ECE |
| --- | ---: | ---: | ---: |
| `constant(1/4)` | 0.1875 | 0.5623 | 0.0000 |
| `vp-share(T=2)` | 0.1486 | 0.4597 | 0.0209 |
| generation 7 | 0.1415 | 0.4407 | 0.0298 |

Generation 7 had Brier skill `+0.245` over `constant(1/4)`, `+0.048` over `vp-share`, and
`+0.011` over the installed generation-1 model. It therefore cleared ADR 0006's adoption gate.
ECE is reported but is not an adoption veto.

## Reproduce the gate

```bash
git show e55f292:model.txt > /tmp/catan-coach-generation-1.txt
uv run catan-coach calibrate \
  --model data/model-v7.txt \
  --corpus data/corpus-v7 \
  --installed /tmp/catan-coach-generation-1.txt \
  --out /tmp/catan-coach-generation-7.txt \
  --seed 0
```

The command fits the map on one deterministic half of the validation games and prints metrics
from the untouched half. It exits nonzero and leaves the output unchanged if any Brier bar fails.

## Playing strength

The [generation-7 strength audit](./experiments/generation-7-vs-value/README.md) found 12 wins
in 2,000 games against three `ValueFunctionPlayer` opponents with four search simulations and
exploration disabled. Generation 7 loses under that preregistered plan. The opening-pip Policy
then won 65 of 2,000 on different seeds and loses under the same rule. Held-out Calibration
does not establish strong play. The next model learns from those value-function games, as
specified in [issue 11](../.scratch/strategy-lab/issues/11-learn-from-value-function-games.md),
rather than from another self-play Corpus of this Policy.
