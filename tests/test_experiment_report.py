from __future__ import annotations

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
    schedule,
)
from catan_coach.domain.experiment_report import (
    compare,
    format_comparison,
    format_report,
    report_to_json,
    summarize,
    wilson,
)

HASH = "a" * 64
COMMIT = "c" * 40


def source() -> SourceProvenance:
    return SourceProvenance(COMMIT, False)


def model(**updates: object) -> FrozenPolicySpec:
    values: dict[str, object] = {
        "name": "generation-7",
        "kind": "model",
        "model_path": "model.txt",
        "model_hash": HASH,
        "search_simulations": 0,
    }
    values.update(updates)
    return FrozenPolicySpec(**values)  # type: ignore[arg-type]


def experiment(**updates: object) -> ExperimentPlan:
    values: dict[str, object] = {
        "name": "audit",
        "candidate": model(),
        "opponent": FrozenPolicySpec(name="ValueFunctionPlayer", kind="value"),
        "games_per_candidate_seat": 1,
        "base_seed": 20_000,
        "source": source(),
    }
    values.update(updates)
    return ExperimentPlan(**values)  # type: ignore[arg-type]


def counts(**updates: object) -> BehaviorCounts:
    values: dict[str, object] = {
        "initial_resources": 3,
        "initial_pips": 8,
        "adjacent_port": False,
        "settlements": 0,
        "cities": 0,
    }
    values.update(updates)
    return BehaviorCounts(**values)  # type: ignore[arg-type]


def played(game: ScheduledGame, *, won: bool, settlements: int = 0) -> CompletedGame:
    winner = game.candidate_seat if won else (game.candidate_seat + 1) % 4
    seats = []
    for index in range(4):
        candidate = index == game.candidate_seat
        seats.append(
            SeatResult(
                index,
                f"S{index}",
                game.policies[index].name,
                BehaviorProfile(
                    counts=counts(settlements=settlements if candidate else 0),
                    public_victory_points=10 if index == winner else 4,
                    actual_victory_points=10 if index == winner else 4,
                    won=index == winner,
                ),
            )
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
        plies=8,
        turns=3,
        winner=winner,
        seats=tuple(seats),
    )


def dropped(game: ScheduledGame) -> DroppedGame:
    return DroppedGame(
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
        plies=2,
        turns=1,
        reason="turn_limit",
        seats=tuple(
            PartialSeatResult(
                index,
                f"S{index}",
                game.policies[index].name,
                PartialBehaviorProfile(
                    counts=counts(),
                    public_victory_points=2,
                    actual_victory_points=2,
                ),
            )
            for index in range(4)
        ),
    )


def test_wilson_matches_hand_calculated_cases() -> None:
    certain = wilson(1, 1)
    assert certain.rate == 1
    assert certain.lower == pytest.approx(0.20654931437723745)
    assert certain.upper == pytest.approx(1)
    empty = wilson(0, 1)
    assert empty.lower == pytest.approx(0)
    assert empty.upper == pytest.approx(0.7934506856227626)
    balanced = wilson(50, 100)
    assert balanced.lower == pytest.approx(0.4038315303659956)
    assert balanced.upper == pytest.approx(0.5961684696340044)
    assert wilson(0, 0).rate is None


def test_all_wins_losses_and_seat_denominators() -> None:
    plan = experiment()
    games = schedule(plan)
    report = summarize(plan, games, [played(game, won=True, settlements=2) for game in games], ())

    assert report.valid
    assert report.wins.successes == 4
    assert report.wins.count == 4
    assert report.wins.rate == 1
    assert [seat.completed for seat in report.seats] == [1, 1, 1, 1]
    assert report.candidate_wins.games == 4
    assert report.candidate_wins.settlements == 2
    assert report.candidate_losses.games == 0
    assert "Descriptive association only" in format_report(report)
    assert "100.0%" in format_report(report)
    assert "ValueFunctionPlayer" in format_report(report)

    losses = summarize(plan, games, [played(game, won=False) for game in games], ())
    assert losses.wins.rate == 0
    assert losses.candidate_losses.games == 4
    assert losses.candidate_victory_point_mean == 4


def test_dropped_and_failed_games_control_validity() -> None:
    plan = experiment()
    games = schedule(plan)
    one_drop = summarize(
        plan,
        games,
        [
            played(games[0], won=True),
            dropped(games[1]),
            played(games[2], won=False),
            played(games[3], won=True),
        ],
        (),
    )
    assert one_drop.completed == 3
    assert one_drop.dropped == 1
    assert one_drop.wins.count == 3
    assert one_drop.attrition_as_losses.count == 4
    assert one_drop.attrition_as_losses.successes == 2
    assert one_drop.attrition_as_wins.successes == 3
    assert not one_drop.valid

    failed = summarize(
        plan,
        games,
        [played(game, won=True) for game in games[:3]],
        (
            TechnicalFailure(games[3].result_key, games[3].pairing_key, 1, "RuntimeError", "boom"),
            TechnicalFailure(games[3].result_key, games[3].pairing_key, 2, "RuntimeError", "boom"),
        ),
    )
    assert failed.terminal_failures == 1
    assert not failed.valid
    assert "Not valid" in format_report(failed)

    large = experiment(games_per_candidate_seat=25)
    scheduled = schedule(large)
    kept: list[CompletedGame | DroppedGame] = [
        dropped(scheduled[0]),
        *[played(game, won=True) for game in scheduled[1:]],
    ]
    rare = summarize(large, scheduled, kept, ())
    assert rare.dropped == 1
    assert rare.valid


