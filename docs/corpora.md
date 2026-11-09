# Corpora

A Corpus is a set of self-play games. Each parquet row stores the game, the ply, the seat, the
split, whether that seat won, the seed, and the observation. It does not store who played.

A generated directory also holds `manifest.json`. Generation writes it before the first game,
with outcome counts at zero, and updates games finished, games dropped, and the drop rate when
the run finishes. The manifest records:

- player kind, `value` or `model`
- model sha256, empty for the value-function bot
- search simulations: 4 when a model plays, 0 for the value-function bot
- exploration, on when a model plays (near-tie exploration)
- ply stride, base seed, requested game count, validation fraction, max turns
- git revision, or `unknown` when `git rev-parse HEAD` fails
- whether the work tree was dirty
- games finished, games dropped, drop rate

Resume continues a directory only when that invocation still matches. A later call may ask for
more games from the same base seed. It may not ask for fewer, and it may not change the player,
the model hash, the search count, exploration, the stride, the validation fraction, or the turn
limit. The git revision and dirty-tree flag stay on the manifest as a record of the checkout.
A later commit does not block resume.

Training and calibration refuse a directory whose manifest is missing, and they refuse a drop
rate above 1%. A drop rate above 1% cannot support a strength claim.

## Counted on 2026-11-09

The player is unknown for corpora 1–6 because the files never stored it. Generation 7 is known
from [model.md](model.md): 1,000 games, seeds 7,000–7,999, played by the generation-6 model with
near-tie exploration and four search simulations, 0 dropped.

| corpus | seeds | finished | dropped | rows | player |
| --- | --- | ---: | ---: | ---: | --- |
| corpus-v1 | 0–2999 | 3000 | 0 | 335336 | unknown |
| corpus-v2 | 3000–5999 | 2792 | 208 (6.9%) | 1222588 | unknown |
| corpus-v3 | 0–2999 | 3000 | 0 | 1669128 | unknown |
| corpus-v4 | 0–999 | 1000 | 0 | 389784 | unknown |
| corpus-v5 | 5000–5999 | 1000 | 0 | 366656 | unknown |
| corpus-v6 | 6000–6999 | 1000 | 0 | 380076 | unknown |
| corpus-v7 | 7000–7999 | 1000 | 0 | 373752 | generation 6, documented in model.md |

Corpus 2 is not a training source. It dropped 208 of 3,000 games, 6.9%. The other corpora
dropped none.

Corpora 3 and 4 reuse seeds from corpus 1, and corpus 5 overlaps corpus 2, so these are not one
pooled sample. Position density differs: about 112 rows per game in corpus-v1, about 556 in
corpus-v3.
