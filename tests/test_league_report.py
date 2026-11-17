from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal

import pytest

from catan_coach.domain.experiment import (
    BehaviorCounts,
    BehaviorProfile,
    CompletedGame,
    DroppedGame,
    FrozenPolicySpec,
    GameRules,
    PartialBehaviorProfile,
    PartialSeatResult,
    SeatResult,
    SourceProvenance,
    TechnicalFailure,
)
from catan_coach.domain.experiment_report import _BEHAVIOR_FIELDS
from catan_coach.domain.league import LeagueGame, LeaguePlan, schedule
from catan_coach.domain.league_report import (
    BehaviorEstimate,
    EntrantBehavior,
    LeagueReport,
    canonical_plan_json,
    format_league_report,
    league_report_to_json,
    plan_hash,
    summarize_league,
)
from catan_coach.domain.rating import DISPLAY_SCALE, HeadToHead

COMMIT = "c" * 40


def entrant(name: str) -> FrozenPolicySpec:
    return FrozenPolicySpec(name=name, kind="value")


def league(*names: str, cycles: int = 1) -> LeaguePlan:
    return LeaguePlan(
        name="league",
        entrants=tuple(entrant(name) for name in names),
        cycles=cycles,
        base_seed=200_000,
    )


def provenance(*, dirty: bool = False) -> SourceProvenance:
    if dirty:
        return SourceProvenance(COMMIT, True, "d" * 64)
    return SourceProvenance(COMMIT, False)


def finish(
    game: LeagueGame,
    winner: str,
    source: SourceProvenance,
    *,
    settlements: Mapping[str, int] | None = None,
    turns: int = 20,
) -> CompletedGame:
    names = tuple(item.name for item in game.entrants)
    winner_seat = names.index(winner)
    given = settlements or {}
    seats = tuple(
        SeatResult(
            index,
            f"S{index}",
            name,
            BehaviorProfile(
                counts=BehaviorCounts(
                    initial_resources=3,
                    initial_pips=8,
                    adjacent_port=False,
                    settlements=given.get(name, 0),
                    cities=1 if index == winner_seat else 0,
                    first_build="settlement" if index == winner_seat else None,
                ),
                public_victory_points=10 if index == winner_seat else 2,
                actual_victory_points=10 if index == winner_seat else 2,
                won=index == winner_seat,
                longest_road=index == winner_seat,
            ),
        )
        for index, name in enumerate(names)
    )
    return CompletedGame(
        result_key=game.game_id,
        pairing_key=game.pairing_key,
        seed=game.seed,
        map_seed=game.seed,
        candidate_seat=0,
        policies=game.entrants,
        map_policy=game.map_policy,
        rules=game.rules,
        source=source,
        engine_version="catanatron",
        engine_sha=COMMIT,
        plies=12,
        turns=turns,
        winner=winner_seat,
        seats=seats,
    )


def abandon(game: LeagueGame, source: SourceProvenance) -> DroppedGame:
    return DroppedGame(
        result_key=game.game_id,
        pairing_key=game.pairing_key,
        seed=game.seed,
        map_seed=game.seed,
        candidate_seat=0,
        policies=game.entrants,
        map_policy=game.map_policy,
        rules=game.rules,
        source=source,
        engine_version="catanatron",
        engine_sha=COMMIT,
        plies=2,
        turns=1,
        reason="turn_limit",
        seats=tuple(
            PartialSeatResult(
                index,
                f"S{index}",
                item.name,
                PartialBehaviorProfile(
                    counts=BehaviorCounts(initial_resources=3, initial_pips=8, adjacent_port=False),
                    public_victory_points=2,
                    actual_victory_points=2,
                ),
            )
            for index, item in enumerate(game.entrants)
        ),
    )


def failure(game: LeagueGame, attempt: Literal[1, 2]) -> TechnicalFailure:
    return TechnicalFailure(game.game_id, game.pairing_key, attempt, "RuntimeError", "boom")


def played(
    plan: LeaguePlan,
    source: SourceProvenance,
    *,
    winner: str = "A",
    settlements: Mapping[str, int] | None = None,
    turns_for: Mapping[str, int] | None = None,
) -> tuple[tuple[LeagueGame, ...], tuple[CompletedGame, ...]]:
    games = schedule(plan)
    given_turns = turns_for or {}
    outcomes = tuple(
        finish(
            game,
            winner,
            source,
            settlements=settlements,
            turns=given_turns.get(game.game_id, 20),
        )
        for game in games
    )
    return games, outcomes


