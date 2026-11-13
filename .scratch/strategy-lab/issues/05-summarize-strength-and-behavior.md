# 05 — Summarize Policy strength and behavior

**What to build:** Pure game-level aggregation for Strength Reports and Behavior Profiles, plus
stable JSON and readable Markdown formatting.

**Blocked by:** 01

**Status:** resolved (shipped in `393a2f8`; corrected 2026-11-13)

## Read first

- `.scratch/strategy-lab/spec.md`, especially Trust Model and Strength Report
- `src/catan_coach/domain/calibration.py` for pure metric/report style
- `src/catan_coach/models/train.py` for human-readable comparison formatting
- Implemented domain result types from issue 01

## Files

- Add `src/catan_coach/domain/experiment_report.py`; import issue 01's types without modifying its
  scheduling implementation
- Add `tests/test_experiment_report.py`
- Formatting may live in `src/catan_coach/models/` only if it remains free of engine imports and I/O

## Required output

`summarize(plan, schedule, outcomes, failures)` returns an immutable report. `outcomes` contains
both completed and dropped games; `failures` contains every technical attempt. Missing scheduled
result keys are inferred from the explicit schedule, never from file counts.

The report contains:

- scheduled, completed, dropped, and failed game counts;
- candidate wins and win rate;
- 95% Wilson interval for candidate win rate;
- the same counts/rates/intervals by candidate Seat;
- final Victory Point mean and distribution for candidate and opponents;
- aggregate candidate Behavior Profiles split into wins and losses;
- aggregate opponent Behavior Profiles;
- complete candidate/Opponent Population names and settings;
- warnings when any Seat has zero completed games or results are incomplete.
- worst-case attrition estimates treating every dropped/terminal game as a candidate loss and then
  as a candidate win;
- a validity flag that is false for any terminal technical failure or a dropped-game rate above 1%.
- dropped/failure counts and rates by candidate Seat so differential attrition is visible.

## Statistical rules

- Games are the independent observations. Never use Plies, Positions, or Seat rows as the sample
  count for uncertainty.
- Use a documented two-sided 95% Wilson interval for proportions. Test known hand-calculated cases.
- Do not report “significant,” “proven,” or “best.”
- Do not compare confidence-interval overlap as a hypothesis test.
- Dropped/failed games are reported and excluded from the win-rate denominator; the denominator is
  printed beside every rate.
- Attrition sensitivity uses all scheduled games: unresolved games are assigned once to losses and
  once to wins, with Wilson intervals for both extremes.
- A positive/negative strength conclusion is forbidden when the report validity flag is false.
- Behavior averages state their denominator (per completed game for the selected group).
- Candidate Seat rotation must be checked against the plan; malformed or duplicate results fail.

## Formatting

Expose separate pure formatters:

```python
report_to_json(report) -> dict[str, object]
format_report(report) -> str
```

Markdown/text must begin with the direct answer: candidate win rate against the named Opponent
Population, interval, and game count. Follow with Seat breakdown, failures, then behavior.

Every behavior section includes:

> Descriptive association only; this does not show that the behavior caused wins.

Do not bury experiment settings: model hashes, search count, exploration, map policy, rules, and
base seed must appear in JSON and a concise provenance block.

## Tests

- Hand-written all-win, no-win, balanced, sparse-Seat, dropped, and failed result sets.
- Wilson interval known values, including `n=1` and `n=0` handling.
- Candidate Seat grouping and denominator checks.
- Duplicate/missing result keys are rejected or clearly marked incomplete according to the
  documented contract.
- One terminal technical failure invalidates the report; one dropped game appears in both attrition
  extremes; more than 1% dropped invalidates the report.
- Setup/profile counts aggregate correctly and wins/losses remain separate.
- JSON output is deterministic and contains no NaN/Infinity.
- Markdown snapshot assertions target required facts, not whitespace or full-table padding.

## Non-goals

- Playing or loading games.
- Reading directories.
- Intervention/difference statistics.
- Elo or multi-Policy rankings.
- Natural-language strategic recommendations.

## Handoff

Document all formulas, denominators, incomplete-result behavior, and public report fields. Include
one short sample report generated from fixtures.
