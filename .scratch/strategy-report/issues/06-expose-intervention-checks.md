# 06 — Expose Intervention validity and manipulation checks

**What to build:** extend `catan-coach lab compare --json` so each variant comparison records, per
behavior field, the paired difference with its 95% bootstrap interval, the manipulation-check
result for the preferred category, the comparison's validity, and the attrition-bound sign check.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] `VariantComparison` gains interval and check fields; older JSON still loads
- [ ] Manipulation check follows issue 09's definition (paired difference positive, interval
      excludes zero)
- [ ] Byte-identical regeneration; JSON and Markdown agree
- [ ] Issue 09's published comparison is regenerated with these fields when it exists
