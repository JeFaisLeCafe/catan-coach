# 03 — Fit Ratings with intervals

**What to build:** the Plackett–Luce first-choice Rating fit, Seat effects, bootstrap intervals,
and head-to-head shares, in `domain/` (see spec, "Rating").

**Blocked by:** none

**Status:** ready-for-agent

- [ ] Maximum-likelihood fit with ratings centred to mean zero and one effect per Seat
- [ ] Fixed-seed 10,000-replicate game-level bootstrap for 95% intervals
- [ ] Display scale (`400 / ln 10`) and expected win rate against three average Entrants
- [ ] Head-to-head share with Wilson interval for every pair
- [ ] Tests: synthetic known strengths recovered in order and covered; equal strengths overlap;
      Seat effects recovered; Entrant order does not change the fit
