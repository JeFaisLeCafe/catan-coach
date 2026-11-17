"""League plans and the balanced schedule of four-Entrant tables.

One cycle plays every combination of four Entrants once, in plan order.
That combination is a block of four games: the cyclic Seat rotations of the
combination, all on one board seed. Rotation ``r`` is the combination shifted
``r`` places toward the last Seat. The next block, across cycles, takes the
next seed. A game id names the cycle, block, and rotation. Games in a block
share a seed, so the seed is not an id.

An Entrant is a frozen Policy, the same spec a Strategy Experiment seats as
its candidate or opponent. The league name is not part of a pairing key.
Preferences are, because they belong to the Entrant.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations

from catan_coach.domain.experiment import (
    FrozenPolicySpec,
    GameRules,
    MapPolicy,
    PolicyKind,
    PolicyPreference,
    PreferenceCategory,
    ScheduledGame,
    SourceProvenance,
)

Entrant = FrozenPolicySpec

_PLAN_FIELDS = {"name", "entrants", "cycles", "base_seed", "rules", "map_policy"}
_ENTRANT_FIELDS = {
    "name",
    "kind",
    "search_simulations",
    "explore",
    "model_path",
    "model_hash",
    "sidecar_path",
    "sidecar_hash",
    "declared_preferences",
    "depth",
}
_RULE_FIELDS = {"vps_to_win", "discard_limit", "friendly_robber", "turn_limit"}
_PREFERENCE_FIELDS = {"category", "delta"}
_SEATS = 4


@dataclass(frozen=True, slots=True)
class LeaguePlan:
    name: str
    entrants: tuple[Entrant, ...]
    cycles: int
    base_seed: int
    rules: GameRules = field(default_factory=GameRules)
    map_policy: MapPolicy = "corpus"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("league name must not be empty")
        object.__setattr__(self, "entrants", _validated_entrants(self.entrants))
        if isinstance(self.cycles, bool) or not isinstance(self.cycles, int) or self.cycles < 1:
            raise ValueError("cycles must be at least 1")
        if (
            isinstance(self.base_seed, bool)
            or not isinstance(self.base_seed, int)
            or self.base_seed < 0
        ):
            raise ValueError("base seed must be a non-negative integer")
        if self.map_policy != "corpus":
            raise ValueError("version 1 uses the corpus map")
        if not isinstance(self.rules, GameRules):
            raise ValueError("rules must be game rules")

    def to_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "entrants": [_entrant_json(entrant) for entrant in self.entrants],
            "cycles": self.cycles,
            "base_seed": self.base_seed,
            "map_policy": self.map_policy,
            "rules": {
                "vps_to_win": self.rules.vps_to_win,
                "discard_limit": self.rules.discard_limit,
                "friendly_robber": self.rules.friendly_robber,
                "turn_limit": self.rules.turn_limit,
            },
        }

    @classmethod
    def from_json(cls, payload: object) -> LeaguePlan:
        document = _mapping(payload, "league plan")
        _reject_unknown(document, _PLAN_FIELDS, "league plan")
        for key in ("name", "entrants", "cycles", "base_seed"):
            if key not in document:
                raise ValueError(f"league plan requires {key}")
        name = document["name"]
        if not isinstance(name, str):
            raise ValueError("league name must be text")
        raw_entrants = document["entrants"]
        if not isinstance(raw_entrants, list):
            raise ValueError("entrants must be a list")
        return cls(
            name=name,
            entrants=tuple(_entrant(item) for item in raw_entrants),
            cycles=_int(document["cycles"], "cycles"),
            base_seed=_int(document["base_seed"], "base seed"),
            map_policy=_map_policy(document.get("map_policy", "corpus")),
            rules=_rules(document.get("rules", {})),
        )


@dataclass(frozen=True, slots=True)
class LeagueGame:
    game_id: str
    pairing_key: str
    seed: int
    cycle: int
    block: int
    rotation: int
    entrants: tuple[Entrant, ...]
    map_policy: MapPolicy
    rules: GameRules

    def __post_init__(self) -> None:
        cycle = _index(self.cycle, "cycle")
        block = _index(self.block, "block")
        if isinstance(self.rotation, bool) or not isinstance(self.rotation, int):
            raise ValueError("rotation must be an integer")
        if not 0 <= self.rotation < _SEATS:
            raise ValueError("rotation must be 0, 1, 2, or 3")
        game_id = f"c{cycle}-b{block}-r{self.rotation}"
        if self.game_id != game_id:
            raise ValueError("game id must name the cycle, block, and rotation")
        if not isinstance(self.pairing_key, str) or not self.pairing_key.strip():
            raise ValueError("pairing key must not be empty")
        seated = _parsed_entrants(self.entrants)
        if len(seated) != _SEATS:
            raise ValueError("a league game seats four Entrants")
        object.__setattr__(self, "entrants", seated)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if self.map_policy != "corpus":
            raise ValueError("version 1 uses the corpus map")
        if not isinstance(self.rules, GameRules):
            raise ValueError("rules must be game rules")


def schedule(plan: LeaguePlan) -> tuple[LeagueGame, ...]:
    """Play every four-Entrant combination, once per cycle, in plan order."""
    tables = tuple(combinations(plan.entrants, 4))
    games: list[LeagueGame] = []
    for cycle in range(plan.cycles):
        for block, table in enumerate(tables):
            seed = plan.base_seed + cycle * len(tables) + block
            for rotation in range(_SEATS):
                seated = table[rotation:] + table[:rotation]
                games.append(
                    LeagueGame(
                        game_id=f"c{cycle}-b{block}-r{rotation}",
                        pairing_key=_pairing_key(seated, seed, plan),
                        seed=seed,
                        cycle=cycle,
                        block=block,
                        rotation=rotation,
                        entrants=seated,
                        map_policy=plan.map_policy,
                        rules=plan.rules,
                    )
                )
    return tuple(games)


def scheduled_games(plan: LeaguePlan, source: SourceProvenance) -> tuple[ScheduledGame, ...]:
    """The league schedule as Strategy Lab games, so its store and runner play them.

    The game id is the result key: rotations of a block share a seed, so a
    seed-derived key would collide. A league has no candidate; Seat 0 stands in.
    """
    return tuple(
        ScheduledGame(
            result_key=game.game_id,
            pairing_key=game.pairing_key,
            seed=game.seed,
            candidate_seat=0,
            policies=game.entrants,
            map_policy=game.map_policy,
            rules=game.rules,
            source=source,
        )
        for game in schedule(plan)
    )


def _validated_entrants(value: object) -> tuple[Entrant, ...]:
    entrants = _parsed_entrants(value)
    if not 4 <= len(entrants) <= 12:
        raise ValueError("a league has between 4 and 12 Entrants")
    return entrants


def _parsed_entrants(value: object) -> tuple[Entrant, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("Entrants must be a sequence")
    entrants: list[Entrant] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, FrozenPolicySpec):
            raise ValueError("an Entrant is a frozen Policy")
        if item.name in seen:
            raise ValueError(f"duplicate Entrant name {item.name}")
        seen.add(item.name)
        entrants.append(item)
    return tuple(entrants)


def _pairing_key(seated: tuple[Entrant, ...], seed: int, plan: LeaguePlan) -> str:
    payload = {
        "seed": seed,
        "seats": [_pairing_identity(entrant) for entrant in seated],
        "map_policy": plan.map_policy,
        "rules": {
            "vps_to_win": plan.rules.vps_to_win,
            "discard_limit": plan.rules.discard_limit,
            "friendly_robber": plan.rules.friendly_robber,
            "turn_limit": plan.rules.turn_limit,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _pairing_identity(entrant: Entrant) -> dict[str, object]:
    return {
        "name": entrant.name,
        "kind": entrant.kind,
        "model_hash": entrant.model_hash,
        "sidecar_hash": entrant.sidecar_hash,
        "search_simulations": entrant.search_simulations,
        "explore": entrant.explore,
        "depth": entrant.depth,
        "preferences": [
            [item.category, round(item.delta, 10)] for item in entrant.declared_preferences
        ],
    }


def _entrant_json(entrant: Entrant) -> dict[str, object]:
    document: dict[str, object] = {
        "name": entrant.name,
        "kind": entrant.kind,
        "search_simulations": entrant.search_simulations,
        "explore": entrant.explore,
        "model_path": entrant.model_path,
        "model_hash": entrant.model_hash,
        "sidecar_path": entrant.sidecar_path,
        "sidecar_hash": entrant.sidecar_hash,
        "declared_preferences": [
            {"category": item.category, "delta": item.delta}
            for item in entrant.declared_preferences
        ],
    }
    if entrant.depth is not None:
        document["depth"] = entrant.depth
    return document


def _entrant(payload: object) -> Entrant:
    document = _mapping(payload, "Entrant")
    _reject_unknown(document, _ENTRANT_FIELDS, "Entrant")
    for key in ("name", "kind"):
        if key not in document:
            raise ValueError(f"Entrant requires {key}")
    name = document["name"]
    if not isinstance(name, str):
        raise ValueError("Entrant name must be text")
    raw_preferences = document.get("declared_preferences", [])
    if not isinstance(raw_preferences, list):
        raise ValueError("declared preferences must be a list")
    return FrozenPolicySpec(
        name=name,
        kind=_policy_kind(document["kind"]),
        search_simulations=_int(document.get("search_simulations", 0), "search simulations"),
        explore=_flag(document.get("explore", False), "explore"),
        model_path=_optional_text(document.get("model_path"), "model path"),
        model_hash=_optional_text(document.get("model_hash"), "model hash"),
        sidecar_path=_optional_text(document.get("sidecar_path"), "sidecar path"),
        sidecar_hash=_optional_text(document.get("sidecar_hash"), "sidecar hash"),
        declared_preferences=tuple(_preference(item) for item in raw_preferences),
        depth=None if document.get("depth") is None else _int(document["depth"], "depth"),
    )


def _preference(payload: object) -> PolicyPreference:
    document = _mapping(payload, "preference")
    _reject_unknown(document, _PREFERENCE_FIELDS, "preference")
    for key in ("category", "delta"):
        if key not in document:
            raise ValueError(f"preference requires {key}")
    return PolicyPreference(_category(document["category"]), _number(document["delta"], "delta"))


def _rules(payload: object) -> GameRules:
    document = _mapping(payload, "rules")
    _reject_unknown(document, _RULE_FIELDS, "rules")
    return GameRules(
        vps_to_win=_int(document.get("vps_to_win", 10), "Victory Points"),
        discard_limit=_int(document.get("discard_limit", 7), "discard limit"),
        friendly_robber=_flag(document.get("friendly_robber", False), "friendly robber"),
        turn_limit=_int(document.get("turn_limit", 1000), "turn limit"),
    )


def _index(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    extra = sorted(set(payload) - allowed)
    if extra:
        raise ValueError(f"unknown {label} field {extra[0]}")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    return float(value)


def _flag(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true or false")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    return value


def _map_policy(value: object) -> MapPolicy:
    if value == "corpus":
        return "corpus"
    raise ValueError("version 1 uses the corpus map")


def _policy_kind(value: object) -> PolicyKind:
    if value == "value":
        return "value"
    if value == "model":
        return "model"
    if value == "random":
        return "random"
    if value == "alphabeta":
        return "alphabeta"
    raise ValueError(f"unknown Policy kind {value}")


def _category(value: object) -> PreferenceCategory:
    if value == "settlement":
        return "settlement"
    if value == "city":
        return "city"
    if value == "road":
        return "road"
    if value == "development_card":
        return "development_card"
    if value == "port":
        return "port"
    raise ValueError(f"unknown Policy Preference {value}")
