# 01 — Open a local game in the browser

**What to build:** Adapt the pinned Catanatron React board and local Flask game server into Catan
Coach, served by one command with durable local persistence.

**Blocked by:** None

**Status:** resolved

- [ ] `uv run catan-coach play` starts the local application and opens it in a browser
- [ ] The clickable board and legal Action controls come from the pinned Catanatron UI
- [ ] Python code outside `engine/` does not import Catanatron
- [ ] Games use a persistent local SQLite database rather than in-memory storage
- [ ] The home page lists unfinished and finished games
- [ ] Closing and restarting the application preserves games
- [ ] Replay can visit any recorded Ply
- [ ] Frontend and backend have one documented development command each
- [ ] Existing analyzer commands remain compatible
- [ ] Backend, frontend, and one browser smoke test are green
