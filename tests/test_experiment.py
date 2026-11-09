from __future__ import annotations

import dataclasses

import pytest

from catan_coach.domain.experiment import (
    BehaviorCounts,
    BehaviorProfile,
    CompletedGame,
    DroppedGame,
    ExperimentPlan,
    FrozenPolicySpec,
    GameRules,
    PartialBehaviorProfile,
    PartialSeatResult,
    PolicyPreference,
    ScheduledGame,
    SeatResult,
    SourceProvenance,
    TechnicalFailure,
    preferences,
    schedule,
)

HASH = "a" * 64
SIDECAR = "b" * 64
COMMIT = "c" * 40


def source(**updates: object) -> SourceProvenance:
    values: dict[str, object] = {"commit": COMMIT, "dirty": False}
    values.update(updates)
    return SourceProvenance(**values)  # type: ignore[arg-type]


def model(**updates: object) -> FrozenPolicySpec:
    values: dict[str, object] = {
        "name": "candidate",
        "kind": "model",
        "model_path": "model.txt",
        "model_hash": HASH,
        "search_simulations": 4,
    }
    values.update(updates)
    return FrozenPolicySpec(**values)  # type: ignore[arg-type]


def plan(**updates: object) -> ExperimentPlan:
    values: dict[str, object] = {
        "name": "audit",
        "candidate": model(),
        "opponent": FrozenPolicySpec(name="value", kind="value"),
        "games_per_candidate_seat": 2,
        "base_seed": 20_000,
        "source": source(),
    }
    values.update(updates)
    return ExperimentPlan(**values)  # type: ignore[arg-type]


def counts() -> BehaviorCounts:
    return BehaviorCounts(initial_resources=3, initial_pips=8, adjacent_port=False)


def profile(*, won: bool) -> BehaviorProfile:
    return BehaviorProfile(
        counts=counts(),
        public_victory_points=10 if won else 6,
        actual_victory_points=10 if won else 6,
        won=won,
    )


def completed(scheduled: ScheduledGame) -> CompletedGame:
    seats = tuple(
        SeatResult(index, f"S{index}", scheduled.policies[index].name, profile(won=index == 0))
        for index in range(4)
    )
    return CompletedGame(
        result_key=scheduled.result_key,
        pairing_key=scheduled.pairing_key,
        seed=scheduled.seed,
        map_seed=scheduled.seed,
        candidate_seat=scheduled.candidate_seat,
        policies=scheduled.policies,
        map_policy=scheduled.map_policy,
        rules=scheduled.rules,
        source=scheduled.source,
        engine_version="catanatron",
        engine_sha=COMMIT,
        plies=12,
        turns=4,
        winner=0,
        seats=seats,
    )


def test_schedule_is_deterministic_and_balanced() -> None:
    first = schedule(plan())
    second = schedule(plan())

    assert first == second
    assert len(first) == 8
    assert len({game.seed for game in first}) == 8
    assert len({game.result_key for game in first}) == 8
    assert [game.seed for game in first] == list(range(20_000, 20_008))
    assert [sum(game.candidate_seat == seat for game in first) for seat in range(4)] == [2, 2, 2, 2]
    for block in range(2):
        seats = {game.candidate_seat for game in first[block * 4 : (block + 1) * 4]}
        assert seats == {0, 1, 2, 3}


def test_play_fields_change_both_keys_and_preferences_change_only_result_keys() -> None:
    baseline = schedule(plan())
    variants = [
        plan(base_seed=20_100),
        plan(candidate=model(search_simulations=0)),
        plan(candidate=model(model_hash="d" * 64)),
        plan(candidate=model(sidecar_path="map.json", sidecar_hash=SIDECAR)),
        plan(map_policy="corpus", rules=GameRules(vps_to_win=8)),
        plan(source=source(commit="d" * 40)),
    ]
    for variant in variants:
        paired = schedule(variant)
        assert [game.result_key for game in paired] != [game.result_key for game in baseline]
        assert [game.pairing_key for game in paired] != [game.pairing_key for game in baseline]

    unbiased = schedule(plan(candidate=model(search_simulations=0)))
    preferred = schedule(
        plan(
            candidate=model(
                search_simulations=0,
                declared_preferences=(PolicyPreference("city", 0.05),),
            )
        )
    )
    assert [game.pairing_key for game in preferred] == [game.pairing_key for game in unbiased]
    assert [game.result_key for game in preferred] != [game.result_key for game in unbiased]


