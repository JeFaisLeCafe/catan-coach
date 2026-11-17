"""Run an Arena league on the Strategy Lab store, worker pool, and validity rules.

A league directory holds ``league.json`` (the frozen plan and source
provenance) beside the same ``games/`` and ``failures/`` folders a Strategy
Experiment writes. Each game file is named by its game id.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from catan_coach.domain.experiment import SourceProvenance
from catan_coach.domain.league import LeaguePlan, scheduled_games
from catan_coach.engine.experiment_store import GameStore, PlanMismatch
from catan_coach.engine.lab import DirtyWorktree, play_store, source_provenance

LEAGUE_SCHEMA = 1
LEAGUE_FILE = "league.json"


class LeagueStore(GameStore):
    def __init__(self, path: Path, plan: LeaguePlan, source: SourceProvenance) -> None:
        super().__init__(path, scheduled_games(plan, source))
        self.plan = plan
        self.source = source

    @classmethod
    def open(cls, path: Path, plan: LeaguePlan, source: SourceProvenance) -> LeagueStore:
        cls._freeze(path, LEAGUE_FILE, _league_document(plan, source))
        return cls(path, plan, source)

    @classmethod
    def load(cls, path: Path) -> LeagueStore:
        document = json.loads((path / LEAGUE_FILE).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema") != LEAGUE_SCHEMA:
            raise ValueError("unsupported league schema")
        source = document["source"]
        if not isinstance(source, dict):
            raise ValueError("league source must be an object")
        provenance = SourceProvenance(
            commit=str(source["commit"]),
            dirty=bool(source["dirty"]),
            dirty_diff_hash=source.get("dirty_diff_hash"),
        )
        return cls(path, LeaguePlan.from_json(document["league"]), provenance)


def load_league(path: Path) -> LeaguePlan:
    """Read a league plan, resolving model paths and pinning their hashes.

    Paths are relative to the plan file. A declared hash must match the file;
    an absent one is computed, so a plan can be written before hashing.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("league plan must be an object")
    entrants = document.get("entrants")
    if isinstance(entrants, list):
        document["entrants"] = [_pinned(item, path.parent) for item in entrants]
    return LeaguePlan.from_json(document)


def run_league(plan_path: Path, out: Path, *, workers: int, allow_dirty: bool) -> int:
    if workers < 1:
        raise ValueError("workers must be at least 1")
    plan = load_league(plan_path)
    store = LeagueStore.open(out, plan, source_provenance(allow_dirty))
    return play_store(store, workers=workers, out=out)


def _pinned(entrant: object, root: Path) -> object:
    if not isinstance(entrant, dict):
        return entrant
    pinned = dict(entrant)
    for path_key, hash_key in (("model_path", "model_hash"), ("sidecar_path", "sidecar_hash")):
        value = pinned.get(path_key)
        if not isinstance(value, str):
            continue
        file = Path(value)
        if not file.is_absolute():
            file = root / file
        file = file.resolve()
        if not file.is_file():
            raise ValueError(f"missing {path_key.replace('_', ' ')} {file}")
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        declared = pinned.get(hash_key)
        if declared is not None and declared != digest:
            raise ValueError(
                f"{hash_key.replace('_', ' ')} for {pinned.get('name')} does not match {file}"
            )
        pinned[path_key] = str(file)
        pinned[hash_key] = digest
    return pinned


def _league_document(plan: LeaguePlan, source: SourceProvenance) -> dict[str, object]:
    return {
        "schema": LEAGUE_SCHEMA,
        "league": plan.to_json(),
        "source": {
            "commit": source.commit,
            "dirty": source.dirty,
            "dirty_diff_hash": source.dirty_diff_hash,
        },
    }


__all__ = [
    "DirtyWorktree",
    "LeagueStore",
    "PlanMismatch",
    "load_league",
    "run_league",
]
