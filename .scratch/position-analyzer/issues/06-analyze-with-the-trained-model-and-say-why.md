# 06 — Analyze with the trained model, and say why

**What to build:** Point the command-line analyzer at the trained model instead of a Baseline, and
attach a reason to each Action so the output teaches rather than only judges.

The reason is the set of feature contributions that moved that Action's Win Probability most, named
in terms a player recognises — production, reachable expansion, hand, army, road — rather than raw
feature identifiers.

**Blocked by:** 03 (See an Analysis from the command line), 05 (Train a model that beats the
Baselines)

**Status:** resolved

- [x] The analyzer uses the trained model by default when one is available
- [x] A Baseline can still be selected explicitly, so the analyzer's behaviour with a known-bad
      model remains inspectable
- [x] If no trained model is present, the command says so and falls back to a Baseline rather than
      failing
- [x] Each ranked Action carries the handful of contributions that most moved its Win Probability
- [x] Contributions are labelled in player-recognisable terms, not raw feature identifiers
- [x] Analysing a whole Position stays within a few seconds
- [x] The output distinguishes a confident call from a near-tie, so a Loss of half a point is not
      presented with the same weight as a Loss of fifteen
- [x] Explanations are covered by tests that assert the shape and labelling of the reasons, not
      specific numeric attributions

## Comments

`uv run catan-coach GAME.json PLY` loads `model.txt` when present (else stderr + `vp-share`).
`--baseline constant|vp-share` forces a Baseline. `--model PATH` names the booster.

`GbdtModel.explain` uses LightGBM `pred_contrib`, grouped in `domain/reasons.py` into production,
reachable expansion, hand, army, road, and points. Loss is printed in percentage points of Win
Probability; a gap of 1 point or less is labelled a near-tie.
