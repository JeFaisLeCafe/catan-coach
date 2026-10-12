# 05 — Review a whole game

**What to build:** A Blunder Report over every meaningful human decision in a saved game.

**Blocked by:** 02 (Play against bots and resume), 03 (Toggle Challenge and Coach Mode)

**Status:** ready-for-agent

- [ ] A finished or unfinished game can open a Review page
- [ ] The report analyzes the Position before every non-forced human Action
- [ ] Each decision shows the played Action, best Action, Win Probability, Loss, and reasons
- [ ] Decisions are sortable by chronology and by Loss
- [ ] Forced Actions do not count as mistakes
- [ ] Near-ties, mistakes, and Blunders are visually distinct
- [ ] Selecting a row opens the board replay at that Ply
- [ ] The report names the model and Search Budget used
- [ ] Partial progress is saved so reviewing a long game can resume
- [ ] Tests use a stub analyzer with hand-written Losses and one engine replay smoke test
