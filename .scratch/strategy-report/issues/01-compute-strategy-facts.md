# 01 — Compute Strategy facts

**What to build:** pure `domain/` code that turns an Arena report and Intervention comparisons into
`facts.json`: ladder, head-to-head, Strategy Profile themes, Intervention results, each fact with
id, class, value, interval, sample size, and source.

**Blocked by:** Arena 05

**Status:** ready-for-agent

- [ ] Themes as listed in the spec, with intervals
- [ ] Stable, readable fact ids (e.g. `profile.production-features-s4.cities.wins`)
- [ ] Byte-identical output from identical inputs
