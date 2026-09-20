# 01 — Rank the Actions in a Position

**What to build:** Given a Position and a Win Probability model, produce an Analysis: every legal
Action in that Position, each with the Win Probability of the Position it leads to and its Loss
against the best Action, ordered best first.

The Win Probability is always stated for the Seat whose turn it is to act. Scoring happens in a
single batched call to the model, because a Position can offer dozens of legal Actions.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] An Analysis lists every legal Action available in the Position, and no others
- [x] Actions are ordered by Win Probability, best first
- [x] Each Action carries its Loss against the best Action; the best Action's Loss is zero
- [x] The model is consulted once for the whole Position, not once per Action
- [x] A Position offering a single legal Action produces an Analysis that says so, rather than a
      one-row ranking presented as a choice
- [x] Analysing a Position does not mutate it; the caller's Position is unchanged afterwards
- [x] Tests drive the analyzer with a stub Win Probability model returning hand-written numbers, so
      ordering, Loss arithmetic and ties are asserted exactly with no dice randomness
- [x] Ties in Win Probability are handled with a defined, documented order rather than arbitrarily
- [x] The analyzer accepts any implementation of the existing model port, verified by running it
      against an existing Baseline as well as the stub

## Comments

Landed in `d7a3c01`. `analyze()` and the `Position` port live in `domain/`; `EnginePosition` in
`engine/` is the only piece that touches catanatron. Ties break by Action label, ascending.

Catanatron's `Game.copy()` shares the random stream with the original, so scoring a `ROLL` would
have advanced the caller's dice. `EnginePosition` gives each copy its own stream, covered by
`test_analysing_does_not_advance_the_callers_dice`.
