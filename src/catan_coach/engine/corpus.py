"""Generate a Corpus of labelled Observations from self-play."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from catanatron import Color, Game
from catanatron.game import TURNS_LIMIT
from catanatron.players.value import ValueFunctionPlayer

from catan_coach.domain.corpus import (
    DEFAULT_VALIDATION_FRACTION,
    Corpus,
    CorpusSummary,
    Split,
    split_for_game,
)
from catan_coach.engine.features import feature_vector

COLORS = (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)
_GAMES_DIR = "games"
_DROPPED_DIR = "dropped"


@dataclass(frozen=True, slots=True)
class _Job:
    game_id: int
    ply_stride: int
    max_turns: int
    output_dir: str
    seed: int
    validation_fraction: float


def generate_corpus(
    output_dir: Path | str,
    *,
    n_games: int,
    ply_stride: int = 12,
    seed: int = 0,
    workers: int = 1,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
    max_turns: int | None = None,
) -> CorpusSummary:
    if n_games < 1:
        raise ValueError("n_games must be at least 1")
    if ply_stride < 1:
        raise ValueError("ply_stride must be at least 1")
    if workers < 1:
        raise ValueError("workers must be at least 1")
    limit = TURNS_LIMIT if max_turns is None else max_turns
    if limit < 0:
        raise ValueError("max_turns must be non-negative")

    root = Path(output_dir)
    (root / _GAMES_DIR).mkdir(parents=True, exist_ok=True)
    (root / _DROPPED_DIR).mkdir(parents=True, exist_ok=True)

    finished = {int(path.stem) for path in (root / _GAMES_DIR).glob("*.parquet")}
    already_dropped = {
        int(path.name) for path in (root / _DROPPED_DIR).iterdir() if path.name.isdigit()
    }
    jobs = [
        _Job(
            game_id=game_id,
            ply_stride=ply_stride,
            max_turns=limit,
            output_dir=str(root),
            seed=seed,
            validation_fraction=validation_fraction,
        )
        for game_id in range(seed, seed + n_games)
        if game_id not in finished and game_id not in already_dropped
    ]
    _run(jobs, workers)
    return _summarize(root)


def read_corpus(output_dir: Path | str) -> Corpus:
    files = sorted((Path(output_dir) / _GAMES_DIR).glob("*.parquet"))
    if not files:
        raise ValueError(f"no Corpus games in {output_dir}")
    frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
    observations = np.asarray(frame["observation"].to_list(), dtype=np.float64)
    return Corpus(
        game_ids=frame["game_id"].to_numpy(dtype=np.int64),
        plies=frame["ply"].to_numpy(dtype=np.int32),
        seats=np.asarray(frame["seat"].to_numpy(), dtype=np.str_),
        splits=np.asarray(frame["split"].to_numpy(), dtype=np.str_),
        won=frame["won"].to_numpy(dtype=np.float64),
        observations=observations,
    )


def _run(jobs: list[_Job], workers: int) -> None:
    if not jobs:
        return
    if workers == 1:
        for job in jobs:
            _play_and_persist(job)
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_play_and_persist, jobs))


def _play_and_persist(job: _Job) -> None:
    sampled = _sample_game(job.game_id, job.ply_stride, job.max_turns)
    root = Path(job.output_dir)
    if sampled is None:
        (root / _DROPPED_DIR / f"{job.game_id:05d}").write_text("")
        return
    winner, samples = sampled
    split = split_for_game(job.game_id, seed=job.seed, validation_fraction=job.validation_fraction)
    dest = root / _GAMES_DIR / f"{job.game_id:05d}.parquet"
    tmp = dest.with_name(f"{dest.name}.tmp")
    _rows_to_frame(job.game_id, split, winner, samples).to_parquet(tmp)
    tmp.replace(dest)


def _sample_game(
    game_id: int, ply_stride: int, max_turns: int
) -> tuple[str, list[tuple[int, str, np.ndarray]]] | None:
    game = Game([ValueFunctionPlayer(color) for color in COLORS], seed=game_id)
    samples: list[tuple[int, str, np.ndarray]] = []
    ply = 0
    while game.winning_color() is None and game.state.num_turns < max_turns:
        if ply % ply_stride == 0:
            for color in game.state.colors:
                samples.append((ply, color.name, feature_vector(game, color)))
        game.play_tick()
        ply += 1
    winner = game.winning_color()
    if winner is None:
        return None
    return winner.name, samples


def _rows_to_frame(
    game_id: int,
    split: Split,
    winner: str,
    samples: list[tuple[int, str, np.ndarray]],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [game_id] * len(samples),
            "ply": [ply for ply, _, _ in samples],
            "seat": [seat for _, seat, _ in samples],
            "split": [split] * len(samples),
            "won": [float(seat == winner) for _, seat, _ in samples],
            "observation": [observation.tolist() for _, _, observation in samples],
        }
    )


def _summarize(root: Path) -> CorpusSummary:
    dropped_dir = root / _DROPPED_DIR
    dropped = (
        len([path for path in dropped_dir.iterdir() if path.name.isdigit()])
        if dropped_dir.exists()
        else 0
    )
    files = list((root / _GAMES_DIR).glob("*.parquet"))
    empty_rates = {color.name: 0.0 for color in COLORS}
    if not files:
        return CorpusSummary(
            games_played=0,
            games_dropped=dropped,
            rows_written=0,
            win_rate_by_seat=empty_rates,
        )
    corpus = read_corpus(root)
    winners: dict[int, str] = {}
    for game_id, seat, won in zip(corpus.game_ids, corpus.seats, corpus.won, strict=True):
        if won:
            winners[int(game_id)] = str(seat)
    played = len(winners)
    win_rate = dict(empty_rates)
    if played:
        for winner in winners.values():
            win_rate[winner] += 1.0 / played
    return CorpusSummary(
        games_played=played,
        games_dropped=dropped,
        rows_written=len(corpus.game_ids),
        win_rate_by_seat=win_rate,
    )
