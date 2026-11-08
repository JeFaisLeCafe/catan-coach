# 07 — Compare Policy Interventions

**What to build:** Policy-only preference deltas and a paired comparison report. This ticket builds
the harness; issue 09 owns the first real sweep.

**Blocked by:** 04, 05, 06

**Status:** ready-for-agent

## Read first

- `.scratch/strategy-lab/spec.md`, especially Policy Specifications and Intervention Comparison
- `CONTEXT.md` definition of Intervention
- `src/catan_coach/engine/model_player.py`
- `src/catan_coach/engine/scoring.py`
- Completed experiment interfaces and reports from issues 01–06
- `docs/references/perfect-play-200-million-games.md`

## Design constraint

A Policy Preference changes **Action selection utility**, not model Win Probability.

For Action `a`:

```text
selection_utility(a) = win_probability(a) + declared_preference_delta(a)
```

The original calibrated Win Probability remains in Analysis, artifacts, and explanations. Never
save or display selection utility as Win Probability.

## Files

- Add a focused selection-policy module under `src/catan_coach/engine/`
- Update `WinProbabilityPlayer` only through a small optional interface; zero preferences must keep
  existing behavior byte-for-byte
- Add pure comparison statistics to the experiment domain/report module
- Extend CLI with `catan-coach lab compare`
- Add focused unit, engine, and CLI tests

## Preference interface

- One internal interface returns a delta for a legal Action in a Position.
- Version 1 categories: settlement, city, road, development-card purchase, and opening placement
  adjacent to a port.
- Category matching lives in the engine adapter because it knows Catanatron Actions/board geometry.
- Multiple deltas add explicitly; no hidden normalization or clipping.
- Tie-breaking remains deterministic and documented.
- Version 1 rejects nonzero preferences when `search_simulations > 0`. Applying a preference only
  at the root would not define one consistent Policy throughout search.

## Comparison statistics

Match games by the `pairing_key` defined in issue 01. Result keys must differ; pairing keys must be
equal. Verify all non-preference fields independently before comparison.

The pure comparison interface accepts each plan's explicit schedule, completed/dropped outcomes,
and technical-failure attempts. It must not infer missing games from directories or completed
pairs alone.

For each variant report:

- completed matched pairs and missing keys;
- candidate win-rate difference from reference;
- deterministic 95% paired bootstrap interval over pairing keys;
- Seat-specific differences;
- Behavior Profile deltas proving whether selection behavior changed.
- dropped and terminal-failure counts by side, attrition sensitivity bounds, and validity.

Bootstrap randomness uses NumPy `PCG64` with an explicit report seed, 10,000 replicates, percentile
intervals at 2.5% and 97.5%, and `numpy.quantile(..., method="linear")`. It resamples whole pairing
keys and never Positions or Seat rows. Zero pairs is an error. A degenerate difference returns a
zero-width interval. Seat-specific intervals resample only pairs within that Seat.

Common engine/map seeds align initial conditions but do not imply identical random events after
Policies diverge.

Compatible schedules with missing outcomes are not an ordinary unpaired comparison. For every
pairing key, preserve observed win indicators and assign unresolved outcomes adversarially:

- lower effect bound: unresolved variant = loss, unresolved reference = win;
- upper effect bound: unresolved variant = win, unresolved reference = loss.

Report both bounds. A positive/negative effect claim requires the corresponding worst-case bound
to retain that sign. Any terminal technical failure or more than 1% dropped games on either side
invalidates the comparison. Structurally incompatible plans are refused before this sensitivity
analysis.

## CLI

```text
catan-coach lab compare REFERENCE_DIR VARIANT_DIR [VARIANT_DIR ...] \
  [--seed N] [--json OUT.json] [--markdown OUT.md]
```

Refuse incompatible plans and name every mismatched field. Refuse an unpaired comparison rather
than falling back to independent intervals.

## Tests

- Zero preferences preserve existing chosen Actions under exact and near ties.
- Positive settlement/city deltas alter only matching legal Actions.
- Opening port preference uses actual port adjacency and only during setup.
- Model predictions/explanations are identical with and without preferences.
- Nonzero preferences with search are rejected before play.
- Paired bootstrap is deterministic, uses pairing keys as units, and covers zero/degenerate pairs
  plus Seat-specific resampling.
- Structurally incompatible schedules fail with useful errors.
- Compatible schedules with missing outcomes produce the declared adversarial bounds; terminal
  failures and excessive drops invalidate the comparison.
- Behavior deltas and win-rate deltas have correct signs on hand-written fixtures.

## Interpretation rules

Generated Markdown must say:

> This Intervention estimates an effect inside the declared simulator and Opponent Population. It
> is not automatically a causal claim about human games.

Do not title a variant “best strategy.” Name the exact preference and magnitude.

## Non-goals

- Goal inference or “almost affordable” preferences.
- Natural-language negotiation.
- Tuning deltas to maximize the same reported games.
- Adding findings to Coach Mode.
- Reproducing unpublished Perfect Play settings.
- Running or tuning the first real preference sweep.

## Handoff

Report the preference interface, exact search rejection, comparison commands, bootstrap contract,
and fixture evidence that selection changes while Win Probability does not.
