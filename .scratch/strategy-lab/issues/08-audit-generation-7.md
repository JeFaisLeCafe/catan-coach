# 08 — Audit generation 7 against the ValueFunction baseline

**What to build:** The first real Strategy Experiment and a checked-in, reproducible report that
answers whether generation 7 with search beats Catanatron's `ValueFunctionPlayer`.

**Blocked by:** 06

**Status:** resolved

## Read first

- `.scratch/strategy-lab/spec.md`
- Every completed handoff from issues 01–06
- `docs/model.md`
- `docs/references/perfect-play-200-million-games.md`
- Repository rule: no positive claim without the relevant harness evidence

## Preregister before the large run

Add and review one plan file before inspecting results. It must specify:

- candidate: root `model.txt` plus `model.calibration.json`;
- candidate search simulations: 4;
- candidate exploration: false;
- opponent: Catanatron `ValueFunctionPlayer`;
- four players, candidate rotated equally through all Seats;
- randomized legal board from `corpus_map(seed)`;
- standard 10 Victory Points and current standard rule settings;
- base seed `20000`, producing seeds `20000–21999` and avoiding every known corpus seed `0–7999`;
- 500 games per candidate Seat, 2,000 games total;
- output directory under `data/experiments/`, which remains untracked except for the final compact
  plan/report artifacts.

## Preregistered primary analysis

- Primary estimand: candidate win rate minus `0.25`, the equal-strength share at this declared
  four-player table.
- Precision target: approximately ±2 percentage points at a 25% win rate and 95% confidence.
  The conservative normal approximation gives
  `1.96² * 0.25 * 0.75 / 0.02² = 1801`; round up to 2,000 and balance 500 per Seat.
- “Beats” requires the completed-game Wilson lower bound above `0.25`, and the worst-case attrition
  Wilson lower bound (all unresolved games counted as candidate losses) above `0.25`.
- “Loses” requires the completed-game Wilson upper bound below `0.25`, and the opposite attrition
  extreme (all unresolved games counted as candidate wins) below `0.25`.
- Otherwise the result is “inconclusive.”
- Any terminal technical failure or more than 1% dropped games invalidates the strength conclusion.
- Seat-specific results are secondary diagnostics; no Seat-specific significance claim is made.
- Do not inspect interim win outcomes or stop early.

If runtime makes the target infeasible, check in a pilot report clearly labelled exploratory and
leave this ticket unresolved.

## Required execution

1. Commit/freeze the plan before running it.
2. Require a clean source tree and record its commit.
3. Run the fast/full CI harness on the code that will execute the experiment.
4. Run or resume to the preregistered count.
5. Generate JSON and Markdown reports from stored results.
6. Independently verify schedule balance, model hashes, completed counts, failures, and report
   denominators.
7. Record the exact command, source commit, environment, elapsed time, and artifact hashes.

## Report location

Check in:

```text
docs/experiments/generation-7-vs-value/
  plan.json
  report.json
  report.md
```

Do not check in large per-game artifacts. The report must say where local raw artifacts were
written and how to regenerate them.

## Required report content

- Direct answer with win rate, 95% interval, and completed game count.
- Preregistered beat/lose/inconclusive decision plus both attrition extremes.
- Candidate results by Seat.
- Drops/failures and whether they are concentrated by Policy or Seat.
- Candidate Behavior Profiles in wins and losses, labelled descriptive.
- Opponent Population and all Policy settings.
- Model/sidecar hashes, engine pin, source commit, seeds, map policy, and rule settings.
- Limitations: simulated opponent, one Opponent Population, no human-game validation, and no causal
  claim from behavior correlations.

## Decision rules

- Publish the result whether favorable, neutral, or unfavorable.
- Do not change the installed model based on this experiment; model adoption remains Calibration.
- If generation 7 loses, open a separate issue for Policy improvement before generating more
  self-play from it.
- If it wins, the exact claim is only that it beat this Opponent Population under this plan.
- Do not run issue 07's interventions on these same games; intervention plans are separate.

## Verification

- A second report generation from the same raw results is byte-for-byte identical.
- Counts in JSON and Markdown agree.
- Candidate Seat counts are equal.
- Every four-game scheduling block contains all candidate Seats once; seeds are unique and within
  `20000–21999`.
- The checked-in report passes a small schema/fixture test so future refactors cannot silently
  reinterpret it.
- Run all repository tests, Ruff, mypy, frontend tests, and production build before checkpointing.

## Non-goals

- Improving code while the experiment is running.
- Retuning search after seeing results.
- Training generation 8.
- User-interface changes.
- Comparing against humans or Perfect Play's unpublished Tuned player.

## Handoff

End with the exact evidence-backed sentence Catan Coach may now claim, or state plainly that the
planned experiment was not completed. Include artifact hashes and the source commit.

## Completed audit — 2026-11-10

Source: `26378264ba6681fa675bf14765f03c0d020af92c` (clean).
[Artifacts, hashes, environment, and reproduction](../../../docs/experiments/generation-7-vs-value/README.md).
2,000 completed, 500 per Seat, no drops or technical failures; eight workers, 618 seconds.
Independent seed/Seat/identity/denominator/Wilson checks and identical report regeneration passed.
Python: 179 fast tests and 282 full tests; frontend: 97 tests and production build; Ruff and mypy clean.

Catan Coach may now claim: generation 7 with four search simulations and exploration disabled
won 12 of 2,000 games (0.60%, 95% Wilson 0.3436%–1.0458%) against three Catanatron
`ValueFunctionPlayer` opponents on seeds 20000–21999; it loses under the preregistered rule.
The installed model is unchanged. Issue 10 records the required Policy-improvement follow-up.
