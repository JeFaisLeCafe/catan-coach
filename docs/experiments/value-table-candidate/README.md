# Value-table model: forecasts better, still loses against this Opponent Population

The value-table model learned Win Probability from the 2,000 opening-production games, where
three Catanatron `ValueFunctionPlayer` Seats beat generation 7. It cleared the calibration gate
and is now the installed model. With production-pip openings, four search simulations, and
exploration off, it won **125 of 2,000 games (6.25%)** against three `ValueFunctionPlayer`
opponents on seeds 50000–51999. The 95% Wilson interval is **5.2707%–7.3970%**. The
preregistered decision is **loses**: the completed-game upper bound and the attrition-as-wins
upper bound are both below 25%. All 2,000 games completed, with zero drops, technical failures,
or missing games.

The specification is [issue 11](../../../.scratch/strategy-lab/issues/11-learn-from-value-function-games.md).
Calibration adopted the model. The strength run was frozen before training and does not adopt
or reject a model.

## Corpus

The stored [opening-production run](../generation-7-opening-production/README.md) was copied
locally. Its raw SHA-256 matched the published `7f4420ae…93fb` before replay. Each of the
2,000 games (seeds 40000–41999) was replayed with the same scheduled-game runner at source
`0a9ed6c`. Before a game's rows were written, its winner, candidate Seat, Plies, and Turns had to
match the stored document. All 2,000 matched; none dropped. Every Seat was sampled every 12
Plies and labelled with whether it won: 251,628 rows, 1,576 train games and 424 validation
games. The candidate Seat's losing Positions stay in, labelled as losses (60,896 rows).
[corpus.json](./corpus.json) holds the independent check, including the manifest, which records
a `mixed` table: generation 7 (`19e0f664…a885`), search 4, exploration off, opponent `value`,
base seed 40000, 2,000 games.

## Calibration

[train.txt](./train.txt) is the unchanged recipe on the train split. [calibration.txt](./calibration.txt)
fits the map on 201 validation games and reports on the other 223:

| candidate minus | Brier difference | game-level 95% |
| --- | ---: | --- |
| `constant(1/4)` | −0.0593 | [−0.0666, −0.0519] |
| `vp-share(T=2)` | −0.0152 | [−0.0189, −0.0113] |
| generation 7 | −0.0170 | [−0.0227, −0.0113] |

Every interval is below zero, so `model.txt` was replaced (trees `4ff465c8…9222`, map
`fe0aa483…5aa2`). ECE was 0.0126. Generation 7 was scored on games it played in but never
trained on; the gate shows better forecasts for this Opponent Population, not better play.

## Strength artifacts and provenance

- [plan.json](./plan.json): the preregistered configuration, committed in `04aa05a` before training.
- [report.json](./report.json) and [report.md](./report.md): the Strength Report.
- [verification.json](./verification.json): decision, environment, hashes, and checks.

The source tree was clean at **34caf46153a1f58928cfc8b19c75fb26698bc47f**. Eight workers
completed the run in **1,079 seconds** on macOS arm64, Python 3.11.6, Catanatron 3.3.0 at its
pinned commit, LightGBM 4.7.0, and NumPy 2.4.6. A four-game runtime pilot on seeds 52000–52003
completed 4/4 in 4 seconds on 4 workers. Its outcomes were not read and are not in this report.
No interim outcomes were inspected, and nothing was retuned.

Independent checks verified the seeds, 500 games per Seat, all Seats in each four-game block,
Policy identities, source commit, engine pin, model and sidecar hashes, winner counts, Seat
denominators, and the Wilson interval. A second report generation was byte-identical. The first
scheduling block replayed identically in a fresh process with hash seed 1.

## Reproduce

```bash
export PYTHONHASHSEED=0
uv run catan-coach lab run .scratch/strategy-lab/plans/11-value-table-strength.json \
  --out data/experiments/value-table-candidate-vs-value --workers 8
uv run catan-coach lab report data/experiments/value-table-candidate-vs-value \
  --json docs/experiments/value-table-candidate/report.json \
  --markdown docs/experiments/value-table-candidate/report.md
```

The plan reads `data/value-table-candidate/`; rebuild it with the commands in
[docs/model.md](../../model.md).

## Interpretation and limitations

Candidate wins by Seat were 41, 26, 39, and 19 of 500. These are diagnostics only.

In its 1,875 losses the candidate built 1.17 post-setup settlements and 1.30 cities per game.
The opening-production Policy built 0.20 and 1.38 in its losses. Opponents here averaged 2.54
post-setup settlements and 1.85 cities. Opening pips were 21.86 in losses, against the
opponents' 19.83; distinct resources were 3.52 against 4.72. In the 125 wins the candidate built
2.58 settlements and 3.36 cities and held Longest Road in 91% of games.

These are descriptive associations. 125 versus 65 compares different seeds and a different
model, so it is not a paired estimate of the model change. Expansion rose, but the cause of the
remaining losses is unknown. This is one Opponent Population, one engine, one search budget, and
one opening rule, with no human-game validation.
