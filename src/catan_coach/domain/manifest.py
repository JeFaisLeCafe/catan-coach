"""Who played a Corpus, and how many games the turn limit dropped.

The parquet rows do not record the player. This manifest does. Training and
calibration refuse a missing manifest, and they refuse a drop rate above 1%.

A `mixed` Corpus is one candidate Seat against an opponent Policy in the
other Seats, replayed from a stored Strategy Experiment. It is not self-play,
and a manifest cannot describe it as self-play: model self-play always
explores, so a `model` manifest with exploration off is refused.
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

_SHA256_HEX = frozenset("0123456789abcdef")


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

    def __post_init__(self) -> None:
        if self.player_kind not in _PLAYER_KINDS:
            raise ValueError("player_kind must be 'value', 'model', or 'mixed'")
        if self.player_kind == "value" and self.model_sha256 != "":
            raise ValueError("a value-function Corpus has no model hash")
        if self.player_kind != "value" and not _is_sha256(self.model_sha256):
            raise ValueError("a model Corpus needs a sha256 of the model file")
        if self.player_kind == "mixed":
            if self.opponent == "":
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
        expected = set(_MIXED_FIELDS if payload.get("player_kind") == "mixed" else _FIELDS)
        found = set(payload)
        if found != expected:
            missing = ", ".join(sorted(expected - found))
            unknown = ", ".join(sorted(found - expected))
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
