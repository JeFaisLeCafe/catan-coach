# 01 — Rank the Actions in a Position

**What to build:** Given a Position and a Win Probability model, produce an Analysis: every legal
Action in that Position, each with the Win Probability of the Position it leads to and its Loss
against the best Action, ordered best first.

The Win Probability is always stated for the Seat whose turn it is to act. Scoring happens in a
single batched call to the model, because a Position can offer dozens of legal Actions.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] An Analysis lists every legal Action available in the Position, and no others
- [ ] Actions are ordered by Win Probability, best first
- [ ] Each Action carries its Loss against the best Action; the best Action's Loss is zero
- [ ] The model is consulted once for the whole Position, not once per Action
- [ ] A Position offering a single legal Action produces an Analysis that says so, rather than a
      one-row ranking presented as a choice
- [ ] Analysing a Position does not mutate it; the caller's Position is unchanged afterwards
- [ ] Tests drive the analyzer with a stub Win Probability model returning hand-written numbers, so
      ordering, Loss arithmetic and ties are asserted exactly with no dice randomness
- [ ] Ties in Win Probability are handled with a defined, documented order rather than arbitrarily
- [ ] The analyzer accepts any implementation of the existing model port, verified by running it
      against an existing Baseline as well as the stub
