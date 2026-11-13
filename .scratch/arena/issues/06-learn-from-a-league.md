# 06 — Turn a league into a Corpus

**What to build:** `catan-coach arena corpus <dir> --out <corpus dir>` that replays league games
into a winner-labelled Corpus, every Seat sampled, with the league and Entrants in the manifest.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Builds on the replay path from `0a9ed6c` but keys games and files by unique game id, not
      seed: the four rotations of a block share a seed and must all survive
- [ ] Rebinds every model Entrant (any Seat may be a model), not one candidate
- [ ] Replayed winners, Plies, and Turns match the store
- [ ] Train/validation split by block, so rotations of one board never straddle the split
- [ ] Arena manifest: league plan hash and every Entrant spec with model hashes
- [ ] Test: a block of four same-seed rotations yields four distinct replayed games
