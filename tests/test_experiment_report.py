from __future__ import annotations

import json

import numpy as np
import pytest

from catan_coach.domain.experiment import (
    BehaviorCounts,
    BehaviorProfile,
    BuildCategory,
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
    EffectEstimate,
    InterventionReport,
    compare,
    format_comparison,
    format_report,
    intervention_from_json,
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


def played(
    game: ScheduledGame,
    *,
    won: bool,
    settlements: int = 0,
    cities: int = 0,
    first_build: BuildCategory | None = None,
) -> CompletedGame:
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
                    counts=counts(
                        settlements=settlements if candidate else 0,
                        cities=cities if candidate else 0,
                        first_build=first_build if candidate else None,
                    ),
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
    settlements = dict(effect.behavior_differences)["settlements"]
    assert settlements.difference == 2
    assert settlements.lower == settlements.upper == 2
    assert settlements.pairs == 4
    assert effect.manipulation_check is not None
    assert effect.manipulation_check.field == "settlements"
    assert effect.manipulation_check.passed
    assert effect.manipulation_check.difference == settlements.difference
    assert effect.attrition_bounds_same_sign
    assert effect.valid
    text = format_comparison(report)
    assert "not automatically a causal claim" in text
    assert "Valid for an effect claim." in text
    assert "Dropped 0 reference, 0 variant." in text
    assert "Terminal failures 0 reference, 0 variant." in text
    assert "Seat 0:" in text
    assert "Behavior change per completed pair: settlements +2.00" in text
    assert "Manipulation check (settlements): +2.0000 (+2.0000 to +2.0000), passed." in text
    assert "Attrition bounds have the same sign as the estimate." in text

    bounded_report = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=True) for game in reference_games],
            [played(variant_games[0], won=False)],
        ),
        ((), ()),
        seed=1,
    )
    bounded = bounded_report.variants[0]
    assert bounded.unresolved_pairs == 3
    assert bounded.lower_bound.difference < bounded.upper_bound.difference
    assert bounded.claim == "none"
    assert bounded.estimate.difference < 0
    assert bounded.lower_bound.difference < 0
    assert bounded.upper_bound.difference < 0
    assert bounded.attrition_bounds_same_sign
    assert "Attrition bounds have the same sign as the estimate." in format_comparison(
        bounded_report
    )

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


def test_behavior_intervals_share_the_win_rate_seed() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="settlement",
        candidate=model(declared_preferences=(PolicyPreference("settlement", 0.05),)),
    )
    reference_games = schedule(reference)
    variant_games = schedule(variant)
    settlements = (0, 1, 2, 1)
    report = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=True) for game in reference_games],
            [
                played(game, won=True, settlements=count, cities=count, first_build="settlement")
                for game, count in zip(variant_games, settlements, strict=True)
            ],
        ),
        ((), ()),
        seed=20261109,
    )
    again = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=True) for game in reference_games],
            [
                played(game, won=True, settlements=count, cities=count, first_build="settlement")
                for game, count in zip(variant_games, settlements, strict=True)
            ],
        ),
        ((), ()),
        seed=20261109,
    )
    assert _rendered(report) == _rendered(again)
    effect = report.variants[0]
    by_name = dict(effect.behavior_differences)
    expected = _paired_interval(settlements, 20261109)
    assert by_name["settlements"] == by_name["cities"] == expected
    assert by_name["initial_pips"].lower == by_name["initial_pips"].upper == 0
    assert by_name["first_build_settlement"].difference == 1
    assert by_name["first_build_none"].difference == -1
    assert by_name["public_victory_points"].difference == 0
    assert set(by_name) == {
        "settlements",
        "cities",
        "roads",
        "development_cards",
        "knights",
        "offers",
        "acceptances",
        "completed_trades",
        "maritime_trades",
        "initial_pips",
        "longest_road_rate",
        "largest_army_rate",
        "initial_resources",
        "adjacent_port_rate",
        "public_victory_points",
        "actual_victory_points",
        "first_build_settlement",
        "first_build_city",
        "first_build_road",
        "first_build_development_card",
        "first_build_none",
    }
    _assert_markdown_matches_json(report)


