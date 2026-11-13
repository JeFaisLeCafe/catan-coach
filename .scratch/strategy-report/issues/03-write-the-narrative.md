# 03 — Write the narrative with Claude

**What to build:** the narrative step: committed prompt, Anthropic SDK client behind a small port,
cache by facts + prompt + model hash, one retry with the validator's rejection fed back, then fall
back to no narrative.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Read the `claude-api` skill before choosing the default model id and SDK calls
- [ ] Tests use a fake client; no network
- [ ] API key from environment only; never logged or stored
