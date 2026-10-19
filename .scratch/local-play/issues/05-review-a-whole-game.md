# 05 — Review a whole game

**What to build:** A Blunder Report over every meaningful human decision in a saved game.

**Blocked by:** 02 (Play against bots and resume), 03 (Toggle Challenge and Coach Mode)

**Status:** resolved

- [x] A finished or unfinished game can open a Review page
- [x] The report analyzes the Position before every non-forced human Action
- [x] Each decision shows the played Action, best Action, Win Probability, Loss, and reasons
- [x] Decisions are sortable by chronology and by Loss
- [x] Forced Actions do not count as mistakes
- [x] Near-ties, mistakes, and Blunders are visually distinct
- [x] Selecting a row opens the board replay at that Ply
- [x] The report names the model and Search Budget used
- [x] Partial progress is saved so reviewing a long game can resume
- [x] Tests use a stub analyzer with hand-written Losses and one engine replay smoke test
