"""Who played a Corpus, and how many games the turn limit dropped.

The parquet rows do not record the player. This manifest does. Training and
calibration refuse a missing manifest, and they refuse a drop rate above 1%.

A `mixed` Corpus is either one candidate Seat against an opponent Policy,
replayed from a stored Strategy Experiment, or an Arena league. A league
records its plan hash and every Entrant. It is not self-play, and a manifest
cannot describe a mixed table as self-play: model self-play always explores,
so a `model` manifest with exploration off is refused.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from typing import Literal

PlayerKind = Literal["value", "model", "mixed"]

_PLAYER_KINDS = ("value", "model", "mixed")

MANIFEST_NAME = "manifest.json"

# A higher drop rate is a biased finish set and cannot support a strength claim.
MAX_TRAINING_DROP_RATE = 0.01

_FIELDS = (
    "player_kind",
    "model_sha256",
    "search_simulations",
    "exploration",
    "ply_stride",
    "base_seed",
    "requested_games",
    "validation_fraction",
    "max_turns",
    "git_revision",
    "dirty_tree",
    "games_finished",
    "games_dropped",
    "drop_rate",
)
# Only a mixed table names an opponent. Self-play manifests keep their shape.
_MIXED_FIELDS = (*_FIELDS, "opponent")
# A league Corpus adds these. Older manifests omit them.
_LEAGUE_FIELDS = ("league_name", "league_plan_sha256", "entrants")
_ENTRANT_FIELDS = {
    "name",
    "kind",
    "search_simulations",
    "explore",
    "model_hash",
    "sidecar_hash",
    "depth",
    "preferences",
}
_PREFERENCE_FIELDS = {"category", "delta"}
_ENTRANT_KINDS = frozenset({"value", "model", "random", "alphabeta"})
_PREFERENCE_CATEGORIES = frozenset({"settlement", "city", "road", "development_card", "port"})

_SHA256_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class CorpusEntrant:
    """One frozen Entrant recorded on a league Corpus, without its file paths."""

    name: str
    kind: str
    search_simulations: int = 0
    explore: bool = False
    model_hash: str = ""
    sidecar_hash: str = ""
    depth: int | None = None
    preferences: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Entrant name must not be empty")
        if self.kind not in _ENTRANT_KINDS:
            raise ValueError(f"unknown Entrant kind {self.kind}")
        if self.model_hash != "" and not _is_sha256(self.model_hash):
            raise ValueError("an Entrant model hash must be a sha256")
        if self.sidecar_hash != "" and not _is_sha256(self.sidecar_hash):
            raise ValueError("an Entrant sidecar hash must be a sha256")
        if self.kind == "model":
            if not _is_sha256(self.model_hash):
                raise ValueError("a model Entrant needs a model hash")
        elif self.model_hash != "" or self.sidecar_hash != "":
            raise ValueError("only a model Entrant has a model or sidecar hash")
        if isinstance(self.search_simulations, bool) or not isinstance(
            self.search_simulations, int
        ):
            raise ValueError("search_simulations must be a non-negative integer")
        if self.search_simulations < 0:
            raise ValueError("search_simulations must be a non-negative integer")
        if not isinstance(self.explore, bool):
            raise ValueError("explore must be true or false")
        if self.kind == "alphabeta":
            if isinstance(self.depth, bool) or not isinstance(self.depth, int) or self.depth < 1:
                raise ValueError("alphabeta depth must be an integer of at least 1")
        elif self.depth is not None:
            raise ValueError("only an alphabeta Entrant has a depth")
        object.__setattr__(self, "preferences", _validated_preferences(self.preferences))

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "search_simulations": self.search_simulations,
            "explore": self.explore,
            "model_hash": self.model_hash,
            "sidecar_hash": self.sidecar_hash,
            "depth": self.depth,
            "preferences": [
                {"category": category, "delta": delta} for category, delta in self.preferences
            ],
        }


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    """Provenance of one Corpus directory, plus the outcome counts."""

    player_kind: PlayerKind
    model_sha256: str
    search_simulations: int
    exploration: bool
    ply_stride: int
    base_seed: int
    requested_games: int
    validation_fraction: float
    max_turns: int
    git_revision: str
    dirty_tree: bool
    games_finished: int
    games_dropped: int
    drop_rate: float
    opponent: str = ""
    league_name: str = ""
    league_plan_sha256: str = ""
    entrants: tuple[CorpusEntrant, ...] = ()

    def __post_init__(self) -> None:
        if self.player_kind not in _PLAYER_KINDS:
            raise ValueError("player_kind must be 'value', 'model', or 'mixed'")
        league = bool(self.league_name or self.league_plan_sha256 or self.entrants)
        if league:
            if self.player_kind != "mixed":
                raise ValueError("a league Corpus is a mixed table")
            if (
                not self.league_name.strip()
                or not _is_sha256(self.league_plan_sha256)
                or not self.entrants
            ):
                raise ValueError(
                    "a league Corpus names the league, its plan hash, and its Entrants"
                )
            names = [entrant.name for entrant in self.entrants]
            if len(names) != len(set(names)):
                raise ValueError("Entrant names must be unique")
            if self.model_sha256 != "" and not _is_sha256(self.model_sha256):
                raise ValueError("a league model hash must be empty or a sha256")
        elif self.player_kind == "value" and self.model_sha256 != "":
            raise ValueError("a value-function Corpus has no model hash")
        elif self.player_kind != "value" and not _is_sha256(self.model_sha256):
            raise ValueError("a model Corpus needs a sha256 of the model file")
        if self.player_kind == "mixed":
            if self.opponent == "" and not league:
                raise ValueError("a mixed table must name its opponent")
        elif self.opponent != "":
            raise ValueError("a self-play Corpus has no opponent")
        if self.player_kind == "model" and not self.exploration:
            raise ValueError(
                "model self-play explores; a table with exploration off is not self-play"
            )
        if self.search_simulations < 0:
            raise ValueError("search_simulations must be non-negative")
        if self.ply_stride < 1:
            raise ValueError("ply_stride must be at least 1")
        if self.requested_games < 1:
            raise ValueError("requested_games must be at least 1")
        if not 0.0 < self.validation_fraction < 1.0:
            raise ValueError("validation_fraction must be between 0 and 1, exclusive")
        if self.max_turns < 0:
            raise ValueError("max_turns must be non-negative")
        if self.git_revision == "":
            raise ValueError("git_revision must be a revision or 'unknown'")
        if self.games_finished < 0 or self.games_dropped < 0:
            raise ValueError("outcome counts must be non-negative")
        expected = _ratio(self.games_finished, self.games_dropped)
        if not math.isclose(self.drop_rate, expected, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("drop rate does not match games finished and games dropped")

    def with_outcomes(self, games_finished: int, games_dropped: int) -> CorpusManifest:
        return replace(
            self,
            games_finished=games_finished,
            games_dropped=games_dropped,
            drop_rate=_ratio(games_finished, games_dropped),
        )

    def resume_conflicts(self, invocation: CorpusManifest) -> tuple[str, ...]:
        """Fields that stop `invocation` from continuing this run.

        Outcome counts are filled in after the games, so they are not part of
        the invocation. A later call may ask for more games; it may not ask
        for fewer. The git revision and dirty-tree flag are recorded, and a
        later commit does not make the same command a different run.
        """
        conflicts: list[str] = []
        if self.player_kind != invocation.player_kind:
            conflicts.append("player_kind")
        if self.opponent != invocation.opponent:
            conflicts.append("opponent")
        if self.league_name != invocation.league_name:
            conflicts.append("league_name")
        if self.league_plan_sha256 != invocation.league_plan_sha256:
            conflicts.append("league_plan_sha256")
        if self.entrants != invocation.entrants:
            conflicts.append("entrants")
        if self.model_sha256 != invocation.model_sha256:
            conflicts.append("model_sha256")
        if self.search_simulations != invocation.search_simulations:
            conflicts.append("search_simulations")
        if self.exploration != invocation.exploration:
            conflicts.append("exploration")
        if self.ply_stride != invocation.ply_stride:
            conflicts.append("ply_stride")
        if self.base_seed != invocation.base_seed:
            conflicts.append("base_seed")
        if invocation.requested_games < self.requested_games:
            conflicts.append("requested_games")
        if not math.isclose(
            self.validation_fraction,
            invocation.validation_fraction,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            conflicts.append("validation_fraction")
        if self.max_turns != invocation.max_turns:
            conflicts.append("max_turns")
        return tuple(conflicts)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "player_kind": self.player_kind,
            "model_sha256": self.model_sha256,
            "search_simulations": self.search_simulations,
            "exploration": self.exploration,
            "ply_stride": self.ply_stride,
            "base_seed": self.base_seed,
            "requested_games": self.requested_games,
            "validation_fraction": self.validation_fraction,
            "max_turns": self.max_turns,
            "git_revision": self.git_revision,
            "dirty_tree": self.dirty_tree,
            "games_finished": self.games_finished,
            "games_dropped": self.games_dropped,
            "drop_rate": self.drop_rate,
        }
        if self.player_kind == "mixed":
            payload["opponent"] = self.opponent
        if self.league_name or self.league_plan_sha256 or self.entrants:
            payload["league_name"] = self.league_name
            payload["league_plan_sha256"] = self.league_plan_sha256
            payload["entrants"] = [entrant.to_dict() for entrant in self.entrants]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, allow_nan=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> CorpusManifest:
        parsed: object = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Corpus manifest must be a JSON object")
        payload: dict[str, object] = {}
        for key, value in parsed.items():
            if not isinstance(key, str):
                raise ValueError("Corpus manifest keys must be strings")
            payload[key] = value
        required = set(_MIXED_FIELDS if payload.get("player_kind") == "mixed" else _FIELDS)
        found = set(payload)
        league_found = set(_LEAGUE_FIELDS) & found
        if league_found and league_found != set(_LEAGUE_FIELDS):
            raise ValueError("a league Corpus records its name, plan hash, and Entrants")
        missing_keys = required - found
        unknown_keys = found - required - set(_LEAGUE_FIELDS)
        if missing_keys or unknown_keys:
            missing = ", ".join(sorted(missing_keys))
            unknown = ", ".join(sorted(unknown_keys))
            raise ValueError(
                f"Corpus manifest fields do not match (missing: {missing}; unknown: {unknown})"
            )
        kind = _string(payload, "player_kind")
        if kind == "value":
            player_kind: PlayerKind = "value"
        elif kind == "model":
            player_kind = "model"
        elif kind == "mixed":
            player_kind = "mixed"
        else:
            raise ValueError("player_kind must be 'value', 'model', or 'mixed'")
        return cls(
            player_kind=player_kind,
            model_sha256=_string(payload, "model_sha256"),
            search_simulations=_integer(payload, "search_simulations"),
            exploration=_boolean(payload, "exploration"),
            ply_stride=_integer(payload, "ply_stride"),
            base_seed=_integer(payload, "base_seed"),
            requested_games=_integer(payload, "requested_games"),
            validation_fraction=_number(payload, "validation_fraction"),
            max_turns=_integer(payload, "max_turns"),
            git_revision=_string(payload, "git_revision"),
            dirty_tree=_boolean(payload, "dirty_tree"),
            games_finished=_integer(payload, "games_finished"),
            games_dropped=_integer(payload, "games_dropped"),
            drop_rate=_number(payload, "drop_rate"),
            opponent=_string(payload, "opponent") if player_kind == "mixed" else "",
            league_name=_string(payload, "league_name") if "league_name" in payload else "",
            league_plan_sha256=(
                _string(payload, "league_plan_sha256") if "league_plan_sha256" in payload else ""
            ),
            entrants=_entrants(payload["entrants"]) if "entrants" in payload else (),
        )


def accepts_training(manifest: CorpusManifest) -> bool:
    """True when the recorded drop rate can support a strength claim."""
    return manifest.drop_rate <= MAX_TRAINING_DROP_RATE


def training_refusal(manifest: CorpusManifest | None) -> str | None:
    """Why this Corpus cannot train or calibrate. None when it can."""
    if manifest is None:
        return "Corpus manifest is missing"
    if not accepts_training(manifest):
        return f"Corpus drop rate {manifest.drop_rate:.1%} is above 1%"
    return None


def _ratio(games_finished: int, games_dropped: int) -> float:
    total = games_finished + games_dropped
    if total <= 0:
        return 0.0
    return games_dropped / total


def _validated_preferences(
    preferences: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    normalized: list[tuple[str, float]] = []
    seen: set[str] = set()
    for category, delta in preferences:
        if category not in _PREFERENCE_CATEGORIES:
            raise ValueError(f"unknown Policy Preference {category}")
        if category in seen:
            raise ValueError(f"Policy Preference {category} is declared twice")
        seen.add(category)
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise ValueError("a Policy Preference delta must be a finite number")
        if not math.isfinite(float(delta)):
            raise ValueError("a Policy Preference delta must be a finite number")
        normalized.append((category, float(delta)))
    return tuple(normalized)


def _entrants(value: object) -> tuple[CorpusEntrant, ...]:
    if not isinstance(value, list):
        raise ValueError("Corpus manifest field entrants must be a list")
    return tuple(_entrant(item) for item in value)


def _entrant(value: object) -> CorpusEntrant:
    document = _object(value, "Entrant")
    if set(document) != _ENTRANT_FIELDS:
        missing = ", ".join(sorted(_ENTRANT_FIELDS - set(document)))
        unknown = ", ".join(sorted(set(document) - _ENTRANT_FIELDS))
        raise ValueError(f"Entrant fields do not match (missing: {missing}; unknown: {unknown})")
    return CorpusEntrant(
        name=_string(document, "name"),
        kind=_string(document, "kind"),
        search_simulations=_integer(document, "search_simulations"),
        explore=_boolean(document, "explore"),
        model_hash=_string(document, "model_hash"),
        sidecar_hash=_string(document, "sidecar_hash"),
        depth=_optional_integer(document["depth"], "depth"),
        preferences=_preference_list(document["preferences"]),
    )


def _preference_list(value: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, list):
        raise ValueError("Entrant preferences must be a list")
    items: list[tuple[str, float]] = []
    for item in value:
        document = _object(item, "preference")
        if set(document) != _PREFERENCE_FIELDS:
            raise ValueError("preference fields must be category and delta")
        category = document["category"]
        if not isinstance(category, str):
            raise ValueError("preference category must be a string")
        delta = document["delta"]
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise ValueError("a Policy Preference delta must be a finite number")
        items.append((category, float(delta)))
    return tuple(items)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    parsed: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} keys must be strings")
        parsed[key] = item
    return parsed


def _optional_integer(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Entrant {label} must be an integer or null")
    return value


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in _SHA256_HEX for char in value)


def _string(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"Corpus manifest field {key} must be a string")
    return value


def _boolean(payload: dict[str, object], key: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"Corpus manifest field {key} must be a boolean")
    return value


def _integer(payload: dict[str, object], key: str) -> int:
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Corpus manifest field {key} must be an integer")
    return value


def _number(payload: dict[str, object], key: str) -> float:
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Corpus manifest field {key} must be a number")
    return float(value)