def report_for(
    plan: LeaguePlan,
    games: Sequence[LeagueGame],
    outcomes: Sequence[CompletedGame | DroppedGame],
    failures: Sequence[TechnicalFailure] = (),
    *,
    source: SourceProvenance | None = None,
    n_replicates: int = 20,
    seed: int = 0,
) -> LeagueReport:
    return summarize_league(
        plan,
        provenance() if source is None else source,
        games,
        outcomes,
        failures,
        n_replicates=n_replicates,
        seed=seed,
    )


def _behavior(report: LeagueReport, name: str) -> EntrantBehavior:
    for row in report.behavior:
        if row.name == name:
            return row
    raise AssertionError(name)


def _mean(row: EntrantBehavior, split: str, field: str) -> BehaviorEstimate:
    chosen = row.wins if split == "wins" else row.losses
    for name, estimate in chosen.means:
        if name == field:
            return estimate
    raise AssertionError(field)


def _cell(report: LeagueReport, entrant_name: str, opponent: str) -> HeadToHead:
    for cell in report.head_to_head:
        if cell.entrant == entrant_name and cell.opponent == opponent:
            return cell
    raise AssertionError((entrant_name, opponent))


def test_the_ladder_orders_entrants_by_rating() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    games, outcomes = played(plan, source)
    report = report_for(plan, games, outcomes)
    ranked = [(row.rating, row.name) for row in report.ladder]
    assert report.ladder[0].name == "A"
    assert ranked == sorted(ranked, key=lambda item: (-item[0], item[1]))
    assert report.ladder[0].rating > report.ladder[1].rating
    assert sum(row.rating for row in report.ladder) == pytest.approx(0.0, abs=1e-8)
    leader = report.ladder[0]
    assert leader.display == pytest.approx(leader.rating * DISPLAY_SCALE)
    assert leader.interval.lower == pytest.approx(leader.display)
    assert leader.interval.upper == pytest.approx(leader.display)
    assert leader.expected_win_rate > report.ladder[1].expected_win_rate
    assert [row.seat for row in report.seat_effects] == [0, 1, 2, 3]
    assert sum(row.effect for row in report.seat_effects) == pytest.approx(0.0, abs=1e-8)
    assert len(report.head_to_head) == 12
    won = _cell(report, "A", "B")
    assert won.share == 1.0
    assert won.tables == 4
    missed = _cell(report, "B", "C")
    assert missed.tables == 0
    assert missed.share is None
    assert missed.interval is None


def test_a_rare_head_to_head_interval_is_unavailable() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    specs = plan.entrants
    games: list[LeagueGame] = []
    outcomes: list[CompletedGame] = []
    for block in range(20):
        game = LeagueGame(
            game_id=f"c0-b{block}-r0",
            pairing_key=f"pair-{block}",
            seed=200_000 + block,
            cycle=0,
            block=block,
            rotation=0,
            entrants=specs,
            map_policy="corpus",
            rules=GameRules(),
        )
        games.append(game)
        outcomes.append(finish(game, "B" if block == 0 else "A", source))
    report = report_for(plan, games, outcomes, n_replicates=40)
    rare = _cell(report, "B", "C")
    assert rare.wins == 1
    assert rare.tables == 1
    assert rare.share == 1.0
    assert rare.interval is None
    assert rare.replicates_excluded * 100 > report.provenance.bootstrap_replicates
    neither = _cell(report, "C", "D")
    assert neither.share is None
    assert neither.interval is None
    text = format_league_report(report)
    assert "100.0% (interval unavailable)" in text
    assert "| C | " in text
    assert "unavailable" in text


