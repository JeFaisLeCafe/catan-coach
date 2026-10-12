# 07 — Control Progressive Analysis in the browser

**What to build:** Stream Progressive Analysis into Coach Mode and game Review with continuous and
pre-budgeted thinking.

**Blocked by:** 03 (Toggle Challenge and Coach Mode), 05 (Review a whole game),
06 (Refine Analysis over time)

**Status:** ready-for-agent

- [ ] Coach Mode offers immediate-only, timed, and continuous Analysis
- [ ] Timed presets include 1, 5, 30, and 120 seconds plus a custom duration
- [ ] Continuous Analysis has an explicit Stop control
- [ ] The browser updates rankings without resetting the board or blocking Actions
- [ ] A human Action cancels the old Position's stream
- [ ] The latest complete snapshot remains visible after stopping
- [ ] Immediate model and deeper search estimates are visually distinguished
- [ ] Work and uncertainty are shown without presenting Catan search as a solved chess depth
- [ ] Game Review can assign one Search Budget to all decisions before starting
- [ ] Bot Search Budget and Presentation Delay are separate settings and labels
- [ ] Browser tests cover timed completion, manual stop, Position-change cancellation, and mode
      toggling while a search is active
