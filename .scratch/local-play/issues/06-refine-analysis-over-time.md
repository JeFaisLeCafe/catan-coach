# 06 — Refine Analysis over time

**What to build:** An anytime stochastic search that publishes the immediate model Analysis and
then refines it in batches until stopped or its Search Budget expires.

**Blocked by:** None

**Status:** ready-for-agent

- [ ] The immediate GBDT Action ranking is the first published snapshot
- [ ] Search uses Catanatron transitions and the trained model as its leaf evaluator
- [ ] Dice and other chance outcomes are sampled rather than treated as adversarial choices
- [ ] Every snapshot reports simulations, nodes, elapsed time, effective horizon, and uncertainty
- [ ] Work increases monotonically across snapshots for one Position
- [ ] A timed Search Budget stops at the requested wall-clock duration
- [ ] A continuous Search Budget runs until explicitly stopped
- [ ] Changing the Position cancels the old search before its result can reach the new Position
- [ ] Completed Position results are cached with model and search configuration in the key
- [ ] Search never mutates the caller's Position or its random stream
- [ ] Deterministic tiny-tree tests cover streaming, timeout, cancellation, and cache reuse
- [ ] A real-engine benchmark records useful work per second without asserting hardware timing
