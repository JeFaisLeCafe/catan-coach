"""End-to-end Corpus generation against the real engine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catan_coach.engine.corpus import generate_corpus, read_corpus  # noqa: E402

SEATS = frozenset({"RED", "BLUE", "WHITE", "ORANGE"})
OPENING_ONLY = 10_000


def test_a_small_run_records_every_seat_at_each_sampled_ply(tmp_path: Path) -> None:
    summary = generate_corpus(
        tmp_path,
        n_games=2,
        ply_stride=OPENING_ONLY,
        seed=0,
        workers=1,
    )
    corpus = read_corpus(tmp_path)

    assert summary.games_played == 2
    assert summary.games_dropped == 0
    assert summary.rows_written == 8
    assert set(summary.win_rate_by_seat) == SEATS
    assert sum(summary.win_rate_by_seat.values()) == pytest.approx(1.0)

    assert corpus.observations.shape == (8, corpus.observations.shape[1])
    assert corpus.observations.shape[1] > 0
    assert set(corpus.game_ids.tolist()) == {0, 1}
    assert set(corpus.seats) == SEATS
    assert set(corpus.plies.tolist()) == {0}

    for game_id in (0, 1):
        rows = corpus.game_ids == game_id
        assert int(rows.sum()) == 4
        assert set(corpus.seats[rows]) == SEATS
        assert len(set(corpus.splits[rows])) == 1
        assert int(corpus.won[rows].sum()) == 1


def test_a_larger_stride_samples_fewer_positions(tmp_path: Path) -> None:
    dense = tmp_path / "dense"
    sparse = tmp_path / "sparse"
    generate_corpus(dense, n_games=1, ply_stride=1, seed=4, workers=1)
    generate_corpus(sparse, n_games=1, ply_stride=OPENING_ONLY, seed=4, workers=1)

    assert read_corpus(dense).observations.shape[0] > read_corpus(sparse).observations.shape[0]
    assert read_corpus(sparse).observations.shape[0] == 4


def test_games_that_do_not_finish_are_dropped_and_counted(tmp_path: Path) -> None:
    summary = generate_corpus(
        tmp_path,
        n_games=2,
        ply_stride=1,
        seed=0,
        workers=1,
        max_turns=0,
    )

    assert summary.games_played == 0
    assert summary.games_dropped == 2
    assert summary.rows_written == 0
    with pytest.raises(ValueError, match="no Corpus"):
        read_corpus(tmp_path)


def test_an_interrupted_run_resumes_without_replaying_finished_games(tmp_path: Path) -> None:
    generate_corpus(tmp_path, n_games=1, ply_stride=OPENING_ONLY, seed=0, workers=1)
    first_game = tmp_path / "games" / "00000.parquet"
    stamp = first_game.stat().st_mtime_ns

    summary = generate_corpus(tmp_path, n_games=2, ply_stride=OPENING_ONLY, seed=0, workers=1)

    assert first_game.stat().st_mtime_ns == stamp
    assert summary.games_played == 2
    assert set(read_corpus(tmp_path).game_ids.tolist()) == {0, 1}


def test_a_crash_mid_run_keeps_games_already_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import catan_coach.engine.corpus as corpus_mod

    calls = {"n": 0}
    real = corpus_mod._sample_game

    def flaky(
        game_id: int, ply_stride: int, max_turns: int
    ) -> tuple[str, list[tuple[int, str, np.ndarray]]] | None:
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("interrupted")
        return real(game_id, ply_stride, max_turns)

    monkeypatch.setattr(corpus_mod, "_sample_game", flaky)
    with pytest.raises(RuntimeError, match="interrupted"):
        generate_corpus(tmp_path, n_games=2, ply_stride=OPENING_ONLY, seed=0, workers=1)

    assert (tmp_path / "games" / "00000.parquet").is_file()
    assert not (tmp_path / "games" / "00001.parquet").is_file()


def test_parallel_workers_write_each_game_once(tmp_path: Path) -> None:
    summary = generate_corpus(
        tmp_path,
        n_games=2,
        ply_stride=OPENING_ONLY,
        seed=5,
        workers=2,
    )
    corpus = read_corpus(tmp_path)

    assert summary.games_played == 2
    assert len(corpus.game_ids) == 8
    assert set(corpus.game_ids.tolist()) == {5, 6}
    assert len(np.unique(corpus.game_ids)) == 2
