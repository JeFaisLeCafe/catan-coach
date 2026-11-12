# 10 — Improve the Policy after the generation-7 strength audit

**Status:** resolved

**Blocked by:** 08 (completed)

## Evidence

The preregistered [audit](../../../docs/experiments/generation-7-vs-value/README.md) completed
2,000 games with no attrition. Generation 7 with four search simulations won 12 games (0.60%;
95% Wilson 0.3436%–1.0458%) against three `ValueFunctionPlayer` opponents. It loses under the
preregistered rule. In losses it built 0.06 post-setup settlements per game. This is descriptive,
not evidence that one build preference caused the loss.

## Goal

Identify and correct the smallest evidence-backed weakness in the installed Policy before using
it to generate another self-play Corpus. Keep the published audit and installed model unchanged.

## Work

1. Read the audit artifacts and inspect representative saved games selected by a documented rule.
2. Verify the complete path from legal Actions through model Win Probabilities, search coverage,
   and final Action selection. Check whether the small total search budget systematically excludes
   useful legal Actions; do not assume that this is the cause.
3. Separate harness correctness, model forecasting quality, and Policy selection quality. Reproduce
   any concrete bug before fixing it, and add a focused regression test.
4. Preregister a new seat-balanced comparison on fresh seeds outside 0–21999 and the reserved
   Intervention range 30000–33999 before inspecting its win outcomes. Declare the changed Policy,
   opponent, sample size, attrition rules, and uncertainty calculation. Pilot runtime separately.
5. Publish favorable and unfavorable results. A model replacement must separately pass Calibration;
   a strength result does not authorize adoption.

## Acceptance

- Evidence explains the observed failure or explicitly records what remains unknown.
- Any implementation fix has direct reproduction and regression proof.
- Any strength-improvement claim has a complete reproducible game-level report against the named
  Opponent Population, with equal Seat exposure and attrition sensitivity.
- No generation-8 self-play is generated from the losing Policy as a substitute for this diagnosis.
- Full Python/frontend suites, build, Ruff, and mypy pass.

## Non-goals

Running the settlement/city sweep, choosing a preference from observed wins, training a model,
changing the historical audit, or publishing fixed strategic coaching advice.

## Preregistered follow-up

Frozen before any win outcome of the changed Policy is inspected. Plan:
[`.scratch/strategy-lab/plans/10-opening-production.json`](../plans/10-opening-production.json).

- Candidate: installed generation 7, four search simulations, exploration off. During the initial
  build, a settlement is the legal node with the most production pips. An exact pip tie breaks on
  Action label, ascending. Roads and every later Action still follow the model. This rule is code
  in `WinProbabilityPlayer`, not a plan preference, so the frozen source commit is part of play
  identity.
- Opponent: `ValueFunctionPlayer` in the other three Seats.
- Seeds `40000–41999` (500 games per Seat). Outside corpus seeds `0–7999`, the generation-7 audit
  `20000–21999`, and the reserved Intervention range `30000–33999`.
- Same map, rules, sample size, Wilson comparison with `0.25`, and attrition rules as issue 08.
- A four-game runtime pilot uses seeds `42000–42003` and records completion and elapsed time only.
  The pilot completed 4/4 games with no terminal failures in 4 seconds on 4 workers. Its win
  outcomes were not read.
- Do not change this plan after seeing its win outcomes. The installed model stays in place either
  way. Calibration remains the adoption gate.

## Comments

Opening diagnosis, before the follow-up run. Sample for the node ranking: the candidate's first
settlement in seeds `20000–20079`. Sample for pip regret and opening totals: seeds `20000–20199`,
the same plan and model as the published audit. No win rates from these replays were read.

The model's first-settlement ranking does not depend on the board. Across 18 nodes that were
legal in every one of those 80 decisions, the rank correlation between a board's Win Probabilities
and the average node ranking was 1. The mean rank correlation between production pips and Win
Probability was -0.10. Node 16 was chosen in 58 of 80 games. The best-pip node varied across the
board. Tile probabilities are 1.2% of the model's gain and do not change from one settlement
Action to another; only the node-occupancy bit does. Four search simulations were not the cause:
on the first settlement they changed 39 of 200 choices, and the one-ply pick was already a
low-pip node (mean pip regret 3.75, rank 11.8 of about 48).

The Policy now chooses that settlement by production pips and does not call the model or the
search. On seeds `20000–20199` the candidate's opening pips rose from about 16 to 21.93, ahead of
the opponents' 19.85. Distinct resources stayed behind: 3.63 versus 4.68. Adjacent ports stayed
rare: 8/200 versus 47/600. Whether the pip rule changes game wins, and whether the remaining
resource gap matters, is what the preregistered run is for. Post-setup expansion was not
re-measured.

## Completed comparison — 2026-11-12

Source: `38b05bea0e560c56e340a208b7d50dce59e4b9a1` (clean).
[Artifacts, hashes, environment, and reproduction](../../../docs/experiments/generation-7-opening-production/README.md).
2,000 completed, 500 per Seat, no drops or technical failures; eight workers, 697 seconds.
Independent seed, Seat, identity, denominator, and Wilson checks passed. Report regeneration was
byte-identical. The first scheduling block replayed identically in a fresh process with hash
seed 1.

The changed Policy won 65 of 2,000 games (3.25%, 95% Wilson 2.5581%–4.1212%). The decision is
**loses**: the completed-game upper bound and the attrition-as-wins upper bound are both below
25%. Seat wins were 18, 18, 15, and 14, reported only as diagnostics.

In the 1,935 losses, opening pips were 21.90 against the opponents' 19.81, distinct resources
were 3.52 against 4.72, adjacent ports occurred in 4.65% of games against 7.57% of opponent
Seats, and post-setup settlements were 0.20 against 2.66. The 65 wins had 21.89 pips and 4.38
distinct resources. These profiles are descriptive. Seeds 40000–41999 differ from the
generation-7 audit's 20000–21999, so 65 versus 12 is not a paired estimate of the opening rule.
The cause of the remaining losses stays unknown. The installed model is unchanged. No generation-8
Corpus was generated.

Catan Coach may now claim: generation 7 with four search simulations, exploration disabled, and
initial settlements chosen by production pips won 65 of 2,000 games (3.25%, 95% Wilson
2.5581%–4.1212%) against three Catanatron `ValueFunctionPlayer` opponents on seeds 40000–41999;
it loses under the preregistered rule.
