# 09 — Run the settlement-versus-city Intervention

**What to build:** The first preregistered Policy Intervention, estimating how a small
settlement/city selection preference changes simulated behavior and win rate.

**Blocked by:** 07, 08

> **Amendment 2026-11-13, before any game was played.** The candidate is the installed
> production-features model (`model.txt` sha256 `616ce2002fb21ec96335637fcf4e972e0efa29b700febedc4f2655490a8ce2e8`, sidecar `f31d0daacd9e08b295854ac81631a22125e988080b2fdde49a1dfcc5d1cce3b2`), not
> generation 7. The plans already loaded the root `model.txt`; only their candidate name changes.
> Reason: generation 7 wins 0.6% at search 4, so a preference effect on it says little about a
> Policy anyone would use. Everything else below — deltas, seeds `30000`+, counts, bootstrap seed,
> manipulation check, validity rules — is unchanged. Read "generation 7" below as
> "the production-features model".

**Status:** ready-for-agent

## Read first

- `.scratch/strategy-lab/spec.md`
- Issue 07 handoff and comparison contract
- `docs/experiments/generation-7-vs-value/report.md`
- `docs/references/perfect-play-200-million-games.md`

## Scientific question

Inside Catanatron, against three `ValueFunctionPlayer` opponents, how do symmetric `+0.05`
Action-selection preferences for settlements or cities change generation 7's build behavior and
win rate relative to an unbiased generation-7 Policy?

This is not a reproduction of Perfect Play's unpublished weights and not a claim about human games.

## Preregistered plans

Commit three plan files before running any games:

| Variant | Search | Settlement delta | City delta |
| --- | ---: | ---: | ---: |
| reference | 0 | 0.00 | 0.00 |
| settlement preference | 0 | +0.05 | 0.00 |
| city preference | 0 | 0.00 | +0.05 |

All use:

- root generation-7 model and calibration sidecar;
- `ValueFunctionPlayer` in the other three Seats;
- four players and standard rules;
- `corpus_map(seed)`;
- exploration disabled;
- base seed `30000`;
- paired-bootstrap report seed `20261109`;
- 1,000 games per candidate Seat, 4,000 pairing keys per variant;
- identical pairing keys, seeds, candidate Seats, boards, opponent, model hashes, and rules;
- clean source commits.

Each variant therefore runs 4,000 games; the full sweep is 12,000 games. Do not reduce the count
after looking at outcomes. If runtime is infeasible, publish only a clearly labelled pilot and
leave the ticket unresolved.

## Why search is zero

Issue 07 rejects preferences with search because applying a bias only at the root would not define
one consistent Policy. This experiment isolates one-ply model-based Action selection. It must not
be compared numerically with issue 08's four-simulation strength audit as if only the preference
changed.

## Analysis

Compare each preference variant separately with reference by pairing key. Report:

- paired candidate win-rate difference and the fixed 10,000-replicate 95% bootstrap interval;
- Seat-specific paired differences as secondary diagnostics;
- paired changes in settlement builds, city builds, first post-setup build category, final awards,
  and all other Behavior Profile fields;
- missing/dropped/failure counts and attrition extremes;
- complete provenance and plan differences.

Do not choose a “best” variant. Every 95% interval is marginal for its one named comparison; no
family-wise coverage is claimed, and no combined “at least one preference works” conclusion is
allowed.

## Manipulation check

Interpret an outcome difference only if the preferred behavior changed in the intended direction:

- settlement variant: paired settlement-build difference is positive;
- city variant: paired city-build difference is positive;
- the corresponding 95% paired bootstrap interval excludes zero.

If the check fails, conclude that `+0.05` did not create a reliable Intervention under this Policy.
Do not select a larger delta after seeing win outcomes. A new magnitude requires a new ticket and
new seed range.

## Artifact location

Check in compact artifacts:

```text
docs/experiments/settlement-city-preference/
  reference-plan.json
  settlement-plan.json
  city-plan.json
  comparison.json
  comparison.md
```

Keep per-game artifacts under untracked `data/experiments/`.

## Validity rules

- Any terminal technical failure invalidates the corresponding comparison.
- More than 1% dropped games invalidates it.
- A directional effect claim also requires issue 07's adversarial missing-outcome bound to retain
  the same sign.
- Common seeds align initial conditions but do not imply identical rolls after Policies diverge.
- Behavior changes establish that the simulator Policy changed; outcome changes estimate an effect
  only inside this engine and Opponent Population.
- Publish null and unfavorable results.

## Verification

- Plans were committed before result inspection.
- Exactly 4,000 pairing keys are shared across all variants.
- Result keys differ where preferences differ.
- Candidate Seat counts are 1,000 each per variant.
- Report regeneration is byte-for-byte deterministic.
- JSON and Markdown counts/differences agree.
- Full repository quality and test suites pass at the source commits used.

## Non-goals

- Search-enabled Intervention.
- Port, road, development-card, trade, robber, or affordability preferences.
- Coaching UI or fixed strategic advice.
- Training/adopting a model from the result.

## Handoff

State whether each manipulation check passed, give both paired outcome estimates and intervals, and
write only the narrow simulator-specific finding supported by the artifacts.
