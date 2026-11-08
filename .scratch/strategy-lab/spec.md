# Spec: Strategy Lab

**Status:** ready-for-agent

## Problem Statement

Catan Coach can predict outcomes and search Positions, but it cannot yet answer two load-bearing
questions:

1. Is the installed Policy actually stronger than the alternatives?
2. Which recurring choices make a Policy stronger, and do those findings survive different Seats,
   boards, opponents, and trading conditions?

Calibration answers a different question. It establishes that predicted Win Probabilities agree
with outcomes under the data-generating Policy. It does not establish that this Policy plays strong
Catan. A perfectly calibrated model of weak play is still weak.

The existing self-play Corpora also make behavioral analysis difficult. They store Observations and
outcomes for model training, not a compact, interpretable account of build order, awards, trades,
robber use, opening resources, and other habits.

The Perfect Play video in `docs/references/` demonstrates a useful presentation: compare named
Policies, intervene on one habit at a time, and report changes in win rate. Its numerical claims
cannot be adopted directly because its code, raw results, and human-game comparison are not
published. Catan Coach should reproduce the method's strongest ideas with a declared, testable
experiment harness.

## Solution

Build a Strategy Lab that runs reproducible Catanatron games from a declared experiment plan and
produces:

- a **Strength Report**: game-level win rates and uncertainty overall and by Seat;
- a **Behavior Profile**: descriptive habits with links to their definitions;
- an **Intervention Comparison**: paired Policy variants that differ by one declared preference.

The first experiment audits generation 7 with four search simulations against Catanatron's
`ValueFunctionPlayer`. Later experiments may compare search settings, model generations, and
explicit Policy interventions.

The Strategy Lab is initially a command-line research tool. Findings earn their way into coaching
UI only after they are reproducible and useful.

## Trust Model

Three claims remain separate:

| Claim | Evidence |
| --- | --- |
| A model forecasts outcomes well | Held-out Calibration and Brier skill |
| A Policy plays strongly | Seat-balanced Strategy Experiments against declared Opponent Populations |
| A habit helps inside the simulator | A preregistered Intervention Comparison |

A Behavior Profile is descriptive. It may suggest an Intervention, but correlation between a habit
and wins is never presented as causal evidence.

## User Stories

1. As a player, I want to know whether the installed Policy beats a declared, reproducible baseline.
2. As a player, I want strategic findings stated in recognizable Catan terms rather than model
   feature identifiers.
3. As a sceptic, I want every finding tied to a complete experiment plan and raw game-level results.
4. As a sceptic, I want uncertainty reported so a small win-rate difference is not called a fact.
5. As a developer, I want every Policy rotated equally through every Seat.
6. As a developer, I want experiment size counted in games, never Positions.
7. As a developer, I want interrupted experiments to resume without replaying completed games.
8. As a developer, I want the same plan and seed to produce the same schedule and game results.
9. As a developer, I want model paths, calibration sidecars, search settings, engine version, and
   source commit recorded with the results.
10. As a researcher, I want a Policy preference to affect Action selection without altering the
    Win Probabilities reported by the model.
11. As a researcher, I want variants compared on the same Seat and board-seed schedule.
12. As a coach, I want useful findings to be promotable into whole-game review later without
    coupling the research harness to the browser.

## Experiment Plan

The version-1 plan compares one **candidate Policy** with an **Opponent Population** containing one
Policy repeated in every other Seat. This intentionally answers a narrow question:

> How often does this candidate win when seated once against three copies of this opponent?

Required plan fields:

- experiment name;
- candidate Policy specification;
- opponent Policy specification;
- player count, initially four;
- games per candidate Seat;
- base seed;
- map policy, initially `corpus_map(seed)`;
- frozen game rules: Victory Points, discard limit, friendly robber, and turn limit;
- source provenance: commit, dirty-tree flag, and dirty-diff hash when applicable.

