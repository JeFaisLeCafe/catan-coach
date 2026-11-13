# 06 — Turn a league into a Corpus

**What to build:** `catan-coach arena corpus <dir> --out <corpus dir>` that replays league games
into a winner-labelled Corpus, every Seat sampled, with the league and Entrants in the manifest.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Reuses the replay path from `0a9ed6c`; replayed winners, Plies, and Turns match the store
- [ ] Game-level train/validation split as existing Corpora
- [ ] Manifest names league plan hash and Entrant specs
