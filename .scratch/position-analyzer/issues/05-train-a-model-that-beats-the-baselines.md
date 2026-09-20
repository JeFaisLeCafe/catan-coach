# 05 — Train a Win Probability model that beats the Baselines

**What to build:** Train a model on the Corpus that predicts, from a Seat's Observation, whether
that Seat eventually wins. Persist it so it can be loaded later, and report it against the existing
Baselines through the calibration harness.

Use gradient-boosted trees rather than a neural network: the Observation is a tabular vector of
about a thousand floats, training takes seconds on CPU, and per-feature contributions come out for
free and are needed later to explain each number.

This ticket is not done because the model exists. It is done when the model is demonstrably better
than knowing only who is ahead on points.

**Blocked by:** 04 (Generate a Corpus of self-play games)

**Status:** resolved

- [x] A command trains a model from a Corpus and saves it
- [x] A saved model can be loaded and used through the existing model port, unchanged
- [x] Training reads only the train split; the validation split is untouched until evaluation
- [x] A command reports the model and every Baseline side by side on held-out games, showing Brier,
      log loss, Calibration error and the reliability bands
- [x] The model beats `constant(1/4)` and `vp-share` on Brier skill on held-out games
- [x] The model's Calibration error on held-out games is better than `vp-share`'s, which is badly
      underconfident
- [x] Both Calibration and Discrimination are reported, so a well-calibrated but undiscriminating
      model cannot pass
- [x] Training is reproducible from a seed
- [x] The report names the Corpus and the number of games behind it, so a result can be traced to
      the data that produced it
- [x] If the model fails to clear a Baseline, the report says so plainly rather than requiring the
      numbers to be compared by eye

## Comments

`uv run catan-coach train --corpus DIR --out model.txt` fits a LightGBM GBDT on the train split
only, writes the booster, reloads it through `GbdtModel` (`WinProbabilityModel`), and prints
`compare_to_baselines` on the validation games. `catan-coach report` re-runs that harness without
fitting. Exit status 1 if any bar is missed.

On 400 `ValueFunctionPlayer` games (44,144 rows): gbdt brier 0.1444 / ece 0.0370 against
`vp-share` 0.1457 / 0.0548 and `constant(1/4)` 0.1875 / 0.000. The CI suite plants a hidden
signal the VP baseline cannot see, so the beat-the-bar assertion stays fast and deterministic.
On macOS LightGBM needs Homebrew `libomp`.
