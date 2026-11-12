# 11 — Learn Win Probability from the value-function games

**Status:** ready-for-agent

**Blocked by:** 10 (resolved)

## Why this, and not more self-play

Generation 7 was installed because it forecasts its own self-play slightly better than the
baselines. That Corpus is the previous model playing itself. In those games the winner is whoever
got the better dice inside a style that barely expands, so the labels never say that the Seat
which built settlements won.

The opening-production games do say that. One Seat played generation 7 with production-pip
openings, four search simulations, and exploration off. The other three Seats played
`ValueFunctionPlayer`. The value-function Seats expanded and won. Those outcomes are the training
signal. Copying our Seat's Actions from those games would teach the loss again. Another self-play
Corpus from this Policy would repeat it.

The stored experiment documents do not contain Observations. The Corpus has to be replayed. The
published games are the oracle for who won.

## Frozen training games

Replay [`.scratch/strategy-lab/plans/10-opening-production.json`](../plans/10-opening-production.json)
at seeds `40000–41999`, with the Policy this tree plays now: pip openings, four search
simulations, exploration off, generation 7 in the scheduled candidate Seat, `ValueFunctionPlayer`
in the others.

Before any training row is kept, every replayed game's winner and candidate Seat must match the
stored document in `data/experiments/generation-7-opening-production/`. A mismatch stops the work.
If that directory is absent, reproduce the published experiment and require its report to match
the committed `report.json` before sampling.

Leave seeds `20000–21999` out. That audit was played before the pip rule, and this tree cannot
regenerate it.

The current Corpus generator cannot do this replay. It seats one kind of player at the whole
table, and a model table turns exploration on and search off when exploration is off. Do not
call that path and hope. Record the mixed table in the manifest as its own player kind, including
the candidate model hash, search 4, exploration false, the opponent, the base seed, and the game
count. A manifest that claims these games were self-play is refused. Existing `value` and `model`
Corpora stay valid. Training still refuses a missing manifest or a drop rate above 1%.

Sample as the other Corpora do: ply stride 12, one Observation per Seat, labeled with whether
that Seat won. Keep the candidate's losing Positions with the loss label. The validation fraction
stays 0.2, and a whole game goes to train or validation together.

## Frozen training recipe

Use `train()` as it stands: the same LightGBM parameters and 80 rounds. Fit on the train split
only. Adopt only through the existing calibrate gate on this Corpus, with generation 7 as the
installed prior. The game-level 95% Brier interval has to clear `constant(1/4)`, `vp-share`, and
generation 7. Publish the report if it fails. A failure does not install the candidate, and it
does not cancel the strength run.

Write the candidate trees and the fitted map to `data/value-table-candidate/`, even when the gate
fails. Do not replace `model.txt` unless the gate passes. Do not retune after seeing calibration
or win counts.

## Preregistered strength run

Frozen before any training metric or win count from the candidate is inspected. Plan:
[`.scratch/strategy-lab/plans/11-value-table-strength.json`](../plans/11-value-table-strength.json).

- Candidate: the file written above, pip openings still in the Policy, four search simulations,
  exploration off. The pip rule stays because settlement Actions still do not show production to
  the model. Taking it off would mix two changes.
- Opponent: `ValueFunctionPlayer` in the other three Seats.
- Seeds `50000–51999` (500 games per Seat). Outside corpus seeds `0–7999`, the generation-7 audit
  `20000–21999`, its pilot `22000–22003`, the reserved Intervention range `30000–33999`, the
  training games `40000–41999`, and their pilot `42000–42003`.
- Same map, rules, sample size, Wilson comparison with `0.25`, and attrition rules as issue 08.
- A four-game runtime pilot uses seeds `52000–52003` and records completion and elapsed time only.
  Its win outcomes are not read and are excluded from the report.
- Do not change this plan after seeing calibration or win outcomes. Strength does not adopt the
  model. Calibration remains the adoption gate.

## Acceptance

- The Corpus manifest describes the mixed table, and a self-play claim for it is refused.
- Replayed winners and candidate Seats match the stored opening-production games before training.
- Train rows come from the train split only. Losing Positions remain, labeled as losses.
- The calibration report is published whether or not the candidate is installed.
- The strength report is the preregistered one, on seeds `50000–51999`, with the same verification
  bar as issues 08 and 10.
- No self-play generation is trained from this Policy as a substitute.
- Full Python and frontend suites, build, Ruff, and mypy pass. The 2,000-game replay is not a CI
  test.

## Non-goals

Changing features, removing the pip rule, behavior-cloning `ValueFunctionPlayer`, training on the
generation-7 audit seeds, running the settlement/city sweep, or installing the candidate because
it won games.
