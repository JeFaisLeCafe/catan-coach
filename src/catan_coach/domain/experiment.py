"""Strategy Experiment plans, schedules, and game results.

Games are scheduled before any engine runs. Result keys include every
play-affecting field. Pairing keys omit only the candidate's preferences, so
an Intervention can be matched without treating it as a different board.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Literal

PolicyKind = Literal["value", "model", "random"]
PreferenceCategory = Literal["settlement", "city", "road", "development_card", "port"]
BuildCategory = Literal["settlement", "city", "road", "development_card"]
MapPolicy = Literal["corpus"]
_PREFERENCE_ORDER: tuple[PreferenceCategory, ...] = (
    "settlement",
    "city",
    "road",
    "development_card",
    "port",
)
_SEATS = (0, 1, 2, 3)


def _hash(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError("a content hash must be 64 lowercase hex characters")
    return text


def _nonempty(value: str, label: str) -> str:
    if not value.strip():
        raise ValueError(f"{label} must not be empty")
    return value


def _count(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class PolicyPreference:
    category: PreferenceCategory
    delta: float

    def __post_init__(self) -> None:
        if self.category not in _PREFERENCE_ORDER:
            raise ValueError(f"unknown Policy Preference {self.category}")
        if isinstance(self.delta, bool) or not isinstance(self.delta, (int, float)):
            raise ValueError("a Policy Preference delta must be a finite number")
        if not math.isfinite(float(self.delta)) or not -1.0 <= float(self.delta) <= 1.0:
            raise ValueError("a Policy Preference delta must be finite and between -1 and 1")
        if float(self.delta) == 0.0:
            raise ValueError("a zero Policy Preference is omitted")
        object.__setattr__(self, "delta", float(self.delta))


def preferences(values: tuple[PolicyPreference, ...]) -> tuple[PolicyPreference, ...]:
    """One entry per category, in canonical order, with zeroes removed."""
    seen: dict[PreferenceCategory, PolicyPreference] = {}
    for value in values:
        if value.category in seen:
            raise ValueError(f"Policy Preference {value.category} is declared twice")
        seen[value.category] = value
    return tuple(seen[category] for category in _PREFERENCE_ORDER if category in seen)


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    name: str
    kind: PolicyKind
    search_simulations: int = 0
    explore: bool = False
    model_path: str | None = None
    sidecar_path: str | None = None
    declared_preferences: tuple[PolicyPreference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _nonempty(self.name, "Policy name"))
        object.__setattr__(self, "declared_preferences", preferences(self.declared_preferences))
        _check_policy(
            self.kind,
            self.search_simulations,
            self.explore,
            self.model_path,
            None,
            self.sidecar_path,
            None,
            self.declared_preferences,
            require_hash=False,
        )


@dataclass(frozen=True, slots=True)
class FrozenPolicySpec:
    name: str
    kind: PolicyKind
    search_simulations: int = 0
    explore: bool = False
    model_path: str | None = None
    model_hash: str | None = None
    sidecar_path: str | None = None
    sidecar_hash: str | None = None
    declared_preferences: tuple[PolicyPreference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _nonempty(self.name, "Policy name"))
        object.__setattr__(self, "model_hash", _hash(self.model_hash))
        object.__setattr__(self, "sidecar_hash", _hash(self.sidecar_hash))
        object.__setattr__(self, "declared_preferences", preferences(self.declared_preferences))
        _check_policy(
            self.kind,
            self.search_simulations,
            self.explore,
            self.model_path,
            self.model_hash,
            self.sidecar_path,
            self.sidecar_hash,
            self.declared_preferences,
            require_hash=True,
        )

    def without_preferences(self) -> FrozenPolicySpec:
        return FrozenPolicySpec(
            name=self.name,
            kind=self.kind,
            search_simulations=self.search_simulations,
            explore=self.explore,
            model_path=self.model_path,
            model_hash=self.model_hash,
            sidecar_path=self.sidecar_path,
            sidecar_hash=self.sidecar_hash,
        )


def _check_policy(
    kind: PolicyKind,
    search_simulations: int,
    explore: bool,
    model_path: str | None,
    model_hash: str | None,
    sidecar_path: str | None,
    sidecar_hash: str | None,
    declared: tuple[PolicyPreference, ...],
    *,
    require_hash: bool,
) -> None:
    if kind not in ("value", "model", "random"):
        raise ValueError(f"unknown Policy kind {kind}")
    if isinstance(search_simulations, bool) or not isinstance(search_simulations, int):
        raise ValueError("search simulations must be a non-negative integer")
    if search_simulations < 0:
        raise ValueError("search simulations must be a non-negative integer")
    if not isinstance(explore, bool):
        raise ValueError("explore must be true or false")
    if kind != "model" and declared:
        raise ValueError("only a model Policy can declare preferences")
    if declared and search_simulations > 0:
        raise ValueError("preferences require zero search simulations")
    if kind == "model":
        if model_path is None or not model_path.strip():
            raise ValueError("a model Policy needs a model path")
        if require_hash and model_hash is None:
            raise ValueError("a frozen model Policy needs a model hash")
    elif model_path is not None or model_hash is not None:
        raise ValueError("only a model Policy has a model path or hash")
    if require_hash and (sidecar_path is None) != (sidecar_hash is None):
        raise ValueError("a calibration sidecar path and hash must both be present or both absent")
    if not require_hash and sidecar_hash is not None and sidecar_path is None:
        raise ValueError("a calibration sidecar hash needs a path")
    if kind != "model" and (sidecar_path is not None or sidecar_hash is not None):
        raise ValueError("only a model Policy has a calibration sidecar")


@dataclass(frozen=True, slots=True)
class GameRules:
    vps_to_win: int = 10
    discard_limit: int = 7
    friendly_robber: bool = False
    turn_limit: int = 1000

    def __post_init__(self) -> None:
        if isinstance(self.vps_to_win, bool) or not isinstance(self.vps_to_win, int):
            raise ValueError("Victory Points must be an integer from 3 to 20")
        if not 3 <= self.vps_to_win <= 20:
            raise ValueError("Victory Points must be an integer from 3 to 20")
        if isinstance(self.discard_limit, bool) or not isinstance(self.discard_limit, int):
            raise ValueError("discard limit must be an integer from 5 to 20")
        if not 5 <= self.discard_limit <= 20:
            raise ValueError("discard limit must be an integer from 5 to 20")
        if not isinstance(self.friendly_robber, bool):
            raise ValueError("friendly robber must be true or false")
        if isinstance(self.turn_limit, bool) or not isinstance(self.turn_limit, int):
            raise ValueError("turn limit must be a positive integer")
        if self.turn_limit < 1:
            raise ValueError("turn limit must be a positive integer")


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    commit: str
    dirty: bool
    dirty_diff_hash: str | None = None

    def __post_init__(self) -> None:
        commit = _nonempty(self.commit, "source commit").lower()
        if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
            raise ValueError("source commit must be a 40-character hex SHA")
        object.__setattr__(self, "commit", commit)
        if not isinstance(self.dirty, bool):
            raise ValueError("dirty must be true or false")
        object.__setattr__(self, "dirty_diff_hash", _hash(self.dirty_diff_hash))
        if self.dirty and self.dirty_diff_hash is None:
            raise ValueError("a dirty source tree needs a diff hash")
        if not self.dirty and self.dirty_diff_hash is not None:
            raise ValueError("a clean source tree has no diff hash")


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    name: str
    candidate: PolicyConfig
    opponent: PolicyConfig
    games_per_candidate_seat: int
    base_seed: int
    map_policy: MapPolicy = "corpus"
    rules: GameRules = GameRules()
    player_count: int = 4

    def __post_init__(self) -> None:
        _check_plan_shape(
            self.name,
            self.player_count,
            self.games_per_candidate_seat,
            self.base_seed,
            self.map_policy,
        )


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    name: str
    candidate: FrozenPolicySpec
    opponent: FrozenPolicySpec
    games_per_candidate_seat: int
    base_seed: int
    source: SourceProvenance
    map_policy: MapPolicy = "corpus"
    rules: GameRules = GameRules()
    player_count: int = 4

    def __post_init__(self) -> None:
        _check_plan_shape(
            self.name,
            self.player_count,
            self.games_per_candidate_seat,
            self.base_seed,
            self.map_policy,
        )


def _check_plan_shape(
    name: str,
    player_count: int,
    games_per_candidate_seat: int,
    base_seed: int,
    map_policy: str,
) -> None:
    _nonempty(name, "experiment name")
    if player_count != 4:
        raise ValueError("version 1 plays exactly four Seats")
    if (
        isinstance(games_per_candidate_seat, bool)
        or not isinstance(games_per_candidate_seat, int)
        or games_per_candidate_seat < 1
    ):
        raise ValueError("games per candidate Seat must be at least 1")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0:
        raise ValueError("base seed must be a non-negative integer")
    if map_policy != "corpus":
        raise ValueError("version 1 uses the corpus map")


@dataclass(frozen=True, slots=True)
class ScheduledGame:
    result_key: str
    pairing_key: str
    seed: int
    candidate_seat: int
    policies: tuple[FrozenPolicySpec, ...]
    map_policy: MapPolicy
    rules: GameRules
    source: SourceProvenance


@dataclass(frozen=True, slots=True)
class BehaviorCounts:
    initial_resources: int
    initial_pips: int
    adjacent_port: bool
    settlements: int = 0
    cities: int = 0
    roads: int = 0
    development_cards: int = 0
    knights: int = 0
    offers: int = 0
    acceptances: int = 0
    completed_trades: int = 0
    maritime_trades: int = 0
    first_build: BuildCategory | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.initial_resources <= 5:
            raise ValueError("initial resources must count from 0 to 5 kinds")
        for label, value in (
            ("initial pips", self.initial_pips),
            ("settlements", self.settlements),
            ("cities", self.cities),
            ("roads", self.roads),
            ("development cards", self.development_cards),
            ("knights", self.knights),
            ("offers", self.offers),
            ("acceptances", self.acceptances),
            ("completed trades", self.completed_trades),
            ("maritime trades", self.maritime_trades),
        ):
            _count(value, label)
        if not isinstance(self.adjacent_port, bool):
            raise ValueError("adjacent port must be true or false")
        if self.first_build not in (None, "settlement", "city", "road", "development_card"):
            raise ValueError("unknown first build")


@dataclass(frozen=True, slots=True)
class BehaviorProfile:
    counts: BehaviorCounts
    public_victory_points: int
    actual_victory_points: int
    won: bool
    longest_road: bool = False
    largest_army: bool = False

    def __post_init__(self) -> None:
        _count(self.public_victory_points, "public Victory Points")
        _count(self.actual_victory_points, "actual Victory Points")
        if not isinstance(self.longest_road, bool) or not isinstance(self.largest_army, bool):
            raise ValueError("award ownership must be true or false")
        if not isinstance(self.won, bool):
            raise ValueError("won must be true or false")


@dataclass(frozen=True, slots=True)
class PartialBehaviorProfile:
    counts: BehaviorCounts
    public_victory_points: int
    actual_victory_points: int
    longest_road: bool = False
    largest_army: bool = False

    def __post_init__(self) -> None:
        _count(self.public_victory_points, "public Victory Points")
        _count(self.actual_victory_points, "actual Victory Points")
        if not isinstance(self.longest_road, bool) or not isinstance(self.largest_army, bool):
            raise ValueError("award ownership must be true or false")


@dataclass(frozen=True, slots=True)
class SeatResult:
    seat_index: int
    seat_name: str
    policy_name: str
    profile: BehaviorProfile

    def __post_init__(self) -> None:
        _seat(self.seat_index)
        _nonempty(self.seat_name, "Seat name")
        _nonempty(self.policy_name, "Policy name")


@dataclass(frozen=True, slots=True)
class PartialSeatResult:
    seat_index: int
    seat_name: str
    policy_name: str
    profile: PartialBehaviorProfile

    def __post_init__(self) -> None:
        _seat(self.seat_index)
        _nonempty(self.seat_name, "Seat name")
        _nonempty(self.policy_name, "Policy name")


@dataclass(frozen=True, slots=True)
class PlayIdentity:
    result_key: str
    pairing_key: str
    seed: int
    map_seed: int
    candidate_seat: int
    policies: tuple[FrozenPolicySpec, ...]
    map_policy: MapPolicy
    rules: GameRules
    source: SourceProvenance
    engine_version: str
    engine_sha: str
    plies: int
    turns: int

    def __post_init__(self) -> None:
        _nonempty(self.result_key, "result key")
        _nonempty(self.pairing_key, "pairing key")
        _nonempty(self.engine_version, "engine version")
        _nonempty(self.engine_sha, "engine source SHA")
        _seat(self.candidate_seat)
        if len(self.policies) != 4:
            raise ValueError("a game records exactly four Policies")
        if self.map_policy != "corpus":
            raise ValueError("version 1 uses the corpus map")
        if self.seed != self.map_seed:
            raise ValueError("the corpus map uses the game seed")
        _count(self.plies, "Plies")
        _count(self.turns, "turns")


@dataclass(frozen=True, slots=True)
class CompletedGame(PlayIdentity):
    winner: int
    seats: tuple[SeatResult, ...]

    def __post_init__(self) -> None:
        PlayIdentity.__post_init__(self)
        _seat(self.winner)
        _seat_rows(self.seats)
        winners = [seat.seat_index for seat in self.seats if seat.profile.won]
        if winners != [self.winner]:
            raise ValueError("exactly the winner's Behavior Profile is marked won")


@dataclass(frozen=True, slots=True)
class DroppedGame(PlayIdentity):
    reason: Literal["turn_limit"]
    seats: tuple[PartialSeatResult, ...]

    def __post_init__(self) -> None:
        PlayIdentity.__post_init__(self)
        if self.reason != "turn_limit":
            raise ValueError("a dropped game reached the turn limit")
        _seat_rows(self.seats)


@dataclass(frozen=True, slots=True)
class TechnicalFailure:
    result_key: str
    pairing_key: str
    attempt: Literal[1, 2]
    exception_type: str
    message: str

    def __post_init__(self) -> None:
        _nonempty(self.result_key, "result key")
        _nonempty(self.pairing_key, "pairing key")
        if self.attempt not in (1, 2):
            raise ValueError("a technical failure records attempt 1 or 2")
        _nonempty(self.exception_type, "exception type")
        _nonempty(self.message, "failure message")


def schedule(plan: ExperimentPlan) -> tuple[ScheduledGame, ...]:
    """Seat the candidate equally, with one shuffled permutation per four games."""
    scheduled: list[ScheduledGame] = []
    for block in range(plan.games_per_candidate_seat):
        for offset, candidate_seat in enumerate(_block_seats(plan.base_seed, block)):
            index = block * 4 + offset
            seed = plan.base_seed + index
            policies = tuple(
                plan.candidate if seat == candidate_seat else plan.opponent for seat in _SEATS
            )
            scheduled.append(
                ScheduledGame(
                    result_key=_key(seed, candidate_seat, policies, plan, preferences=True),
                    pairing_key=_key(seed, candidate_seat, policies, plan, preferences=False),
                    seed=seed,
                    candidate_seat=candidate_seat,
                    policies=policies,
                    map_policy=plan.map_policy,
                    rules=plan.rules,
                    source=plan.source,
                )
            )
    return tuple(scheduled)


def _block_seats(base_seed: int, block: int) -> tuple[int, ...]:
    order = [0, 1, 2, 3]
    random.Random(f"{base_seed}:{block}").shuffle(order)
    return tuple(order)


def _seat(index: int) -> None:
    if index not in _SEATS:
        raise ValueError("Seat index must be 0, 1, 2, or 3")


def _seat_rows(seats: tuple[SeatResult, ...] | tuple[PartialSeatResult, ...]) -> None:
    indexes = tuple(seat.seat_index for seat in seats)
    if indexes != _SEATS:
        raise ValueError("Seat results must be ordered indexes 0, 1, 2, and 3")


def _key(
    seed: int,
    candidate_seat: int,
    policies: tuple[FrozenPolicySpec, ...],
    plan: ExperimentPlan,
    *,
    preferences: bool,
) -> str:
    encoded = [
        _policy_identity(
            policy,
            include_preferences=preferences and index == candidate_seat,
        )
        for index, policy in enumerate(policies)
    ]
    payload = {
        "seed": seed,
        "candidate_seat": candidate_seat,
        "policies": encoded,
        "map_policy": plan.map_policy,
        "rules": {
            "vps_to_win": plan.rules.vps_to_win,
            "discard_limit": plan.rules.discard_limit,
            "friendly_robber": plan.rules.friendly_robber,
            "turn_limit": plan.rules.turn_limit,
        },
        "source": {
            "commit": plan.source.commit,
            "dirty": plan.source.dirty,
            "dirty_diff_hash": plan.source.dirty_diff_hash,
        },
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return digest


def _policy_identity(policy: FrozenPolicySpec, *, include_preferences: bool) -> dict[str, object]:
    selected = policy.declared_preferences if include_preferences else ()
    return {
        "kind": policy.kind,
        "model_hash": policy.model_hash,
        "sidecar_hash": policy.sidecar_hash,
        "search_simulations": policy.search_simulations,
        "explore": policy.explore,
        "preferences": [[item.category, round(item.delta, 10)] for item in selected],
    }