def test_a_clean_league_is_valid_and_one_percent_drops_stay_valid() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    games, outcomes = played(plan, source)
    retried = (failure(games[0], 1),)
    report = report_for(plan, games, outcomes, retried)
    assert report.attrition.valid is True
    assert report.attrition.terminal_failures == 0
    assert report.attrition.dropped == 0
    assert report.attrition.missing == 0
    assert report.attrition.drop_rate == 0.0
    assert report.warnings == ()
    assert "Valid for a rating." in format_league_report(report)

    wide = league("A", "B", "C", "D", cycles=25)
    wide_games = schedule(wide)
    kept = tuple(finish(game, "A", source) for game in wide_games[1:])
    boundary = report_for(wide, wide_games, (abandon(wide_games[0], source), *kept), n_replicates=4)
    assert boundary.attrition.scheduled == 100
    assert boundary.attrition.dropped == 1
    assert boundary.attrition.drop_rate == pytest.approx(0.01)
    assert boundary.attrition.valid is True
    two = report_for(
        wide,
        wide_games,
        (abandon(wide_games[0], source), abandon(wide_games[1], source), *kept[1:]),
        n_replicates=4,
    )
    assert two.attrition.dropped == 2
    assert two.attrition.valid is False
    assert "dropped games exceed 1% of the schedule" in two.warnings
    assert "Not valid for a rating." in format_league_report(two)


def test_too_many_drops_or_a_terminal_failure_invalidate_the_league() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    games, outcomes = played(plan, source)
    dropped = report_for(plan, games, (abandon(games[0], source), *outcomes[1:]))
    assert dropped.attrition.completed == 3
    assert dropped.attrition.dropped == 1
    assert dropped.attrition.drop_rate == pytest.approx(0.25)
    assert dropped.attrition.valid is False
    assert dropped.attrition.scheduled == dropped.attrition.completed + dropped.attrition.dropped

    missing = report_for(
        plan,
        games,
        outcomes[1:],
        (failure(games[0], 1), failure(games[0], 2)),
    )
    assert missing.attrition.terminal_failures == 1
    assert missing.attrition.missing == 1
    assert missing.attrition.valid is False
    assert "games failed on both attempts" in missing.warnings[1]
    assert "Not valid for a rating." in format_league_report(missing)

    unfinished = report_for(plan, games, outcomes[1:])
    assert unfinished.attrition.terminal_failures == 0
    assert unfinished.attrition.missing == 1
    assert unfinished.attrition.valid is False


def test_behavior_profiles_split_wins_and_resample_blocks() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    games = schedule(plan)
    outcomes = tuple(
        finish(
            game,
            "A",
            source,
            settlements={"A": game.rotation},
            turns=10 * (game.rotation + 1),
        )
        for game in games
    )
    report = report_for(plan, games, outcomes)
    alpha = _behavior(report, "A")
    beta = _behavior(report, "B")
    assert alpha.wins.games == 4
    assert alpha.losses.games == 0
    assert beta.wins.games == 0
    assert beta.losses.games == 4
    settlements = _mean(alpha, "wins", "settlements")
    assert settlements.mean == pytest.approx(1.5)
    assert settlements.interval is not None
    assert settlements.interval.lower == pytest.approx(1.5)
    assert settlements.interval.upper == pytest.approx(1.5)
    assert settlements.replicates_excluded == 0
    turns = alpha.turns_in_won_games
    assert turns.mean == pytest.approx(25.0)
    assert turns.interval is not None
    assert turns.interval.lower == pytest.approx(25.0)
    assert turns.interval.upper == pytest.approx(25.0)
    assert _mean(alpha, "wins", "first_build_settlement").mean == pytest.approx(1.0)
    assert _mean(beta, "losses", "settlements").mean == pytest.approx(0.0)
    assert beta.turns_in_won_games.mean is None
    assert beta.turns_in_won_games.interval is None
    text = format_league_report(report)
    assert "Wins (0 games):" in text
    assert "- no games" in text
    assert "Turns in won games: unavailable" in text
    assert "settlements: 1.50 (95% 1.50 to 1.50)" in text
    assert "Turns in won games: 25.00 (95% 25.00 to 25.00)" in text

    spread = league("A", "B", "C", "D", cycles=4)
    spread_games = schedule(spread)
    spread_outcomes = tuple(
        finish(game, "A", source, settlements={"A": game.cycle}) for game in spread_games
    )
    varied = report_for(spread, spread_games, spread_outcomes, n_replicates=80)
    other = report_for(spread, spread_games, spread_outcomes, n_replicates=80, seed=1)
    estimate = _mean(_behavior(varied, "A"), "wins", "settlements")
    mean = estimate.mean
    assert mean is not None
    assert mean == pytest.approx(1.5)
    assert estimate.interval is not None
    assert estimate.replicates_excluded == 0
    assert estimate.interval.lower < mean < estimate.interval.upper
    again = _mean(_behavior(other, "A"), "wins", "settlements")
    assert again.interval is not None
    assert (again.interval.lower, again.interval.upper) != (
        estimate.interval.lower,
        estimate.interval.upper,
    )
    repeated = report_for(spread, spread_games, spread_outcomes, n_replicates=80)
    assert format_league_report(varied) == format_league_report(repeated)
    assert league_report_to_json(varied) == league_report_to_json(repeated)


