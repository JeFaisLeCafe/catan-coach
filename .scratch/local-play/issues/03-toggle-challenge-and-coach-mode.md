# 03 — Toggle Challenge Mode and Coach Mode

**What to build:** An in-game toggle controlling whether live Analysis is hidden or visible.

**Blocked by:** 01 (Open a local game in the browser)

**Status:** resolved

- [x] Every live game shows a Challenge/Coach toggle
- [x] The toggle can change at any time without changing the Position or action history
- [x] Challenge Mode hides current-Position recommendations and reasons
- [x] Coach Mode immediately ranks legal Actions using the trained model
- [x] A missing trained model is stated and the Baseline fallback is visibly labelled
- [x] Analysis names the Seat, model, Win Probability, Loss, and reasons
- [x] Forced Actions are presented as forced, not as choices
- [x] Switching back to Challenge Mode removes live Analysis from view
- [x] The selected mode survives a page reload but is not recorded as a Ply
- [x] Tests cover both directions of the toggle and unchanged game history
