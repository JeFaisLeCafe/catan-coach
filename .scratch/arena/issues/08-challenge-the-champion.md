# 08 — Champion Challenge and lineage

**What to build:** the promotion procedure (spec, "Promotion Cycle" steps 5–6), the lineage file
`docs/champions.md` seeded with the current Champion, and one documented cycle run from league 1.

**Blocked by:** 06, 07

**Status:** ready-for-agent

- [ ] Challenge and anchor plans committed before play, fresh seeds
- [ ] Decision computed by the existing Strength Report rules against `0.25`
- [ ] Anchor check: candidate and Champion on identical anchor schedules; paired-bootstrap lower
      bound of the difference above `−0.03`; missing games scored adversarially; an invalid
      anchor run refuses promotion
- [ ] Promotion only after the calibration gate; refusal is published too
- [ ] Lineage row: model hashes, corpus, gate report, challenge report, date
