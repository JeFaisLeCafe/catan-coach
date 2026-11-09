from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.engine

from catanatron.players.value import ValueFunctionPlayer  # noqa: E402

from catan_coach.domain.strength import GameRecord, game_record_to_json  # noqa: E402
from catan_coach.engine.model_player import WinProbabilityPlayer  # noqa: E402
from catan_coach.engine.strength_audit import (  # noqa: E402
    game_record_from_path,
    play_scheduled_game,
    players_for_seat,
)
from catan_coach.models.gbdt import GbdtModel  # noqa: E402
from catan_coach.strength_audit import report_directory  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "model.txt"


def test_the_candidate_searches_four_simulations_without_exploration() -> None:
    players = players_for_seat("BLUE", GbdtModel.load(MODEL))

    assert [type(player) for player in players] == [
        ValueFunctionPlayer,
        WinProbabilityPlayer,
        ValueFunctionPlayer,
        ValueFunctionPlayer,
    ]
    candidate = players[1]
    assert isinstance(candidate, WinProbabilityPlayer)
    assert candidate._explore is False
    assert candidate._search_simulations == 4


def test_a_mismatched_completed_seed_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / "20000.json"
    planted = GameRecord(20_000, "BLUE", "BLUE", 3, (8, 6))
    dest.write_text(json.dumps(game_record_to_json(planted)), encoding="utf-8")

    with pytest.raises(ValueError, match="seat"):
        play_scheduled_game(20_000, tmp_path, model_path=MODEL)


def test_a_tiny_game_round_trips_and_a_rerun_skips_it(tmp_path: Path) -> None:
    dest = play_scheduled_game(
        20_000,
        tmp_path,
        model_path=MODEL,
        vps_to_win=3,
        search_simulations=0,
    )
    record = game_record_from_path(dest)

    assert record.seed == 20_000
    assert record.candidate_seat == "RED"
    assert record.winner_seat in {"RED", "BLUE", "WHITE", "ORANGE"}
    assert record.turn_count > 0
    assert record.rolls is not None
    assert record.rolls
    assert all(2 <= roll <= 12 for roll in record.rolls)
    text = report_directory(tmp_path)
    assert text.startswith("Exploratory result: this is not the preregistered decision.\n")
    assert "Dice unavailable: 0" in text

    contents = dest.read_bytes()
    modified = dest.stat().st_mtime_ns
    again = play_scheduled_game(
        20_000,
        tmp_path,
        model_path=MODEL,
        vps_to_win=3,
        search_simulations=0,
    )

    assert again == dest
    assert dest.stat().st_mtime_ns == modified
    assert dest.read_bytes() == contents
