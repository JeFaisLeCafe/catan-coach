"""Command-line analysis of a saved game at a Ply."""

from __future__ import annotations

from pathlib import Path

import pytest

from catan_coach.cli import format_analysis, main
from catan_coach.domain.analysis import Analysis, Contribution, RankedAction
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


def test_loss_is_shown_in_percentage_points_and_a_near_tie_is_named() -> None:
    text = format_analysis(
        Analysis(
            seat=Seat("BLUE"),
            ranked=(
                RankedAction(
                    Action("BUILD_SETTLEMENT 3"),
                    0.410,
                    0.0,
                    (Contribution("hand", 0.08),),
                ),
                RankedAction(
                    Action("BUILD_SETTLEMENT 7"),
                    0.406,
                    0.004,
                    (Contribution("road", 0.03),),
                ),
            ),
        ),
        "gbdt",
        Path("board.png"),
    )
    assert "0.4" in text  # 0.4 percentage points, not a raw 0.004
    assert "near-tie" in text.lower()
    assert "hand" in text
    assert "BUILD_SETTLEMENT 3" in text


def test_a_wide_gap_is_not_called_a_near_tie() -> None:
    text = format_analysis(
        Analysis(
            seat=Seat("BLUE"),
            ranked=(
                RankedAction(Action("BUILD_CITY 3"), 0.50, 0.0),
                RankedAction(Action("END_TURN"), 0.35, 0.15),
            ),
        ),
        "gbdt",
        Path("board.png"),
    )
    assert "15" in text
    assert "near-tie" not in text.lower()


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
def test_analyze_falls_back_to_vp_share_when_no_trained_model_is_present(
    capsys: pytest.CaptureFixture[str], saved_game: Path
) -> None:
    code = main([str(saved_game), "0", "--model", str(saved_game.parent / "absent.txt")])

    captured = capsys.readouterr()
    assert code == 0
    assert "No trained model" in captured.err
    assert "vp-share" in captured.out
    assert "Traceback" not in captured.err


@pytest.mark.engine
def test_a_baseline_can_be_selected_explicitly(
    capsys: pytest.CaptureFixture[str], saved_game: Path
) -> None:
    code = main([str(saved_game), "0", "--baseline", "constant"])

    captured = capsys.readouterr()
    assert code == 0
    assert "constant(1/4)" in captured.out
    assert "vp-share" not in captured.out


@pytest.mark.engine
def test_analyze_with_a_trained_model_prints_player_reasons(
    capsys: pytest.CaptureFixture[str], saved_game: Path, tmp_path: Path
) -> None:
    from catan_coach.domain.reasons import PLAYER_LABELS
    from catan_coach.engine.corpus import generate_corpus

    corpus_dir = tmp_path / "corpus"
    model_path = tmp_path / "model.txt"
    generate_corpus(corpus_dir, n_games=2, ply_stride=10_000, seed=0, workers=1)
    main(["train", "--corpus", str(corpus_dir), "--out", str(model_path), "--seed", "0"])
    capsys.readouterr()

    code = main([str(saved_game), "0", "--model", str(model_path)])
    captured = capsys.readouterr()

    assert code == 0
    assert "gbdt" in captured.out
    assert any(label in captured.out for label in PLAYER_LABELS)
    assert "Traceback" not in captured.err


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


@pytest.mark.engine
def test_the_train_command_writes_a_model_and_reports_baselines(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from catan_coach.engine.corpus import generate_corpus

    corpus_dir = tmp_path / "corpus"
    model_path = tmp_path / "model.txt"
    generate_corpus(corpus_dir, n_games=2, ply_stride=10_000, seed=0, workers=1)

    code = main(["train", "--corpus", str(corpus_dir), "--out", str(model_path), "--seed", "0"])
    captured = capsys.readouterr()

    assert model_path.is_file()
    assert "Wrote" in captured.out
    assert str(corpus_dir) in captured.out
    assert "games: 2" in captured.out
    assert "constant(1/4)" in captured.out
    assert "vp-share" in captured.out
    assert "brier" in captured.out.lower()
    assert "ece" in captured.out.lower()
    assert "does not beat" in captured.out or "beats" in captured.out
    assert code in (0, 1)
    assert "Traceback" not in captured.err

    capsys.readouterr()
    report_code = main(["report", "--corpus", str(corpus_dir), "--model", str(model_path)])
    report = capsys.readouterr()
    assert report_code == code
    assert "constant(1/4)" in report.out


def test_a_missing_trained_model_is_a_readable_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code = main(["report", "--corpus", str(tmp_path), "--model", str(tmp_path / "missing.txt")])

    captured = capsys.readouterr()
    assert code == 1
    assert "missing.txt" in captured.err
    assert "Traceback" not in captured.err