def test_attrition_sign_fails_when_a_missing_outcome_bound_flips() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="settlement",
        candidate=model(declared_preferences=(PolicyPreference("settlement", 0.05),)),
    )
    reference_games = schedule(reference)
    variant_games = schedule(variant)
    report = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(reference_games[0], won=False)],
            [played(variant_games[0], won=True)],
        ),
        ((), ()),
        seed=11,
    )
    effect = report.variants[0]
    assert effect.estimate.difference == 1
    assert effect.lower_bound.difference == pytest.approx(-0.5)
    assert effect.upper_bound.difference == 1
    assert not effect.attrition_bounds_same_sign
    assert "Attrition bounds do not have the same sign as the estimate." in format_comparison(
        report
    )


def test_manipulation_check_fails_when_the_build_interval_includes_zero() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="settlement",
        candidate=model(declared_preferences=(PolicyPreference("settlement", 0.05),)),
    )
    reference_games = schedule(reference)
    variant_games = schedule(variant)
    # Three extra settlements and one fewer: the mean is positive and the interval covers zero.
    reference_counts = (0, 0, 0, 1)
    variant_counts = (1, 1, 1, 0)
    report = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [
                played(game, won=False, settlements=count)
                for game, count in zip(reference_games, reference_counts, strict=True)
            ],
            [
                played(game, won=True, settlements=count)
                for game, count in zip(variant_games, variant_counts, strict=True)
            ],
        ),
        ((), ()),
        seed=20261109,
    )
    effect = report.variants[0]
    settlements = dict(effect.behavior_differences)["settlements"]
    assert settlements.difference == pytest.approx(0.5)
    assert settlements.lower <= 0 <= settlements.upper
    assert effect.manipulation_check is not None
    assert not effect.manipulation_check.passed
    assert effect.manipulation_check.lower == settlements.lower
    assert effect.manipulation_check.upper == settlements.upper
    assert "failed." in format_comparison(report)


def test_city_preference_checks_city_builds() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="city",
        candidate=model(declared_preferences=(PolicyPreference("city", 0.05),)),
    )
    reference_games = schedule(reference)
    variant_games = schedule(variant)
    report = compare(
        reference,
        (variant,),
        (reference_games, variant_games),
        (
            [played(game, won=False, cities=0) for game in reference_games],
            [played(game, won=False, cities=1) for game in variant_games],
        ),
        ((), ()),
        seed=7,
    )
    effect = report.variants[0]
    check = effect.manipulation_check
    assert check is not None
    assert check.field == "cities"
    assert check.passed
    assert check.difference == 1
    assert dict(effect.behavior_differences)["settlements"].difference == 0
    assert effect.estimate.difference == 0
    assert effect.attrition_bounds_same_sign


def test_manipulation_check_is_absent_for_other_preferences() -> None:
    reference = experiment(name="reference")
    reference_games = schedule(reference)
    road = experiment(
        name="road",
        candidate=model(declared_preferences=(PolicyPreference("road", 0.05),)),
    )
    road_games = schedule(road)
    road_report = compare(
        reference,
        (road,),
        (reference_games, road_games),
        (
            [played(game, won=False) for game in reference_games],
            [played(game, won=True) for game in road_games],
        ),
        ((), ()),
        seed=3,
    )
    assert road_report.variants[0].manipulation_check is None
    assert "Manipulation check: not applicable." in format_comparison(road_report)

    negative = experiment(
        name="fewer-settlements",
        candidate=model(declared_preferences=(PolicyPreference("settlement", -0.05),)),
    )
    negative_games = schedule(negative)
    negative_report = compare(
        reference,
        (negative,),
        (reference_games, negative_games),
        (
            [played(game, won=False) for game in reference_games],
            [played(game, won=True) for game in negative_games],
        ),
        ((), ()),
        seed=3,
    )
    assert negative_report.variants[0].manipulation_check is None


