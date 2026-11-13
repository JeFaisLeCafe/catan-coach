# 02 — Validate a narrative against facts

**What to build:** the validator in the spec ("Claim classes"), pure and testable without an LLM.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Rejects wrong numbers, uncited numbers, unknown fact ids, and causal verbs on non-interventional facts
- [ ] Rejects interventional claims whose manipulation check failed
- [ ] Each rejection explains which sentence failed and why
