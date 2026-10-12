# 02 — Play against bots and resume

**What to build:** A standard local game with one human Seat and two or three Catanatron bots,
autosaved after every Ply.

**Blocked by:** 01 (Open a local game in the browser)

**Status:** ready-for-agent

- [ ] A standard game seats three or four players with exactly one human
- [ ] Bot type and strength are selectable from the server's registered players
- [ ] A human can complete setup, main play, discard, robber, development-card, and trade Actions
- [ ] Bots act automatically only when their Seat must act
- [ ] The bot's real compute time is not confused with Presentation Delay
- [ ] Every completed Ply is durable before the next Seat acts
- [ ] Reloading the page resumes the latest Position
- [ ] A finished game names the winner and opens in replay
- [ ] Private hands are redacted outside the active human perspective
- [ ] An end-to-end test completes a reduced-target human-versus-bot game