def test_old_comparison_json_loads_and_regeneration_matches() -> None:
    reference = experiment(name="reference")
    variant = experiment(
        name="settlement",
        candidate=model(declared_preferences=(PolicyPreference("settlement", 0.05),)),
    )
    reference_games = schedule(reference)
    variant_games = schedule(variant)
    counts = (0, 1, 2, 1)

    def run() -> InterventionReport:
        return compare(
            reference,
            (variant,),
            (reference_games, variant_games),
            (
                [played(game, won=index % 2 == 0) for index, game in enumerate(reference_games)],
                [
                    played(game, won=index % 2 == 1, settlements=count)
                    for index, (game, count) in enumerate(zip(variant_games, counts, strict=True))
                ],
            ),
            ((), ()),
            seed=20261109,
        )

    report = run()
    repeat = run()
    assert _rendered(report) == _rendered(repeat)
    parsed: object = json.loads(_rendered(report)[1])
    assert intervention_from_json(parsed) == report
    _assert_markdown_matches_json(report)

    assert isinstance(parsed, dict)
    variants = parsed["variants"]
    assert isinstance(variants, list)
    for item in variants:
        assert isinstance(item, dict)
        del item["behavior_differences"]
        del item["manipulation_check"]
        del item["attrition_bounds_same_sign"]
    loaded = intervention_from_json(parsed)
    old = loaded.variants[0]
    assert old.behavior_differences == ()
    assert old.manipulation_check is None
    assert old.attrition_bounds_same_sign is False
    assert old.estimate == report.variants[0].estimate
    assert old.behavior_deltas == report.variants[0].behavior_deltas
    assert old.valid is report.variants[0].valid
    assert "Behavior paired differences: none." in format_comparison(loaded)


def _rendered(report: InterventionReport) -> tuple[str, str]:
    text = format_comparison(report)
    payload = json.dumps(report_to_json(report), sort_keys=True, indent=2) + "\n"
    return text, payload


def _assert_markdown_matches_json(report: InterventionReport) -> None:
    text = format_comparison(report)
    payload = report_to_json(report)
    variants = payload["variants"]
    assert isinstance(variants, list)
    for variant in variants:
        assert isinstance(variant, dict)
        differences = variant["behavior_differences"]
        assert isinstance(differences, list)
        for item in differences:
            assert isinstance(item, list) and len(item) == 2
            name, effect = item
            assert isinstance(name, str)
            assert isinstance(effect, dict)
            difference = effect["difference"]
            lower = effect["lower"]
            upper = effect["upper"]
            pairs = effect["pairs"]
            assert isinstance(difference, float)
            assert isinstance(lower, float)
            assert isinstance(upper, float)
            assert isinstance(pairs, int)
            fragment = f"- {name}: {difference:+.4f} ({lower:+.4f} to {upper:+.4f}, {pairs} pairs)"
            assert fragment in text
        check = variant["manipulation_check"]
        if check is None:
            assert "Manipulation check: not applicable." in text
        else:
            assert isinstance(check, dict)
            field = check["field"]
            difference = check["difference"]
            lower = check["lower"]
            upper = check["upper"]
            passed = check["passed"]
            assert isinstance(field, str)
            assert isinstance(difference, float)
            assert isinstance(lower, float)
            assert isinstance(upper, float)
            assert isinstance(passed, bool)
            verdict = "passed" if passed else "failed"
            assert (
                f"Manipulation check ({field}): {difference:+.4f} "
                f"({lower:+.4f} to {upper:+.4f}), {verdict}."
            ) in text
        if variant["attrition_bounds_same_sign"]:
            assert "Attrition bounds have the same sign as the estimate." in text
        else:
            assert "Attrition bounds do not have the same sign as the estimate." in text


def _paired_interval(values: tuple[int, ...], seed: int) -> EffectEstimate:
    observed = float(np.mean(np.asarray(values, dtype=np.float64)))
    generator = np.random.Generator(np.random.PCG64(seed))
    sample = np.asarray(values, dtype=np.float64)
    draws = generator.integers(0, len(sample), size=(10_000, len(sample)))
    means = sample[draws].mean(axis=1)
    lower, upper = np.quantile(means, (0.025, 0.975), method="linear")
    return EffectEstimate(len(values), observed, float(lower), float(upper))


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
