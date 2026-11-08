# 06 — Refine Analysis over time

**What to build:** An anytime stochastic search that publishes the immediate model Analysis and
then refines it in batches until stopped or its Search Budget expires.

**Blocked by:** None

**Status:** resolved

- [x] The immediate GBDT Action ranking is the first published snapshot
- [x] Search uses Catanatron transitions and the trained model as its leaf evaluator
- [x] Dice and other chance outcomes are sampled rather than treated as adversarial choices
- [x] Every snapshot reports simulations, nodes, elapsed time, effective horizon, and uncertainty
- [x] Work increases monotonically across snapshots for one Position
- [x] A timed Search Budget stops at the requested wall-clock duration
- [x] A continuous Search Budget runs until explicitly stopped
- [x] Changing the Position cancels the old search before its result can reach the new Position
- [x] Completed Position results are cached with model and search configuration in the key
- [x] Search never mutates the caller's Position or its random stream
- [x] Deterministic tiny-tree tests cover streaming, timeout, cancellation, and cache reuse
- [x] A real-engine benchmark records useful work per second without asserting hardware timing

## Comments

The first snapshot is the model ranking with zero simulations. Later snapshots sample dice and
hidden outcomes, and the seat to move keeps the sampled Action that wins for them. A timed budget
is checked between simulations. Stopping or replacing the search drops a snapshot that has not
been published. Search uses whichever model is currently installed; see `docs/model.md` for its
provenance and held-out result.
