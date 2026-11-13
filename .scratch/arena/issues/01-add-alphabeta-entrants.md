# 01 — Add AlphaBetaPlayer as a Policy kind

**What to build:** an `alphabeta` Policy kind backed by Catanatron's `AlphaBetaPlayer`, with its
search depth declared in the plan and frozen into provenance.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] `PolicyKind` accepts `alphabeta`; plan parsing requires an integer `depth` for it and rejects
      it for other kinds
- [ ] Only `engine/` imports `AlphaBetaPlayer`
- [ ] A Strategy Lab plan with an `alphabeta` opponent runs and reports
- [ ] Engine-marked smoke test: two small games complete
