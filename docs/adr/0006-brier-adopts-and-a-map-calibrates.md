# Brier adopts a model, and a monotone map calibrates it

Win Probability stays the unit of evaluation. A stated 70% still has to be won
about 70% of the time. The adoption decision is Brier skill: the candidate must
beat `constant(1/4)`, `vp-share`, and the installed model. Every other
supplied prior is the same bar. Brier already punishes probabilities that
miss what happened.

When the caller supplies a per-game sample, each of those references is
cleared only when the upper end of a game-level 95% interval is strictly
below zero. The interval resamples games, not rows, and the statistic is the
row-weighted mean Brier difference, candidate minus reference.

Calibration error stays in the report. It is not a veto. A vague baseline can
sit near the diagonal while a sharper model, slightly low on its confident
calls, is the better forecast and still loses an error contest. After the trees
are chosen, a monotone map fit on held-out games and judged on games it did not
see is what pulls a stated 70% onto the outcomes.

## Consequences

`clears_adoption` checks Brier skill only. A supplied per-game sample must
clear the game-level 95% interval above, and every supplied prior counts.
Without per-game scores the point estimate remains the bar. Extra priors are
passed as `prior_paths` to `calibrate_model`, next to `installed_path`, and as
`priors` to `compare_to_baselines` together with validation `game_ids`. The
CLI does not parse that list yet; a flag can forward paths into `prior_paths`.
The map is stored beside the LightGBM file and applied when that file is
loaded. A candidate that loses on Brier does not replace the installed model,
and neither does a map fit that fails those same bars. An interval that
reaches zero is such a loss.