def test_candidate_seat_changes_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "catan_coach.domain.experiment._block_seats", lambda _seed, _block: (0, 1, 2, 3)
    )
    first = schedule(plan(games_per_candidate_seat=1))[0]
    monkeypatch.setattr(
        "catan_coach.domain.experiment._block_seats", lambda _seed, _block: (1, 0, 2, 3)
    )
    second = schedule(plan(games_per_candidate_seat=1))[0]

    assert first.seed == second.seed
    assert first.candidate_seat != second.candidate_seat
    assert first.result_key != second.result_key
    assert first.pairing_key != second.pairing_key


def test_display_name_is_not_play_identity() -> None:
    original = schedule(plan())
    renamed = schedule(plan(name="renamed"))
    assert [game.result_key for game in renamed] == [game.result_key for game in original]
    assert [game.pairing_key for game in renamed] == [game.pairing_key for game in original]


def test_preferences_are_canonical() -> None:
    ordered = preferences((PolicyPreference("port", -0.2), PolicyPreference("settlement", 0.5)))
    assert [item.category for item in ordered] == ["settlement", "port"]
    with pytest.raises(ValueError, match="omitted"):
        PolicyPreference("road", 0)
    with pytest.raises(ValueError, match="twice"):
        preferences((PolicyPreference("city", 0.1), PolicyPreference("city", 0.2)))
    with pytest.raises(ValueError, match="between -1 and 1"):
        PolicyPreference("city", float("nan"))
    with pytest.raises(ValueError, match="only a model"):
        FrozenPolicySpec(
            name="value",
            kind="value",
            declared_preferences=(PolicyPreference("settlement", 0.1),),
        )
    with pytest.raises(ValueError, match="zero search"):
        model(
            search_simulations=4,
            declared_preferences=(PolicyPreference("city", 0.05),),
        )


def test_model_files_follow_kind_and_hash_pairs() -> None:
    with pytest.raises(ValueError, match="model path"):
        FrozenPolicySpec(name="candidate", kind="model")
    with pytest.raises(ValueError, match="model hash"):
        FrozenPolicySpec(name="candidate", kind="model", model_path="model.txt")
    with pytest.raises(ValueError, match="both be present"):
        model(sidecar_path="map.json")
    with pytest.raises(ValueError, match="only a model"):
        FrozenPolicySpec(name="value", kind="value", model_path="model.txt", model_hash=HASH)


def test_plan_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="exactly four"):
        plan(player_count=3)
    with pytest.raises(ValueError, match="at least 1"):
        plan(games_per_candidate_seat=0)
    with pytest.raises(ValueError, match="non-negative"):
        plan(base_seed=-1)
    with pytest.raises(ValueError, match="corpus map"):
        plan(map_policy="standard")


def test_results_reject_inconsistent_outcomes() -> None:
    scheduled = schedule(plan(games_per_candidate_seat=1))[0]
    game = completed(scheduled)
    with pytest.raises(ValueError, match="exactly the winner"):
        CompletedGame(
            **{
                **{field.name: getattr(game, field.name) for field in dataclasses.fields(game)},
                "winner": 1,
            }
        )
    with pytest.raises(ValueError, match="attempt 1 or 2"):
        TechnicalFailure(scheduled.result_key, scheduled.pairing_key, 3, "RuntimeError", "boom")  # type: ignore[arg-type]
    dropped = DroppedGame(
        result_key=scheduled.result_key,
        pairing_key=scheduled.pairing_key,
        seed=scheduled.seed,
        map_seed=scheduled.seed,
        candidate_seat=scheduled.candidate_seat,
        policies=scheduled.policies,
        map_policy=scheduled.map_policy,
        rules=scheduled.rules,
        source=scheduled.source,
        engine_version="catanatron",
        engine_sha=COMMIT,
        plies=4,
        turns=1000,
        reason="turn_limit",
        seats=tuple(
            PartialSeatResult(
                index,
                f"S{index}",
                scheduled.policies[index].name,
                PartialBehaviorProfile(
                    counts=BehaviorCounts(initial_resources=2, initial_pips=4, adjacent_port=True),
                    public_victory_points=4,
                    actual_victory_points=4,
                ),
            )
            for index in range(4)
        ),
    )
    assert dropped.reason == "turn_limit"
    assert not hasattr(dropped.seats[0].profile, "won")
    assert counts().initial_resources == 3
