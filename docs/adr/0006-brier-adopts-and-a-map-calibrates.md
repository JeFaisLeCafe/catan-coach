# Brier adopts a model, and a monotone map calibrates it

Win Probability stays the unit of evaluation. A stated 70% still has to be won
about 70% of the time. The adoption decision is Brier skill: the candidate must
beat `constant(1/4)`, `vp-share`, and the installed model. Brier already
punishes probabilities that miss what happened.

Calibration error stays in the report. It is not a veto. A vague baseline can
sit near the diagonal while a sharper model, slightly low on its confident
calls, is the better forecast and still loses an error contest. After the trees
are chosen, a monotone map fit on held-out games and judged on games it did not
see is what pulls a stated 70% onto the outcomes.

## Consequences

`clears_adoption` checks Brier skill only. The map is stored beside the
LightGBM file and applied when that file is loaded. A candidate that loses on
Brier does not replace the installed model, and neither does a map fit that
fails those same bars.
