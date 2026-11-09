from __future__ import annotations

import json
from pathlib import Path

import pytest

from catan_coach.domain.strength import (
    SEATS,
    GameRecord,
    attrition_invalidates,
    candidate_seat_for_seed,
    clears_fair_share,
    falls_below_fair_share,
    format_strength_report,
    game_record_from_json,
    game_record_to_json,
    strength_conclusion,
    strength_report,
    wilson_interval,
)
from catan_coach.strength_audit import main, report_directory


@pytest.mark.parametrize(
    ("wins", "games", "lower", "upper"),
    [
        (0, 1, 0.0, 0.793450685623),
        (1, 1, 0.206549314377, 1.0),
        (0, 4, 0.0, 0.489890836455),
        (1, 4, 0.045587260810, 0.699358157418),
        (500, 2000, 0.231514134425, 0.269444389216),
    ],
)
def test_wilson_interval_matches_hand_computed_bounds(
    wins: int, games: int, lower: float, upper: float
) -> None:
    interval = wilson_interval(wins, games)

    assert interval.lower == pytest.approx(lower, abs=1e-12)
    assert interval.upper == pytest.approx(upper, abs=1e-12)


def test_wilson_interval_rejects_an_empty_sample() -> None:
    with pytest.raises(ValueError, match="at least one game"):
        wilson_interval(0, 0)


def test_unresolved_games_count_as_losses_and_stay_out_of_the_completed_rate() -> None:
    report = strength_report(
        (
            GameRecord(20_000, "RED", "RED", 40, (8, 6)),
            GameRecord(20_001, "BLUE", "WHITE", 40, (8, 6)),
            GameRecord(20_002, "WHITE", None, 1_000, (9, 9)),
        )
    )

    assert report.wins == 1
    assert report.games_completed == 2
    assert report.unfinished == 1
    assert report.win_rate == pytest.approx(0.5)
    assert report.interval is not None
    assert report.interval.lower == pytest.approx(0.094531205734, abs=1e-12)
    assert report.interval.upper == pytest.approx(0.905468794266, abs=1e-12)
    assert report.attrition_as_losses.wins == 1
    assert report.attrition_as_losses.games == 3
    assert report.attrition_as_losses.win_rate == pytest.approx(1 / 3)
    assert report.attrition_as_losses.interval is not None
    assert report.attrition_as_losses.interval.lower == pytest.approx(0.061491944720, abs=1e-12)
    assert report.attrition_as_wins.wins == 2
    assert report.attrition_as_wins.games == 3
    assert report.attrition_as_wins.interval is not None
    assert report.attrition_as_wins.interval.lower == pytest.approx(0.207659600802, abs=1e-12)
    assert report.attrition_as_wins.interval.upper == pytest.approx(0.938508055280, abs=1e-12)

    by_seat = {seat.seat: seat for seat in report.by_seat}
    assert by_seat["RED"].wins == 1
    assert by_seat["RED"].games_completed == 1
    assert by_seat["RED"].interval is not None
    assert by_seat["RED"].interval.lower == pytest.approx(0.206549314377, abs=1e-12)
    assert by_seat["BLUE"].wins == 0
    assert by_seat["BLUE"].games_completed == 1
    assert by_seat["BLUE"].interval is not None
    assert by_seat["BLUE"].interval.upper == pytest.approx(0.793450685623, abs=1e-12)
    assert by_seat["WHITE"].games_completed == 0
    assert by_seat["WHITE"].unfinished == 1
    assert by_seat["WHITE"].win_rate is None
    assert by_seat["ORANGE"].games_completed == 0
    assert by_seat["ORANGE"].unfinished == 0


def test_a_completed_lead_does_not_clear_fair_share_when_attrition_does_not() -> None:
    report = strength_report(_games(wins=540, games=2_000, unfinished=8))

    assert report.games_completed == 2_000
    assert report.interval is not None
    assert report.interval.lower == pytest.approx(0.250997556188, abs=1e-12)
    assert report.attrition_as_losses.games == 2_008
    assert report.attrition_as_losses.interval is not None
    assert report.attrition_as_losses.interval.lower == pytest.approx(0.249985246737, abs=1e-12)
    assert clears_fair_share(report) is False
    assert strength_conclusion(report) == "inconclusive"


def test_fair_share_bounds_match_the_preregistered_rule() -> None:
    clears = strength_report(_games(wins=540, games=2_000))
    short = strength_report(_games(wins=462, games=2_000))
    inside = strength_report(_games(wins=500, games=2_000))

    assert clears.interval is not None
    assert clears.interval.lower == pytest.approx(0.250997556188, abs=1e-12)
    assert clears_fair_share(clears) is True
    assert strength_conclusion(clears) == "beats"
    assert short.interval is not None
    assert short.interval.upper == pytest.approx(0.249976679564, abs=1e-12)
    assert falls_below_fair_share(short) is True
    assert strength_conclusion(short) == "loses"
    assert clears_fair_share(inside) is False
    assert falls_below_fair_share(inside) is False
    assert strength_conclusion(inside) == "inconclusive"


