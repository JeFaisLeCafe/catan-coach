# 10 — Improve the Policy after the generation-7 strength audit

**Status:** ready-for-agent

**Blocked by:** 08 (completed)

## Evidence

The preregistered [audit](../../../docs/experiments/generation-7-vs-value/README.md) completed
2,000 games with no attrition. Generation 7 with four search simulations won 2 games (0.60%;
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
