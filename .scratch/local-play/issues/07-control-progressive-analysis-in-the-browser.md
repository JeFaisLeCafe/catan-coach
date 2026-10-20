# 07 — Control Progressive Analysis in the browser

**What to build:** Stream Progressive Analysis into Coach Mode and game Review with continuous and
pre-budgeted thinking.

**Blocked by:** 03 (Toggle Challenge and Coach Mode), 05 (Review a whole game),
06 (Refine Analysis over time)

**Status:** resolved

- [x] Coach Mode offers immediate-only, timed, and continuous Analysis
- [x] Timed presets include 1, 5, 30, and 120 seconds plus a custom duration
- [x] Continuous Analysis has an explicit Stop control
- [x] The browser updates rankings without resetting the board or blocking Actions
- [x] A human Action cancels the old Position's stream
- [x] The latest complete snapshot remains visible after stopping
- [x] Immediate model and deeper search estimates are visually distinguished
- [x] Work and uncertainty are shown without presenting Catan search as a solved chess depth
- [x] Game Review can assign one Search Budget to all decisions before starting
- [x] Bot Search Budget and Presentation Delay are separate settings and labels
- [x] Browser tests cover timed completion, manual stop, Position-change cancellation, and mode
      toggling while a search is active

## Comments

Coach Mode starts a search as soon as a budget other than Immediate is chosen. Game Review keeps
one chosen budget and applies it to each position after Start this budget. Presentation Delay is
only the pause before a bot Action is shown. Bot Search Budget is how long a bot's Position is
read, and it does not change that pause.