The scheduler creates the same number of games for each candidate Seat. Seeds are unique. Candidate
Seats are assigned by deterministically shuffling each consecutive block of all four Seats, so Seat
assignment is balanced without assigning one contiguous seed range to one Seat.

A schedule entry contains:

- a **result key** that includes every play-affecting field, including Policy Preferences;
- a **pairing key** that excludes only the candidate's declared Intervention preference and is used
  to pair variants;
- seed, candidate Seat, the four ordered Policy specifications, map policy, frozen game rules, and
  source provenance.

Changing a preference changes the result key but preserves the pairing key. Any other
play-affecting change changes both.

A submitted plan names model/sidecar paths. Before scheduling, an adapter freezes it into an
Experiment Plan with content hashes and source provenance. The output directory is CLI/storage
configuration, not part of play identity. The frozen plan is serialized there before play starts.
Completed games are one machine-readable file each, written atomically. A changed plan must use a
new output directory.

## Policy Specifications

Version 1 supports:

- `value`: Catanatron `ValueFunctionPlayer`;
- `model`: `WinProbabilityPlayer` loaded from a named model and calibration sidecar, with explicit
  search simulation count and exploration setting.

Every specification has a human-readable name. A model specification records a content hash, not
only a path. It explicitly records model path/hash and optional calibration-sidecar path/hash.
Scheduling rejects an unresolved model Policy.

`random` may exist for smoke tests but is not a strength baseline and is excluded from published
claims.

Later tickets add **Policy Preferences**. A preference adds a declared delta to Action-selection
utility. It never edits the model's Win Probability, Analysis, or Calibration. Version 1 preference
categories are:

- settlement;
- city;
- road;
- development-card purchase;
- opening placement adjacent to a port.

The zero-preference Policy is always included. Symmetric positive and negative deltas are preferred
to one hand-picked rule, so reports can show a dose-response rather than a single favorable result.

## Game Result

Each completed game records:

- result key, pairing key, engine seed, map seed, and candidate Seat;
- Policy specification in every Seat;
- winner, final Victory Points, Plies, and turns;
- one Behavior Profile per Seat;
- enough provenance to reproduce the game.

The closed execution outcomes are:

- **CompletedGame**: has one winner and all Seat results/profiles;
- **DroppedGame**: reached the declared turn limit and has no strength outcome;
- **TechnicalFailure**: the runner could not produce a valid game artifact.

Completed and dropped games are versioned result documents. Technical failures are separate
attempt documents. A technical failure is retried once; after two total attempts it is terminal.
Programmer/test failures are not converted into ordinary game failures.

Positions are not stored in the Strategy Lab result. The training Corpus remains a separate
artifact with a separate purpose.

## Behavior Profile

Version 1 records facts available from Catanatron play without inferring intent:

- initial distinct resources, production pips, and port adjacency;
- post-setup settlements, cities, roads, and development cards bought;
- knights played;
- domestic offers, acceptances, and completed trades;
- maritime trades;
- first post-setup purchase or build;
- final Longest Road and Largest Army ownership;
- final Victory Points and win/loss.

Metric definitions live in one reducer and are included in report metadata. Setup settlements and
roads are excluded from post-setup build counts.

Resource production, blocked production, goal inference, and "almost affordable" behavior are
deferred until they can be defined without ambiguity.

The earlier `catan-game` repository is reference material for event names and reducers. It is not a
runtime dependency and does not execute games.

## Strength Report

Reports include:

- games completed, dropped, and failed;
- candidate win rate with a 95% Wilson interval;
- candidate win rate and game count by Seat;
- mean and distribution of final Victory Points;
- the complete candidate and opponent specifications;
- an explicit sentence naming the Opponent Population;
- Behavior Profiles for candidate wins, candidate losses, and opponents.

Every report includes attrition sensitivity bounds that treat every unresolved scheduled game once
as a candidate loss and once as a candidate win. Any terminal technical failure invalidates a
strength claim. A dropped-game rate above 1% also invalidates it. Lower attrition remains visible
and the sensitivity conclusion, not only the completed-game estimate, controls claim wording.

