"""Freeze an Experiment Plan and store one result per scheduled game."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Literal, TypedDict

from catan_coach.domain.experiment import (
    BehaviorCounts,
    BehaviorProfile,
    BuildCategory,
    CompletedGame,
    DroppedGame,
    ExperimentConfig,
    ExperimentPlan,
    FrozenPolicySpec,
    GameRules,
    PartialBehaviorProfile,
    PartialSeatResult,
    PolicyConfig,
    PolicyKind,
    PolicyPreference,
    PreferenceCategory,
    ScheduledGame,
    SeatResult,
    SourceProvenance,
    TechnicalFailure,
    schedule,
)

PLAN_SCHEMA = 1
RESULT_SCHEMA = 1
FAILURE_SCHEMA = 1


class _Identity(TypedDict):
    result_key: str
    pairing_key: str
    seed: int
    map_seed: int
    candidate_seat: int
    policies: tuple[FrozenPolicySpec, ...]
    map_policy: Literal["corpus"]
    rules: GameRules
    source: SourceProvenance
    engine_version: str
    engine_sha: str
    plies: int
    turns: int


class PlanMismatch(ValueError):
    """The directory already holds a different frozen plan."""


def load_plan(path: Path) -> ExperimentPlan:
    document = json.loads((path / "plan.json").read_text(encoding="utf-8"))
    if document.get("schema") != PLAN_SCHEMA:
        raise ValueError("unsupported plan schema")
    return ExperimentPlan(
        name=str(document["name"]),
        candidate=_policy(document["candidate"]),
        opponent=_policy(document["opponent"]),
        games_per_candidate_seat=int(document["games_per_candidate_seat"]),
        base_seed=int(document["base_seed"]),
        source=_source(document["source"]),
        map_policy=document["map_policy"],
        rules=_rules(document["rules"]),
        player_count=int(document["player_count"]),
    )


def freeze_config(config: ExperimentConfig, source: SourceProvenance) -> ExperimentPlan:
    return ExperimentPlan(
        name=config.name,
        candidate=_freeze_policy(config.candidate),
        opponent=_freeze_policy(config.opponent),
        games_per_candidate_seat=config.games_per_candidate_seat,
        base_seed=config.base_seed,
        source=source,
        map_policy=config.map_policy,
        rules=config.rules,
        player_count=config.player_count,
    )


class ExperimentStore:
    def __init__(self, path: Path, plan: ExperimentPlan) -> None:
        self.path = path
        self.plan = plan

    @classmethod
    def open(cls, path: Path, plan: ExperimentPlan) -> ExperimentStore:
        path.mkdir(parents=True, exist_ok=True)
        (path / "games").mkdir(exist_ok=True)
        (path / "failures").mkdir(exist_ok=True)
        plan_path = path / "plan.json"
        document = _plan_document(plan)
        if plan_path.exists():
            stored = json.loads(plan_path.read_text(encoding="utf-8"))
            mismatch = _first_mismatch(stored, document)
            if mismatch is not None:
                raise PlanMismatch(f"frozen plan differs at {mismatch}")
        else:
            _write_json(plan_path, document)
        return cls(path, plan)

    def pending(self, games: Sequence[ScheduledGame] | None = None) -> tuple[ScheduledGame, ...]:
        scheduled = tuple(games) if games is not None else schedule(self.plan)
        done = {game.result_key for game in self.read_outcomes()}
        terminal = {failure.result_key for failure in self.read_failures() if failure.attempt == 2}
        return tuple(
            game
            for game in scheduled
            if game.result_key not in done and game.result_key not in terminal
        )

    def write_result(self, result: CompletedGame | DroppedGame) -> None:
        if result.result_key not in {game.result_key for game in schedule(self.plan)}:
            raise ValueError(f"result {result.result_key} is not in this plan")
        destination = self.path / "games" / f"{result.result_key}.json"
        _write_json(destination, _result_document(result))

    def write_failure(self, failure: TechnicalFailure) -> None:
        directory = self.path / "failures" / failure.result_key
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"attempt-{failure.attempt}.json"
        if destination.exists():
            raise ValueError(f"attempt {failure.attempt} already exists for {failure.result_key}")
        if failure.attempt == 2 and not (directory / "attempt-1.json").exists():
            raise ValueError(f"attempt 2 for {failure.result_key} has no first attempt")
        _write_json(destination, _failure_document(failure))

    def read_outcomes(self) -> tuple[CompletedGame | DroppedGame, ...]:
        outcomes: list[CompletedGame | DroppedGame] = []
        games = self.path / "games"
        if not games.exists():
            return ()
        for path in sorted(games.glob("*.json")):
            if path.name.endswith(".tmp"):
                continue
            document = json.loads(path.read_text(encoding="utf-8"))
            result = _result_from_document(document)
            if path.stem != result.result_key:
                raise ValueError(f"{path.name} does not match result key {result.result_key}")
            outcomes.append(result)
        keys = [result.result_key for result in outcomes]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate result keys in the experiment directory")
        return tuple(outcomes)

    def read_failures(self) -> tuple[TechnicalFailure, ...]:
        failures: list[TechnicalFailure] = []
        root = self.path / "failures"
        if not root.exists():
            return ()
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            for attempt in (1, 2):
                path = directory / f"attempt-{attempt}.json"
                if not path.exists():
                    continue
                failure = _failure_from_document(json.loads(path.read_text(encoding="utf-8")))
                if failure.result_key != directory.name or failure.attempt != attempt:
                    raise ValueError(f"{path} does not match its failure")
                failures.append(failure)
        return tuple(failures)


def _freeze_policy(policy: PolicyConfig) -> FrozenPolicySpec:
    model_hash = None
    sidecar_hash = None
    model_path = policy.model_path
    sidecar_path = policy.sidecar_path
    if policy.kind == "model":
        if model_path is None:
            raise ValueError("a model Policy needs a model path")
        model_path = str(Path(model_path).resolve())
        model_hash = _file_hash(Path(model_path))
        if sidecar_path is not None:
            sidecar_path = str(Path(sidecar_path).resolve())
            sidecar_hash = _file_hash(Path(sidecar_path))
    return FrozenPolicySpec(
        name=policy.name,
        kind=policy.kind,
        search_simulations=policy.search_simulations,
        explore=policy.explore,
        model_path=model_path,
        model_hash=model_hash,
        sidecar_path=sidecar_path,
        sidecar_hash=sidecar_hash,
        declared_preferences=policy.declared_preferences,
    )


def _file_hash(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"missing model file {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _plan_document(plan: ExperimentPlan) -> dict[str, object]:
    return {"schema": PLAN_SCHEMA, **_dataclass(plan)}


def _result_document(result: CompletedGame | DroppedGame) -> dict[str, object]:
    kind = "completed" if isinstance(result, CompletedGame) else "dropped"
    return {"schema": RESULT_SCHEMA, "kind": kind, **_dataclass(result)}


def _failure_document(failure: TechnicalFailure) -> dict[str, object]:
    return {"schema": FAILURE_SCHEMA, **_dataclass(failure)}


def _result_from_document(document: Mapping[str, object]) -> CompletedGame | DroppedGame:
    if document.get("schema") != RESULT_SCHEMA:
        raise ValueError("unsupported result schema")
    kind = document.get("kind")
    payload = {key: value for key, value in document.items() if key not in {"schema", "kind"}}
    if kind == "completed":
        return _completed(payload)
    if kind == "dropped":
        return _dropped(payload)
    raise ValueError(f"unknown result kind {kind}")


def _failure_from_document(document: Mapping[str, object]) -> TechnicalFailure:
    if document.get("schema") != FAILURE_SCHEMA:
        raise ValueError("unsupported failure schema")
    return TechnicalFailure(
        result_key=_text(document["result_key"], "result key"),
        pairing_key=_text(document["pairing_key"], "pairing key"),
        attempt=_attempt(document["attempt"]),
        exception_type=_text(document["exception_type"], "exception type"),
        message=_text(document["message"], "failure message"),
    )


def _completed(payload: Mapping[str, object]) -> CompletedGame:
    return CompletedGame(
        **_identity(payload),
        winner=_int(payload["winner"], "winner"),
        seats=tuple(_seat(_mapping(item, "seat")) for item in _items(payload["seats"], "seats")),
    )


def _dropped(payload: Mapping[str, object]) -> DroppedGame:
    if payload["reason"] != "turn_limit":
        raise ValueError("a dropped game reached the turn limit")
    return DroppedGame(
        **_identity(payload),
        reason="turn_limit",
        seats=tuple(
            _partial_seat(_mapping(item, "seat")) for item in _items(payload["seats"], "seats")
        ),
    )


def _identity(payload: Mapping[str, object]) -> _Identity:
    policies = tuple(
        _policy(_mapping(item, "policy")) for item in _items(payload["policies"], "policies")
    )
    return {
        "result_key": _text(payload["result_key"], "result key"),
        "pairing_key": _text(payload["pairing_key"], "pairing key"),
        "seed": _int(payload["seed"], "seed"),
        "map_seed": _int(payload["map_seed"], "map seed"),
        "candidate_seat": _int(payload["candidate_seat"], "candidate seat"),
        "policies": policies,
        "map_policy": _map_policy(payload["map_policy"]),
        "rules": _rules(_mapping(payload["rules"], "rules")),
        "source": _source(_mapping(payload["source"], "source")),
        "engine_version": _text(payload["engine_version"], "engine version"),
        "engine_sha": _text(payload["engine_sha"], "engine source SHA"),
        "plies": _int(payload["plies"], "plies"),
        "turns": _int(payload["turns"], "turns"),
    }


def _seat(payload: Mapping[str, object]) -> SeatResult:
    return SeatResult(
        _int(payload["seat_index"], "seat"),
        _text(payload["seat_name"], "seat name"),
        _text(payload["policy_name"], "policy name"),
        _profile(_mapping(payload["profile"], "profile")),
    )


def _partial_seat(payload: Mapping[str, object]) -> PartialSeatResult:
    return PartialSeatResult(
        _int(payload["seat_index"], "seat"),
        _text(payload["seat_name"], "seat name"),
        _text(payload["policy_name"], "policy name"),
        _partial_profile(_mapping(payload["profile"], "profile")),
    )


def _profile(payload: Mapping[str, object]) -> BehaviorProfile:
    return BehaviorProfile(
        counts=_behavior_counts(_mapping(payload["counts"], "counts")),
        public_victory_points=_int(payload["public_victory_points"], "public victory points"),
        actual_victory_points=_int(payload["actual_victory_points"], "actual victory points"),
        won=_flag(payload["won"], "won"),
        longest_road=_flag(payload["longest_road"], "longest road"),
        largest_army=_flag(payload["largest_army"], "largest army"),
    )


def _partial_profile(payload: Mapping[str, object]) -> PartialBehaviorProfile:
    return PartialBehaviorProfile(
        counts=_behavior_counts(_mapping(payload["counts"], "counts")),
        public_victory_points=_int(payload["public_victory_points"], "public victory points"),
        actual_victory_points=_int(payload["actual_victory_points"], "actual victory points"),
        longest_road=_flag(payload["longest_road"], "longest road"),
        largest_army=_flag(payload["largest_army"], "largest army"),
    )


def _behavior_counts(payload: Mapping[str, object]) -> BehaviorCounts:
    return BehaviorCounts(
        initial_resources=_int(payload["initial_resources"], "initial resources"),
        initial_pips=_int(payload["initial_pips"], "initial pips"),
        adjacent_port=_flag(payload["adjacent_port"], "adjacent port"),
        settlements=_int(payload["settlements"], "settlements"),
        cities=_int(payload["cities"], "cities"),
        roads=_int(payload["roads"], "roads"),
        development_cards=_int(payload["development_cards"], "development cards"),
        knights=_int(payload["knights"], "knights"),
        offers=_int(payload["offers"], "offers"),
        acceptances=_int(payload["acceptances"], "acceptances"),
        completed_trades=_int(payload["completed_trades"], "completed trades"),
        maritime_trades=_int(payload["maritime_trades"], "maritime trades"),
        first_build=_build(payload["first_build"]),
    )


def _policy(payload: Mapping[str, object]) -> FrozenPolicySpec:
    preferences = tuple(
        PolicyPreference(
            _category(_mapping(item, "preference")["category"]),
            _number(_mapping(item, "preference")["delta"], "delta"),
        )
        for item in _items(payload["declared_preferences"], "preferences")
    )
    return FrozenPolicySpec(
        name=_text(payload["name"], "policy name"),
        kind=_policy_kind(payload["kind"]),
        search_simulations=_int(payload["search_simulations"], "search simulations"),
        explore=_flag(payload["explore"], "explore"),
        model_path=_optional_text(payload["model_path"], "model path"),
        model_hash=_optional_text(payload["model_hash"], "model hash"),
        sidecar_path=_optional_text(payload["sidecar_path"], "sidecar path"),
        sidecar_hash=_optional_text(payload["sidecar_hash"], "sidecar hash"),
        declared_preferences=preferences,
    )


def _rules(payload: Mapping[str, object]) -> GameRules:
    return GameRules(
        vps_to_win=_int(payload["vps_to_win"], "victory points"),
        discard_limit=_int(payload["discard_limit"], "discard limit"),
        friendly_robber=_flag(payload["friendly_robber"], "friendly robber"),
        turn_limit=_int(payload["turn_limit"], "turn limit"),
    )


def _source(payload: Mapping[str, object]) -> SourceProvenance:
    return SourceProvenance(
        commit=_text(payload["commit"], "commit"),
        dirty=_flag(payload["dirty"], "dirty"),
        dirty_diff_hash=_optional_text(payload["dirty_diff_hash"], "diff hash"),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _items(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


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


def _attempt(value: object) -> Literal[1, 2]:
    if value == 1:
        return 1
    if value == 2:
        return 2
    raise ValueError("a technical failure records attempt 1 or 2")


def _map_policy(value: object) -> Literal["corpus"]:
    if value != "corpus":
        raise ValueError("version 1 uses the corpus map")
    return "corpus"


def _policy_kind(value: object) -> PolicyKind:
    if value in ("value", "model", "random"):
        return value
    raise ValueError(f"unknown Policy kind {value}")


def _category(value: object) -> PreferenceCategory:
    if value in ("settlement", "city", "road", "development_card", "port"):
        return value
    raise ValueError(f"unknown Policy Preference {value}")


def _build(value: object) -> BuildCategory | None:
    if value is None:
        return None
    if value in ("settlement", "city", "road", "development_card"):
        return value
    raise ValueError("unknown first build")


def _dataclass(value: object) -> dict[str, object]:
    if not is_dataclass(value):
        raise TypeError(f"{type(value).__name__} is not a dataclass")
    return {item.name: _value(getattr(value, item.name)) for item in fields(value)}


def _value(value: object) -> object:
    if is_dataclass(value):
        return _dataclass(value)
    if isinstance(value, tuple):
        return [_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _first_mismatch(left: object, right: object, path: str = "plan") -> str | None:
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                return f"{path}.{key}"
            found = _first_mismatch(left[key], right[key], f"{path}.{key}")
            if found is not None:
                return found
        return None
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return path
        for index, (item, other) in enumerate(zip(left, right, strict=True)):
            found = _first_mismatch(item, other, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if left != right:
        return path
    return None
