# Spec: Position Analyzer

**Status:** ready-for-agent

## Problem Statement

I want to get better at Catan, and I have no way to tell whether a move I made was good. I can
replay a game in my head and argue with myself, but nothing tells me that the settlement I placed
on turn three cost me eight points of win probability, or that the trade I refused was the real
mistake. Chess players have had engine analysis for decades; Catan players have opinions.

The four previous attempts at this failed the same way: they produced bots whose strength was
unknown, so even when a bot disagreed with me I had no reason to believe it over myself. An
analyzer nobody trusts is worse than no analyzer, because it wastes the time you spend arguing
with it.

## Solution

Given a Position, rank every legal Action by Win Probability and show the Loss of each against
the best one. Render the board alongside so the numbers attach to something visible.

Trust comes from Calibration, not from confidence: the Win Probability is produced by a model
trained on the outcomes of real self-play games, and that model is only adopted if it beats the
existing Baselines on held-out games through the calibration harness. The harness already exists
and already reports the bar to clear.

Positions arrive by replaying a saved game to a chosen Ply, so I can ask "what should I have done
here?" about any moment in any game the engine can produce.

## User Stories

1. As a player, I want to load a saved game and jump to any Ply, so that I can ask about the exact
   moment I think I went wrong.
2. As a player, I want every legal Action at that Position ranked by Win Probability, so that I can
   see what the alternatives were worth rather than only whether my move was "bad".
3. As a player, I want each Action's Loss against the best Action, so that I can tell a marginal
   preference from a real mistake.
4. As a player, I want the Win Probability stated for my Seat specifically, so that the number
   means "my chance of winning" and not something abstract.
5. As a player, I want a rendered image of the Position next to the ranking, so that I can connect
   an action label like `BUILD_SETTLEMENT 42` to a place on the board.
6. As a player, I want the analysis to return in seconds rather than minutes, so that I can work
   through a whole game without losing patience.
7. As a player, I want to know how much to trust a number, so that I can tell a confident call from
   a coin flip.
8. As a sceptic, I want to see the model's Calibration on held-out games, so that I can verify that
   positions it calls 70% are actually won about 70% of the time.
9. As a sceptic, I want to see the model measured against the Baselines, so that I know it has
   learned more than "who is ahead on points".
10. As a sceptic, I want both Calibration and Discrimination reported, so that I am not fooled by a
    model that is perfectly calibrated and completely useless.
11. As a developer, I want to generate a Corpus of self-play games of a size I choose, so that I can
    trade training time against model quality.
12. As a developer, I want Corpus generation to use strong play, so that the model learns the win
    probability of good Catan rather than of random flailing.
13. As a developer, I want every Seat's perspective recorded per Position, so that the model does
    not absorb Seat-order advantage as a constant.
14. As a developer, I want the Corpus split into train and validation by game and never by Position,
    so that positions from the same game cannot leak across the split.
15. As a developer, I want Corpus generation to be resumable and parallel, so that a large run is
    not lost to one interruption.
16. As a developer, I want the trained model to load behind the existing `WinProbabilityModel` port,
    so that the analyzer does not know or care which implementation it is using.
17. As a developer, I want to swap in a Baseline anywhere the real model is used, so that I can
    always see what the analyzer looks like with a known-bad model.
18. As a developer, I want a reason attached to each Win Probability, so that the output teaches me
    something rather than only judging me.
19. As a developer, I want the analyzer covered by tests that use a stub model, so that its ranking
    and Loss arithmetic are verified without dice randomness or a trained model.
20. As a developer, I want a single command that reports the current model against every Baseline,
    so that "is it any good" is one command and not a research project.
21. As a player, I want positions saved and reloaded losslessly, so that I can come back to an
    interesting one later or share it.
22. As a player, I want to be told when a Position has only one legal Action, so that I am not shown
    a ranking of length one and invited to think about it.

## Implementation Decisions

**The Corpus.** Self-play games are generated with catanatron's `ValueFunctionPlayer`, which is
fast and second-strongest on the published ladder. Every sampled Position is recorded once per
Seat, each row being that Seat's Observation plus a binary label for whether that Seat eventually
won. Rows are written to parquet. Sampling may use a Ply stride to reduce redundancy between
near-identical consecutive Positions.

Corpus size is reasoned about in **games, not rows**: every Position within a game shares a single
outcome, so the effective independent sample size is the number of games. Measured cost is about
0.52s per 4-player game, so a 10,000-game Corpus is roughly 90 minutes single-threaded and
parallelizes across cores.

**Train/validation split is by game.** A game's rows go entirely to one side or the other. Splitting
by row would put near-identical positions on both sides and produce a meaningless validation score.