def test_provenance_records_the_plan_hash_and_source() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    games, outcomes = played(plan, source)
    report = report_for(plan, games, outcomes, n_replicates=4)
    canonical = json.dumps(plan.to_json(), sort_keys=True, separators=(",", ":"))
    assert canonical_plan_json(plan) == canonical
    assert plan_hash(plan) == hashlib.sha256(canonical.encode()).hexdigest()
    assert report.provenance.plan_hash == plan_hash(plan)
    assert report.provenance.name == "league"
    assert report.provenance.source_commit == COMMIT
    assert report.provenance.source_dirty is False
    assert report.provenance.source_dirty_diff_hash is None
    assert report.provenance.penalty_sd == 2.0
    assert report.provenance.bootstrap_replicates == 4
    assert report.provenance.bootstrap_seed == 0
    dirty = report_for(plan, games, outcomes, source=provenance(dirty=True), n_replicates=4)
    assert dirty.provenance.source_dirty is True
    assert dirty.provenance.source_dirty_diff_hash == "d" * 64
    assert plan_hash(league("A", "B", "C", "D", cycles=2)) != plan_hash(plan)


def test_json_and_markdown_agree_and_regenerate() -> None:
    plan = league("A", "B", "C", "D")
    source = provenance()
    games, outcomes = played(plan, source)
    report = report_for(plan, games, outcomes)
    text = format_league_report(report)
    payload = league_report_to_json(report)
    rendered = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    assert rendered.endswith("\n")
    assert json.loads(rendered) == payload
    _assert_sorted(json.loads(rendered))
    assert payload["schema"] == 1
    assert payload["provenance"]["plan_hash"] in text  # type: ignore[index]
    assert "Valid for a rating." in text
    ladder = payload["ladder"]
    assert isinstance(ladder, list)
    names: list[str] = []
    for row in ladder:
        assert isinstance(row, dict)
        name = row["name"]
        display = row["display"]
        interval = row["interval"]
        rate = row["expected_win_rate"]
        assert isinstance(name, str)
        assert isinstance(display, float)
        assert isinstance(interval, dict)
        assert isinstance(rate, float)
        lower = interval["lower"]
        upper = interval["upper"]
        assert isinstance(lower, float)
        assert isinstance(upper, float)
        names.append(name)
        assert (
            f"| {name} | {display:.1f} | {lower:.1f} to {upper:.1f} | {rate * 100:.1f}% |" in text
        )
    behavior = payload["behavior"]
    assert isinstance(behavior, list)
    leader = behavior[0]
    assert isinstance(leader, dict)
    wins = leader["wins"]
    assert isinstance(wins, dict)
    means = wins["means"]
    assert isinstance(means, list)
    assert [item[0] for item in means] == list(_BEHAVIOR_FIELDS)
    settlements = means[0][1]
    assert isinstance(settlements, dict)
    mean = settlements["mean"]
    band = settlements["interval"]
    assert isinstance(mean, float)
    assert isinstance(band, dict)
    assert isinstance(band["lower"], float)
    assert isinstance(band["upper"], float)
    assert f"{mean:.2f} (95% {band['lower']:.2f} to {band['upper']:.2f})" in text
    positions = [text.index(f"| {name} |") for name in names]
    assert positions == sorted(positions)

    again = report_for(plan, games, tuple(reversed(outcomes)))
    assert format_league_report(again) == text
    assert json.dumps(league_report_to_json(again), sort_keys=True, indent=2) + "\n" == rendered


def _assert_sorted(value: object) -> None:
    if isinstance(value, dict):
        assert list(value) == sorted(value)
        for item in value.values():
            _assert_sorted(item)
    elif isinstance(value, list):
        for item in value:
            _assert_sorted(item)
