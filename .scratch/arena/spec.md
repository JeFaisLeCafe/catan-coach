# Spec: Arena

**Status:** ready-for-agent

## Problem Statement

The production-features model now wins about half its games against three `ValueFunctionPlayer`
Seats. That opponent has stopped being informative. Every Strategy Experiment so far asks one
question — one candidate against three copies of one opponent — so the project cannot say:

1. how its Policies rank against each other and against other engine bots;
2. whether a new model generation is stronger than the current champion, not just than a fixed
   baseline;
3. which games to learn from next.

Chess engines answer these with tournaments and rating lists. Catan needs the same idea, adapted
to four-player tables, Seat advantage, and dice variance.

## Solution

An **Arena**: a declared field of Entrants plays a balanced schedule of mixed four-player tables.
The result is a **Rating** per Entrant with an uncertainty interval, a ladder ordered by Rating,
and a store of every game. The Arena then drives a **Promotion Cycle**: its games become a Corpus,
a candidate model is trained on them, the candidate passes the calibration gate, and a
preregistered **Champion Challenge** decides whether the candidate becomes the new Champion.

### Why a rating league and not a knockout bracket

A knockout eliminates on one noisy result. At 1,000 games a three-point win-rate edge is inside
the 95% interval, so brackets would regularly eliminate the stronger Policy. A league fits one
Rating per Entrant from every game it played, reports intervals, and can still be shown as a
ladder. A bracket view is out of scope.

## User Stories

1. As a researcher, I want to declare a field of Entrants in one file, so that a league is
   reproducible.
2. As a researcher, I want Entrants to include saved model generations at chosen search budgets,
   `ValueFunctionPlayer`, `AlphaBetaPlayer`, and random play, so that the field has fixed anchors.
3. As a researcher, I want every Entrant to sit equally often in every Seat and to meet every other
   Entrant, so that Seat advantage and table luck do not decide the ladder.
4. As a researcher, I want one Rating per Entrant with a 95% interval, so that I can tell a real
   gap from noise.
5. As a researcher, I want head-to-head win shares between any two Entrants at shared tables, so
   that I can see who beats whom.
6. As a researcher, I want to resume an interrupted league without changing its result, so that
   long runs survive restarts.
7. As a researcher, I want a league's games turned into a Corpus, so that the next model learns
   from stronger and more varied play than self-play.
8. As a researcher, I want a preregistered Champion Challenge, so that a candidate is promoted only
   when it is measurably stronger than the Champion.
9. As a researcher, I want promotion to require the calibration gate as well, so that strength never
   installs a model on its own.
10. As a researcher, I want every promotion recorded with provenance, so that the Champion lineage is
    auditable.

## Implementation Decisions

### Entrants

An Entrant is a named, frozen Policy specification: the existing `model`, `value`, and `random`
kinds plus a new `alphabeta` kind for Catanatron's `AlphaBetaPlayer` (depth declared in the plan).
Model Entrants pin model and sidecar hashes as Strategy Experiments already do. The same model at
two search budgets is two Entrants.

### Schedule

- A league plan declares at least four Entrants, a number of **cycles**, base seed, rules, and map
  policy.
- Tables hold four distinct Entrants. One cycle plays every one of the `C(n,4)` combinations once
  as a **block** of four games: the four cyclic Seat rotations of that combination, all on the same
  board seed. Each block has its own seed.
- Per cycle every Entrant plays `4·C(n-1,3)` games, `C(n-1,3)` in each Seat. Games per Entrant are
  therefore a multiple of that number; the plan states cycles, not games.
- Seeds come from a range not used by any earlier experiment, starting at `200000`.
- Games, persistence, resume, drops, and technical failures reuse the Strategy Lab store and its
  validity rules (more than 1% drops or any terminal failure invalidates the league).

### Rating