def test_more_than_one_percent_unfinished_invalidates_the_conclusion() -> None:
    flooded = strength_report(_games(wins=2_000, games=2_000, unfinished=21))
    on_the_line = strength_report(_games(wins=1_980, games=1_980, unfinished=20))

    assert attrition_invalidates(flooded) is True
    assert strength_conclusion(flooded) == "invalid"
    assert flooded.unfinished / (flooded.games_completed + flooded.unfinished) > 0.01
    assert attrition_invalidates(on_the_line) is False
    assert on_the_line.unfinished / (on_the_line.games_completed + on_the_line.unfinished) == 0.01


def test_a_short_sample_is_exploratory_even_when_every_game_is_a_win() -> None:
    report = strength_report(_games(wins=4, games=4))
    text = format_strength_report(report, extreme_games=0)

    assert clears_fair_share(report) is True
    assert text.startswith("Exploratory result: this is not the preregistered decision.\n")
    assert "Preregistered decision:" not in text
    assert "games 4" in text
    assert "Unfinished: 0" in text
    assert "Extreme dice: 0" in text


def test_two_thousand_completed_games_open_with_the_rate() -> None:
    text = format_strength_report(strength_report(_games(wins=540, games=2_000)), extreme_games=0)

    assert text.startswith("Win rate:")
    assert "games 2000" in text.splitlines()[0]
    assert "Exploratory" not in text
    assert "Preregistered decision: beats." in text


def test_flagged_dice_are_not_removed_from_the_win_rate(tmp_path: Path) -> None:
    flagged = (12,) * 10 + (6,) * 110
    ordinary = (8,) * 36
    _write(tmp_path, GameRecord(20_000, "RED", "RED", 80, flagged))
    _write(tmp_path, GameRecord(20_001, "BLUE", "ORANGE", 80, ordinary))
    _write(tmp_path, GameRecord(20_002, "WHITE", "WHITE", 80, None))

    text = report_directory(tmp_path)

    assert text.startswith("Exploratory result: this is not the preregistered decision.\n")
    assert "Win rate: wins 2  win rate 0.666667  " in text
    assert "games 3" in text
    assert "Extreme dice: 1" in text
    assert "Dice unavailable: 1" in text
    assert "Unfinished: 0" in text


def test_the_candidate_rotates_equally_through_every_seat() -> None:
    seats = [candidate_seat_for_seed(20_000 + offset) for offset in range(2_000)]

    assert seats[:4] == ["RED", "BLUE", "WHITE", "ORANGE"]
    assert {seat: seats.count(seat) for seat in SEATS} == {seat: 500 for seat in SEATS}
    for offset in range(0, 2_000, 4):
        assert set(seats[offset : offset + 4]) == set(SEATS)


def test_a_game_record_round_trips_and_keeps_unavailable_rolls() -> None:
    recorded = GameRecord(20_000, "RED", "BLUE", 77, (8, 12, 2))
    unfinished = GameRecord(20_001, "ORANGE", None, 1_000, None)

    assert game_record_from_json(game_record_to_json(recorded)) == recorded
    assert game_record_from_json(game_record_to_json(unfinished)) == unfinished
    broken = game_record_to_json(unfinished)
    broken["rolls"] = [8]
    broken["rolls_available"] = False
    with pytest.raises(ValueError, match="null"):
        game_record_from_json(broken)


def test_report_only_prints_the_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, GameRecord(20_003, "ORANGE", None, 1_000, (7, 7)))

    code = main(["--out", str(tmp_path), "--report-only"])

    assert code == 0
    captured = capsys.readouterr().out
    assert captured.startswith("Exploratory result: this is not the preregistered decision.\n")
    assert "Unfinished: 1" in captured
    assert "games 0" in captured


def test_a_file_name_must_match_its_seed(tmp_path: Path) -> None:
    path = tmp_path / "20001.json"
    path.write_text(
        json.dumps(game_record_to_json(GameRecord(20_000, "RED", "RED", 1, (6,)))), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=r"20001\.json"):
        report_directory(tmp_path)


def _games(*, wins: int, games: int, unfinished: int = 0) -> tuple[GameRecord, ...]:
    rows = [
        GameRecord(
            20_000 + index,
            SEATS[index % 4],
            SEATS[index % 4] if index < wins else SEATS[(index + 1) % 4],
            10,
            (8,),
        )
        for index in range(games)
    ]
    rows.extend(
        GameRecord(40_000 + index, SEATS[index % 4], None, 1_000, (8,))
        for index in range(unfinished)
    )
    return tuple(rows)


def _write(directory: Path, record: GameRecord) -> None:
    path = directory / f"{record.seed}.json"
    path.write_text(json.dumps(game_record_to_json(record)), encoding="utf-8")
