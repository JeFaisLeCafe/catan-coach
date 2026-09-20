"""Command-line analysis of a saved game at a Ply."""

from __future__ import annotations

from pathlib import Path

import pytest

from catan_coach.cli import format_analysis, main
from catan_coach.domain.analysis import Analysis, RankedAction
from catan_coach.domain.position import Action, Seat


def test_a_missing_game_file_is_a_readable_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    missing = tmp_path / "no-such-game.json"

    code = main([str(missing), "0"])

    captured = capsys.readouterr()
    assert code == 1
    assert "no-such-game.json" in captured.err
    assert "Traceback" not in captured.err


def test_a_forced_action_is_not_presented_as_a_choice() -> None:
    text = format_analysis(
        Analysis(
            seat=Seat("WHITE"),
            ranked=(RankedAction(Action("END_TURN"), 0.31, 0.0),),
        ),
        "constant(1/4)",
        Path("position.png"),
    )
    assert "not a choice" in text
    assert "END_TURN" in text
    assert "WHITE" in text
    assert "constant(1/4)" in text
    assert "Loss" not in text


@pytest.fixture(scope="module")
def saved_game(tmp_path_factory: pytest.TempPathFactory) -> Path:
    pytest.importorskip("catanatron")
    from catanatron import Color, Game
    from catanatron.players.value import ValueFunctionPlayer

    from catan_coach.engine.persist import write_game

    colors = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)
    game = Game([ValueFunctionPlayer(c) for c in colors], seed=7)
    game.play()
    path = tmp_path_factory.mktemp("cli") / "game.json"
    write_game(game, path)
    return path


@pytest.mark.engine
def test_an_out_of_range_ply_names_the_valid_range(
    capsys: pytest.CaptureFixture[str], saved_game: Path
) -> None:
    code = main([str(saved_game), "99999"])

    captured = capsys.readouterr()
    assert code == 1
    assert "valid plies are 0 to" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.engine
def test_the_command_prints_an_analysis_and_writes_a_png(
    capsys: pytest.CaptureFixture[str], saved_game: Path
) -> None:
    code = main([str(saved_game), "0"])

    captured = capsys.readouterr()
    assert code == 0
    assert "vp-share" in captured.out
    assert "Seat" in captured.out
    assert "Win Probability" in captured.out
    assert "Loss" in captured.out
    png = saved_game.with_name("game-ply-0.png")
    assert png.name in captured.out
    assert png.is_file()
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.engine
def test_the_corpus_command_writes_parquet_and_prints_a_summary(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    out = tmp_path / "corpus"
    code = main(
        [
            "corpus",
            "--games",
            "1",
            "--out",
            str(out),
            "--stride",
            "10000",
            "--workers",
            "1",
            "--seed",
            "3",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "Games played: 1" in captured.out
    assert "Games dropped: 0" in captured.out
    assert "Rows written: 4" in captured.out
    assert "Win rate:" in captured.out
    assert "Traceback" not in captured.err
    assert (out / "games").is_dir()
    from catan_coach.engine.corpus import read_corpus

    corpus = read_corpus(out)
    assert corpus.observations.shape[0] == 4