- Each completed game is one observation: the winning Entrant out of the four at the table.
- Fit a multinomial-logit (Plackett–Luce first-choice) strength model,
  `P(i wins) = exp(r_i + s_seat(i)) / Σ exp(r_j + s_seat(j))`. Identification: ratings sum to
  zero and Seat effects sum to zero.
- The estimator is penalized maximum likelihood with a declared Gaussian penalty (standard
  deviation 2 on each rating and Seat effect), so an Entrant with no wins, such as random, still
  gets a finite, clearly low rating. The penalty is stated in every report. Pure Python/NumPy in
  `domain/`.
- 95% intervals from a fixed-seed **block bootstrap** (10,000 replicates): resample blocks, keeping
  the four same-seed rotations together, because they share a board and are not independent.
- Report ratings on an Elo-like display scale (`400 / ln 10` per unit) and, for readability, each
  Entrant's expected win rate against three average Entrants.
- Head-to-head: for each pair, the share of shared tables that one of the two won which the first
  one won, with a block-bootstrap interval from the same replicates.

### Promotion Cycle

1. **League** — run the plan; publish ladder and head-to-head.
2. **Corpus** — replay league games into a Corpus labelled by winner (the replay path from
   `0a9ed6c`); the manifest records the league and its Entrants.
3. **Train** — train a candidate on the train split.
4. **Calibration gate** — unchanged: the candidate must beat the installed model and the Baselines
   on held-out games. Failing the gate ends the cycle.
5. **Champion Challenge** — a 2,000-game plan committed before play: candidate in one Seat, three
   Champion Seats, fresh seeds, issue-08 decision rule against `0.25`. Promotion requires the
   lower Wilson bound above `0.25` under both completed-game and attrition-as-losses readings.
   **Anchor check**, preregistered in the same commit: the candidate and the Champion, at the same
   Search Budget and exploration setting, each play the same 2,000 scheduled games against three
   `ValueFunctionPlayer` Seats (identical seeds and Seats). Promotion also requires the paired
   bootstrap 95% lower bound of candidate minus Champion win rate to be above `−0.03`: the
   candidate must not have become weaker against a fixed outsider while beating the Champion.
6. **Promote** — install the candidate as `model.txt`, append the lineage entry, add it to the next
   league field.

The Champion is the installed model. A cycle never retunes from Champion Challenge outcomes.

### Interfaces

- `catan-coach arena run <plan> --out <dir> [--workers N]`
- `catan-coach arena report <dir> --json ... --markdown ...`
- `catan-coach arena corpus <dir> --out <corpus dir>`
- Champion Challenge plans are ordinary Strategy Lab plans; no new runner.
- Lineage lives in `docs/champions.md`, one row per promotion.

### Seams

Scheduling, rating, and reports are pure `domain/` code. Only `engine/` builds Catanatron players,
including `AlphaBetaPlayer`.

## Testing Decisions

- Schedule tests: every Entrant appears equally often per Seat; every combination appears; the
  schedule is deterministic from the plan.
- Rating tests: synthetic games drawn from known strengths recover their order and lie inside the
  interval; equal strengths give overlapping intervals; Seat effects are recovered; the fit is
  invariant to Entrant ordering; a zero-win Entrant gets a finite rating.
- Resume test: an interrupted tiny league resumes to an identical report.
- Engine-marked smoke test: a four-Entrant league of a few games completes with `AlphaBetaPlayer`.

## Out of Scope

- Knockout or Swiss brackets.
- Archetype bots (Ore-Wheat-Sheep, Road Builder, …): a follow-up spec once the Arena exists.
- Trading regimes, three-player tables, and human games.
- Automatic, unattended promotion: each step stays a committed, reviewable command.

## Further Notes

The first league field: generation 7, value-table, and production-features at search 0 and 4;
`ValueFunctionPlayer`; `AlphaBetaPlayer`; random. The Strategy Report spec
(`.scratch/strategy-report/`) turns league output into readable findings.
