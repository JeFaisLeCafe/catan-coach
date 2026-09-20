# Win probability is the unit of evaluation

Actions are scored in Win Probability rather than a heuristic score, because a probability is
falsifiable: take every Position called 70% and check that about 70% were won. No other
candidate unit can be checked at all. A previous attempt (`catanai2`) trained neural networks
with no way to tell whether they were learning anything, and drowned in diagnostics as a result.

Chess is the obvious counter-reference, but it argues the same way: engines moved from
centipawns to win/draw/loss precisely because heuristic units are not comparable across
positions. Catan has far more variance than chess, so the argument is stronger here.

## Consequences

The calibration harness is built before any model and gates every model. Win Probability also
makes Loss and Blunder definable in a unit that means something, which every downstream feature
depends on.
