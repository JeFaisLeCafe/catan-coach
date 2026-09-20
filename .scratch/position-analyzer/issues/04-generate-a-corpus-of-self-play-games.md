# 04 — Generate a Corpus of self-play games

**What to build:** A command that plays N self-play games with strong play and records a Corpus:
one row per Seat per sampled Position, holding that Seat's Observation and whether that Seat
eventually won.

Two constraints are load-bearing and were established by measurement, not guesswork.

**All four Seat perspectives are recorded for each sampled Position.** Recording only one Seat
lets Seat-order advantage be absorbed as a constant: the first Seat was measured winning 29% over
24 games and 42% over 12, against a naive 25%.

**Train and validation are assigned by game, never by Position.** Every Position within a game
shares one outcome, so splitting by row would place near-identical Positions on both sides and make
the validation score meaningless. For the same reason, Corpus size is reasoned about in games: a
run of 10,000 games gives roughly 10,000 independent labels, not millions.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] A command generates a Corpus from a requested number of games and writes it to parquet
- [x] Games are played with strong play, not random play, so the learned probabilities describe
      good Catan
- [x] Each sampled Position contributes one row per Seat, each labelled with whether that Seat won
- [x] Every row records which game it came from, so splits can be made by game
- [x] The train/validation assignment is by game and is reproducible from a seed
- [x] Sampling frequency across Plies is configurable, so redundancy between near-identical
      consecutive Positions can be reduced
- [x] Generation runs across multiple cores
- [x] An interrupted run can be resumed without discarding completed games
- [x] Games that fail to terminate are dropped and counted, not silently included
- [x] A summary reports games played, rows written, and the observed win rate per Seat
- [x] Verified end to end on a small run in the test suite, marked as engine-touching

## Comments

`uv run catan-coach corpus --games N --out DIR` plays `ValueFunctionPlayer` games and writes one
parquet file per finished game under `DIR/games/`. Split assignment is `split_for_game` in
`domain/`; sampling and I/O live in `engine/corpus.py`. Each game is persisted as soon as it
finishes, so a crash keeps already-written games. Dropped games (hitting the engine turn limit)
are marker files under `DIR/dropped/`, counted in the summary, and skipped on resume.
