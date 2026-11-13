# 03 — Fit Ratings with intervals

**What to build:** the Plackett–Luce first-choice Rating fit, Seat effects, bootstrap intervals,
and head-to-head shares, in `domain/` (see spec, "Rating").

**Blocked by:** none

**Status:** ready-for-agent

- [ ] Penalized maximum-likelihood fit (Gaussian, sd 2); ratings and Seat effects each sum to zero
- [ ] Fixed-seed 10,000-replicate block bootstrap (blocks of four same-seed rotations)
- [ ] Display scale (`400 / ln 10`) and expected win rate against three average Entrants
- [ ] Head-to-head share with block-bootstrap interval for every pair
- [ ] An Entrant with zero wins gets a finite rating, including in every bootstrap replicate
- [ ] Tests: synthetic known strengths recovered in order and covered; equal strengths overlap;
      Seat effects recovered; Entrant order does not change the fit
