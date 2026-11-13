# 02 — Validate a narrative against facts

**What to build:** the validator in the spec ("Claim classes"), pure and testable without an LLM.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Rejects unknown fact ids and templates not allowed for the fact's class
- [ ] Rejects section ids outside the fixed set; titles come from code
- [ ] Rejects digits, percentages, and causal verbs in every LLM-written string
- [ ] A causal template is allowed only on an interventional fact with a `supported_direction`
- [ ] Renders each claim's sentence from its fact; the rendered text is what the page shows
- [ ] Each rejection explains which sentence failed and why