**The model is gradient-boosted trees, not a neural network.** The Observation is a tabular vector
of ~1,000 floats, which is exactly what GBDTs are best at. They train in seconds on CPU, need no
GPU, and expose per-feature contributions that serve directly as the "reason" shown next to each
Win Probability. A previous attempt reached for neural networks and drowned in diagnostics.

**The model implements the existing `WinProbabilityModel` port**, taking a batch of Observations
and returning a batch of probabilities. Batching is not an optimisation detail: the analyzer scores
every legal Action in one call.

**The analyzer** copies the Position once per legal Action, executes that Action on the copy,
converts each resulting Position to an Observation, and scores the whole batch in a single call.
It returns an Analysis: the Actions ranked by Win Probability, each with its Loss against the best.

**No rollouts anywhere in the analyzer.** Measured: 25 playouts per Action costs about 52 seconds
multithreaded and still carries roughly 10 percentage points of standard error. Reaching 1 point of
precision would need about 2,500 playouts per Action, roughly an hour per Position. Rollouts are
therefore rejected as the source of Win Probability.

**Care is required when copying a game.** The engine's random stream lives inside the game state, so
a copied game replays identical dice. This does not affect the analyzer, which applies one Action
and stops, but any future code that plays a copy forward must reseed.

**Position input** uses the engine's existing full-fidelity JSON serialization to save and restore,
and replays a recorded Action log to reach a chosen Ply. No new position format is invented.

**Rendering** wraps the engine's existing headless renderer, which returns an RGB array from a
Position with no window and no display. It is written to PNG.

**The CLI** names a saved game and a Ply, and prints the ranked table plus the path to the rendered
PNG. It is a thin adapter and holds no logic of its own.

**The engine seam holds.** Only `src/catan_coach/engine/` imports catanatron; the domain, the
models, and the calibration harness stay ignorant of it. This is what keeps ADR 0001's escape route
open.

## Testing Decisions

A good test here asserts externally visible behaviour: the order of an Analysis, the arithmetic of a
Loss, whether a model beats a Baseline. It does not assert model weights, row counts, internal call
sequences, or anything that would change when an implementation is improved rather than broken.

**Seam 1 — the analyzer.** `analyze(position, model)` is tested with a **stub** `WinProbabilityModel`
returning hand-written probabilities. Because the port already exists, this makes the analyzer fully
deterministic: ranking order, Loss arithmetic, ties, and the single-legal-action case are all
asserted exactly, with no dice randomness and no trained model involved. This is the primary seam
and should carry most of the tests.

**Seam 2 — the calibration harness.** Corpus generation and model training are judged only through
`calibration_report` on held-out games: does the model beat `constant(1/4)` and
`vp-share` on Brier skill, and is its reliability curve better? Prior art is
`tests/test_engine.py::TestBaselinesOnRealPositions`, which already establishes the bar at +0.186
Brier skill for the VP Baseline over the constant one.

**Thin adapters get smoke tests only.** Position loading gets a round-trip assertion, since the
engine's serialization makes that nearly free. Rendering asserts an image of the right shape and
dtype comes back. The CLI asserts it runs and produces output.

**Engine-touching tests are marked** `engine` so the pure suite stays instant. The existing split is
42 pure tests in 0.34s against 63 total in about 9s, and that property is worth preserving.

**The pin tripwire stays.** `tests/test_engine.py` asserts the catanatron version and imports every
module depended upon, so a drifted git pin fails loudly rather than subtly.

## Out of Scope

- A board editor for building Positions by hand. The position format exists, so this is pure UI and
  can be added later without touching the core.
- Any web interface.
- An ELO or ranking system, and the bot ladder that would feed it.
- Blunder reports over a whole game. The Analysis makes them possible; presenting them is separate.
- Playing a full game against a calibrated bot.
- Importing games from external sites such as colonist.io.
- Player-to-player trade negotiation strategy as a distinct concern. Trade Actions are ranked like
  any other Action, but nothing models an opponent's willingness to accept.
- Any change to catanatron itself. It is a pinned dependency, not a fork.

## Further Notes

The deferred features are deliberately ordered so that each is a presentation of the analyzer rather
than new machinery: a Blunder report is the analyzer applied to every Ply of a game; a calibrated
sparring bot is the analyzer with added noise or shallower search; an ELO ladder is how the model's
strength gets validated independently of Calibration.

Reversibility is retained by the engine seam. If GPL-3.0 (ADR 0003) or dependence on an unreleased
upstream branch (ADR 0004) becomes a problem, only `engine/` is rewritten — though the Corpus and
model, being tied to the engine's Observation layout, would need regenerating.