def test_duplicate_and_missing_results() -> None:
    plan = experiment()
    games = schedule(plan)
    with pytest.raises(ValueError, match="duplicate"):
        summarize(plan, games, [played(games[0], won=True), played(games[0], won=False)], ())
    partial = summarize(plan, games, [played(games[0], won=True)], ())
    assert partial.missing == 3
    assert not partial.valid
    assert "no result" in partial.warnings[0]


def test_json_is_finite_and_deterministic() -> None:
    plan = experiment()
    games = schedule(plan)
    report = summarize(
        plan, games, [played(game, won=index % 2 == 0) for index, game in enumerate(games)], ()
    )
    payload = report_to_json(report)
    assert payload == report_to_json(report)
    assert "NaN" not in str(payload)
    candidate = payload["candidate"]
    assert isinstance(candidate, dict)
    assert candidate["model_hash"] == HASH
    assert payload["base_seed"] == 20_000


def test_paired_comparison_bounds_and_behavior() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="settlement",
        candidate=model(declared_preferences=(PolicyPreference("settlement", 0.05),)),
    )
    reference_games = schedule(reference)
    variant_games = schedule(variant)
    assert [game.pairing_key for game in reference_games] == [
        game.pairing_key for game in variant_games
    ]
    assert [game.result_key for game in reference_games] != [
        game.result_key for game in variant_games
    ]
    report = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=False, settlements=0) for game in reference_games],
            [played(game, won=True, settlements=2) for game in variant_games],
        ),
        ((), ()),
        seed=20261109,
    )
    effect = report.variants[0]
    assert effect.estimate.difference == 1
    assert effect.estimate.lower == effect.estimate.upper == 1
    assert effect.behavior_deltas[0] == ("settlements", 2)
    assert effect.valid
    text = format_comparison(report)
    assert "not automatically a causal claim" in text
    assert "Valid for an effect claim." in text
    assert "Dropped 0 reference, 0 variant." in text
    assert "Terminal failures 0 reference, 0 variant." in text
    assert "Seat 0:" in text
    assert "Behavior change per completed pair: settlements +2.00" in text

    bounded = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=True) for game in reference_games],
            [played(variant_games[0], won=False)],
        ),
        ((), ()),
        seed=1,
    ).variants[0]
    assert bounded.unresolved_pairs == 3
    assert bounded.lower_bound.difference < bounded.upper_bound.difference
    assert bounded.claim == "none"

    poisoned = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=False) for game in reference_games],
            [played(game, won=True) for game in variant_games[1:]],
        ),
        (
            (),
            (
                TechnicalFailure(
                    variant_games[0].result_key,
                    variant_games[0].pairing_key,
                    1,
                    "RuntimeError",
                    "x",
                ),
                TechnicalFailure(
                    variant_games[0].result_key,
                    variant_games[0].pairing_key,
                    2,
                    "RuntimeError",
                    "x",
                ),
            ),
        ),
        seed=1,
    ).variants[0]
    assert not poisoned.valid
    assert poisoned.claim == "none"


def test_a_comparison_without_completed_pairs_is_refused() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="settlement",
        candidate=model(declared_preferences=(PolicyPreference("settlement", 0.05),)),
    )
    with pytest.raises(ValueError, match="completed pair"):
        compare(
            reference,
            (variant,),
            (schedule(reference), schedule(variant)),
            ((), ()),
            ((), ()),
            seed=1,
        )


def test_two_preference_changes_are_not_one_intervention() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="both",
        candidate=model(
            declared_preferences=(
                PolicyPreference("settlement", 0.05),
                PolicyPreference("city", 0.05),
            )
        ),
    )
    with pytest.raises(ValueError, match="preferences"):
        compare(
            reference,
            (variant,),
            (schedule(reference), schedule(variant)),
            ((), ()),
            ((), ()),
            seed=1,
        )


def test_incompatible_plans_name_the_field() -> None:
    reference = experiment()
    shifted = experiment(base_seed=20_100)
    with pytest.raises(ValueError, match="base_seed"):
        compare(
            reference,
            (shifted,),
            (schedule(reference), schedule(shifted)),
            ((), ()),
            ((), ()),
            seed=0,
        )


def test_rules_change_is_visible() -> None:
    plan = experiment(rules=GameRules(vps_to_win=8))
    report = summarize(plan, schedule(plan), (), ())
    assert report.vps_to_win == 8
    assert "vp=8" in format_report(report)