No scalar Elo is reported in version 1. One candidate-versus-population experiment does not identify
a global rating.

## Intervention Comparison

An Intervention Comparison contains two or more plans that share pairing keys and differ in one
Policy Preference. The report:

- verifies that all non-intervention fields match;
- compares win indicators by shared pairing key;
- reports the win-rate difference and a deterministic game-level bootstrap interval;
- reports Behavior Profile changes that confirm the intervention changed play;
- names the simulator, Opponent Population, and preference delta in every conclusion.

The first preregistered experiment is a settlement-versus-city preference sweep. Port preference,
road preference, and development-card preference follow only after the first experiment validates
the interface.

Common seeds align boards and initial random streams but are not claimed to replay identical random
events after Policies choose different Actions.

## Module Design

### Pure domain

`src/catan_coach/domain/experiment.py` owns immutable plan, schedule, result, and report types plus
pure scheduling and aggregation. Its external interface is:

```python
schedule(plan) -> tuple[ScheduledGame, ...]
summarize(plan, schedule, outcomes, failures) -> ExperimentReport
compare(reference, variants, schedules, outcomes, failures, *, seed) -> InterventionReport
```

Callers do not calculate confidence intervals, Seat rotations, or Behavior Profile aggregates.

### Engine adapter

`src/catan_coach/engine/experiment.py` is the only new module that imports Catanatron. It turns a
`ScheduledGame` into one `GameResult`, including behavior reduction while the game runs.

Policy construction stays in the engine package. It reuses `WinProbabilityPlayer`,
`ValueFunctionPlayer`, `corpus_map`, and the existing no-shared-RNG practices.

### Persistence adapter

`src/catan_coach/engine/experiment_store.py` writes the frozen plan and one atomic result per game,
detects completed result keys, and loads results for reporting. File I/O does not enter the domain
module.

### CLI adapter

The CLI exposes separate verbs:

```text
catan-coach lab run PLAN.json
catan-coach lab report EXPERIMENT_DIR
catan-coach lab compare REFERENCE_DIR VARIANT_DIR [VARIANT_DIR ...]
```

`run` resumes by default. `report` never plays games. `compare` refuses incompatible plans.

## Testing Decisions

- Pure scheduling tests assert equal Seat exposure, result/pairing keys, deterministic seeds, and no
  duplicate games.
- Pure statistics tests use hand-written game outcomes and assert intervals and grouping at the
  game level.
- Behavior tests replay a short scripted engine game and assert exact counts, including exclusion
  of setup builds.
- Engine smoke tests use reduced Victory Points or a small game count and carry the `engine` marker.
- Resume tests interrupt after a few games and assert those files are not rewritten.
- Determinism tests run the same tiny plan twice and compare complete result documents after
  excluding wall-clock metadata.
- Intervention tests prove that selection utility changes while model Win Probabilities do not.
- CLI tests assert helpful validation errors and machine-readable artifacts, not terminal spacing.

The full experiment is not run in CI. CI verifies the harness on tiny plans; published reports name
the command and artifacts used for the larger run.

## Out of Scope

- Training or adopting a new model.
- Replacing held-out Calibration as the model-adoption gate.
- A browser dashboard or Strategy Profile in game Review.
- Table Recorder or importing proprietary game logs.
- Natural-language negotiation or an LLM player.
- A second Catan engine.
- Reproducing the Perfect Play video's unpublished implementation or claiming identical results.
- Treating Behavior Profile correlations as causal.
- Elo, leaderboards, or a universal claim that one Policy is best against every population.

## Initial Success Criterion

The milestone is complete when one checked-in report answers, with game-level uncertainty:

> Does generation 7 with four search simulations beat Catanatron's `ValueFunctionPlayer` when the
> candidate is rotated equally through all four Seats on randomized legal boards?

Whatever the answer, it is recorded. A negative result is useful evidence and must not be hidden by
changing the experiment after seeing it.
