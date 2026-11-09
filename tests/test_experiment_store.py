from __future__ import annotations

import json
from pathlib import Path

import pytest

from catan_coach.domain.experiment import (
    BehaviorCounts,
    BehaviorProfile,
    CompletedGame,
    ExperimentConfig,
    ExperimentPlan,
    GameRules,
    PolicyConfig,
    SeatResult,
    SourceProvenance,
    TechnicalFailure,
    schedule,
)
from catan_coach.engine.experiment_store import (
    ExperimentStore,
    PlanMismatch,
    freeze_config,
    load_plan,
)

COMMIT = "d" * 40


def config(model_path: Path, **updates: object) -> ExperimentConfig:
    values: dict[str, object] = {
        "name": "audit",
        "candidate": PolicyConfig(
            "candidate", "model", model_path=str(model_path), search_simulations=0
        ),
        "opponent": PolicyConfig("value", "value"),
        "games_per_candidate_seat": 1,
        "base_seed": 5,
    }
    values.update(updates)
    return ExperimentConfig(**values)  # type: ignore[arg-type]


def frozen(tmp_path: Path, **updates: object) -> ExperimentPlan:
    model = tmp_path / "model.txt"
    model.write_bytes(b"trees")
    return freeze_config(config(model, **updates), SourceProvenance(COMMIT, False))


def completed(plan_path: Path) -> CompletedGame:
    plan = load_plan(plan_path)
    game = schedule(plan)[0]
    seats = tuple(
        SeatResult(
            index,
            f"S{index}",
            game.policies[index].name,
            BehaviorProfile(
                counts=BehaviorCounts(2, 4, False),
                public_victory_points=10 if index == 0 else 2,
                actual_victory_points=10 if index == 0 else 2,
                won=index == 0,
            ),
        )
        for index in range(4)
    )
    return CompletedGame(
        result_key=game.result_key,
        pairing_key=game.pairing_key,
        seed=game.seed,
        map_seed=game.seed,
        candidate_seat=game.candidate_seat,
        policies=game.policies,
        map_policy=game.map_policy,
        rules=game.rules,
        source=game.source,
        engine_version="catanatron",
        engine_sha=COMMIT,
        plies=3,
        turns=1,
        winner=0,
        seats=seats,
    )


def test_open_freezes_and_resume_detects_a_changed_model(tmp_path: Path) -> None:
    plan = frozen(tmp_path)
    ExperimentStore.open(tmp_path / "run", plan)
    assert (tmp_path / "run" / "plan.json").is_file()
    assert ExperimentStore.open(tmp_path / "run", plan).plan == plan

    model = Path(plan.candidate.model_path or "")
    model.write_bytes(b"changed")
    changed = freeze_config(
        config(model, name="audit"),
        SourceProvenance(COMMIT, False),
    )
    with pytest.raises(PlanMismatch, match="model_hash"):
        ExperimentStore.open(tmp_path / "run", changed)


def test_results_round_trip_and_pending_ignores_partial_files(tmp_path: Path) -> None:
    plan = frozen(tmp_path)
    store = ExperimentStore.open(tmp_path / "run", plan)
    scheduled = schedule(plan)
    assert store.pending() == scheduled
    result = completed(tmp_path / "run")
    games = tmp_path / "run" / "games"
    (games / f".{result.result_key}.json.tmp").write_text("{", encoding="utf-8")
    assert store.pending() == scheduled
    store.write_result(result)
    assert [item.result_key for item in store.pending()] == [
        game.result_key for game in scheduled[1:]
    ]
    assert store.read_outcomes() == (result,)


def test_failures_retry_once(tmp_path: Path) -> None:
    plan = frozen(tmp_path)
    store = ExperimentStore.open(tmp_path / "run", plan)
    game = schedule(plan)[0]
    failure = TechnicalFailure(game.result_key, game.pairing_key, 1, "RuntimeError", "boom")
    store.write_failure(failure)
    assert store.pending()[0] == game
    store.write_failure(
        TechnicalFailure(game.result_key, game.pairing_key, 2, "RuntimeError", "boom")
    )
    assert game not in store.pending()
    with pytest.raises(ValueError, match="already exists"):
        store.write_failure(failure)


def test_sidecar_bytes_change_the_frozen_plan(tmp_path: Path) -> None:
    model = tmp_path / "model.txt"
    model.write_bytes(b"trees")
    sidecar = tmp_path / "model.calibration.json"
    sidecar.write_text('{"knots": [[0, 0], [1, 1]]}', encoding="utf-8")
    first = freeze_config(
        ExperimentConfig(
            "audit",
            PolicyConfig("candidate", "model", model_path=str(model), sidecar_path=str(sidecar)),
            PolicyConfig("value", "value"),
            1,
            5,
        ),
        SourceProvenance(COMMIT, False),
    )
    sidecar.write_text('{"knots": [[0, 0], [1, 0.5]]}', encoding="utf-8")
    second = freeze_config(
        ExperimentConfig(
            "audit",
            PolicyConfig("candidate", "model", model_path=str(model), sidecar_path=str(sidecar)),
            PolicyConfig("value", "value"),
            1,
            5,
        ),
        SourceProvenance(COMMIT, False),
    )
    assert first.candidate.sidecar_hash != second.candidate.sidecar_hash


def test_a_mismatched_result_file_fails(tmp_path: Path) -> None:
    plan = frozen(tmp_path, rules=GameRules())
    store = ExperimentStore.open(tmp_path / "run", plan)
    result = completed(tmp_path / "run")
    document = json.loads((tmp_path / "run" / "plan.json").read_text(encoding="utf-8"))
    assert document["name"] == "audit"
    store.write_result(result)
    path = tmp_path / "run" / "games" / f"{result.result_key}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["pairing_key"] = "not-the-pairing-key"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = store.read_outcomes()
    with pytest.raises(ValueError, match="does not match"):
        from catan_coach.domain.experiment_report import summarize

        summarize(plan, schedule(plan), loaded, ())
