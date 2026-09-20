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

**Status:** ready-for-agent

- [ ] A command trains a model from a Corpus and saves it
- [ ] A saved model can be loaded and used through the existing model port, unchanged
- [ ] Training reads only the train split; the validation split is untouched until evaluation
- [ ] A command reports the model and every Baseline side by side on held-out games, showing Brier,
      log loss, Calibration error and the reliability bands
- [ ] The model beats `constant(1/4)` and `vp-share` on Brier skill on held-out games
- [ ] The model's Calibration error on held-out games is better than `vp-share`'s, which is badly
      underconfident
- [ ] Both Calibration and Discrimination are reported, so a well-calibrated but undiscriminating
      model cannot pass
- [ ] Training is reproducible from a seed
- [ ] The report names the Corpus and the number of games behind it, so a result can be traced to
      the data that produced it
- [ ] If the model fails to clear a Baseline, the report says so plainly rather than requiring the
      numbers to be compared by eye
