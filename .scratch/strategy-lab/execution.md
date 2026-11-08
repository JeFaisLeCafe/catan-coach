# Strategy Lab execution guide

This guide is for implementation agents. The spec is authoritative; each issue narrows one piece.
Do not infer requirements from the issue title alone.

## Required reading for every agent

1. `AGENTS.md`
2. `CONTEXT.md`
3. `.scratch/strategy-lab/spec.md`
4. The assigned issue
5. Every blocker issue's `## Handoff` and implemented interface

## Dependency waves

```text
Wave 1:  01 domain plans/schedule
             |
Wave 2:  02 persistence    03 behavior    05 reports
             |                |
             +-------- 04 one-game runner
                              |
Wave 3:                 06 CLI orchestration
                              |
Wave 4:              08 generation-7 audit
                              |
Wave 5:              07 intervention harness
                              |
Wave 6:              09 settlement/city sweep
```

Issue 07 can technically begin after 06, but run the generation-7 audit first. It establishes the
unmodified reference Policy before preference code expands the execution surface. Issue 09 is the
only ticket authorized to run the first real Intervention sweep.

Within Wave 2, issues 02, 03, and 05 are intentionally file-disjoint and may run in parallel.
Do not let issue 03 redesign issue 01's domain types unless a required spec field is genuinely
missing; report that as a blocker first.

## Agent assignment

Give one issue to one agent. The prompt must include:

- full repository path;
- exact issue path;
- dependency commit SHA(s);
- instruction to read the files listed by the issue;
- permission scope: only that issue, no adjacent cleanup;
- required test commands;
- required final handoff format below.

Never ask one agent to “implement Strategy Lab.” The spec is too broad for a single context.

## Branch and integration discipline

- Start each agent from the latest integration commit containing all blocker issues.
- Parallel Wave-2 agents use isolated worktrees/branches.
- One logical issue equals one commit with a descriptive message.
- Before integration, review the diff against both the issue and repository standards.
- Merge/cherry-pick only after the issue's focused tests and required global checks pass.
- Resolve integration problems in the integration branch; do not make one child agent guess another
  child's unpublished interface.

## Invariants no agent may relax

- Only `src/catan_coach/engine/` imports Catanatron.
- Games are the sampling units for one strength experiment. In Intervention comparisons, the
  independent resampling unit is the whole pairing-key block across variants. Positions, Plies,
  and Seat rows are never independent samples.
- Win Probability and Policy selection utility are different quantities.
- Calibration remains the model-adoption gate.
- A Behavior Profile is descriptive, not causal.
- Every strength claim names the Opponent Population.
- Every experiment rotates the candidate equally through Seats.
- Plans and game results are deterministic, versioned, and resumable.
- Result keys include preferences; pairing keys exclude only the declared Intervention.
- Technical failures retry once, terminal failures invalidate claims, and attrition sensitivity is
  always reported.
- The older `catan-game` project is reference material, never a runtime dependency.
- No large experiment runs in CI.

## Required handoff format

Every implementation agent ends with:

```text
Issue:
Commit:
Files changed:
Public interface:
Invariants enforced:
Tests run and results:
Known limitations:
Assumptions or follow-up needed:
```

“Tests pass” without commands and counts is not sufficient.

## Review gates

### Per issue

- Acceptance bullets are demonstrably covered.
- No behavior from a later issue was added speculatively.
- User errors have actionable messages.
- Tests cross the same interface callers use.
- Determinism tests compare full value objects/documents, not selected fields.

### Before issue 06

- Domain, persistence, behavior, runner, and report interfaces are documented in handoffs.
- A manual integration smoke script can schedule, play, persist, reload, and summarize one game.
- Fast tests, Ruff, and mypy are clean.

### Before issue 08

- Full Python and frontend suites/build are clean.
- The plan is reviewed and committed before any result is inspected.
- The chosen seed range `20000–21999` excludes all known corpus seeds `0–7999`.
- A pilot estimates runtime only; pilot outcomes are not used to tune the final plan.

### After issue 08

- Publish favorable and unfavorable results alike.
- Do not alter the installed model automatically.
- Open the next issue from evidence: Policy improvement if weak, broader Opponent Populations if
  strong, or harness repair if the audit exposed invalid assumptions.

## Suggested orchestrator checks

After each child returns:

1. Read the full diff and handoff.
2. Run the issue's focused tests yourself.
3. Run `uv run ruff format --check .`, `uv run ruff check .`, and `uv run mypy`.
4. Verify `git diff --check`.
5. Update the issue checklist/comments only with evidence from the merged commit.
6. Rebase the next wave on the integrated result.

Do not start a long experiment as a background substitute for a missing implementation test.
