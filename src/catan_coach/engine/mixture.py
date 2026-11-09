"""Load several Corpora without holding every Observation in memory."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from catan_coach.domain.corpus import TRAIN, VALIDATION

_GAMES = "games"


@dataclass(frozen=True, slots=True)
class MaterializedMixture:
    train_features: np.ndarray
    train_won: np.ndarray
    validation_features: np.ndarray
    validation_won: np.ndarray
    n_games: int
    n_players: int


@dataclass(frozen=True, slots=True)
class ValidationGame:
    """One held-out game. The caller predicts, then drops `features`."""

    corpus_index: int
    game_id: int
    features: np.ndarray
    won: np.ndarray


def iter_validation_games(paths: Sequence[Path | str]) -> Iterator[ValidationGame]:
    """Yield each validation game's Observations, one game at a time.

    Train games are skipped before their Observations are read. Two Corpora
    keep distinct games even when they reuse a game id.
    """
    files = _corpus_files(paths)
    for index, (corpus_index, path) in enumerate(files, start=1):
        split = pd.read_parquet(path, columns=["split"])
        if not bool((split["split"] == VALIDATION).any()):
            if index % 500 == 0:
                print(f"Read {index} of {len(files)} games", flush=True)
            continue
        frame = pd.read_parquet(path, columns=["game_id", "split", "won", "observation"])
        part = frame.loc[frame["split"] == VALIDATION]
        for _game_id, rows in part.groupby("game_id", sort=False):
            yield ValidationGame(
                corpus_index=corpus_index,
                game_id=int(rows["game_id"].to_numpy(dtype=np.int64)[0]),
                features=np.asarray(rows["observation"].to_list(), dtype=np.float32),
                won=rows["won"].to_numpy(dtype=np.float64),
            )
        if index % 500 == 0:
            print(f"Read {index} of {len(files)} games", flush=True)


def player_count(paths: Sequence[Path | str]) -> int:
    frame = pd.read_parquet(_corpus_files(paths)[0][1], columns=["seat"])
    count = int(frame["seat"].nunique())
    if count < 2:
        raise ValueError("Corpus needs at least two Seats")
    return count


def materialize_mixture(paths: Sequence[Path | str], work: Path) -> MaterializedMixture:
    """Copy train and validation rows into on-disk arrays.

    Game ids are not renumbered: each row already carries the split it was
    written with, and a game is never split across train and validation.
    """
    files = _game_files(paths)
    if not files:
        raise ValueError("need at least one Corpus")
    train_rows, validation_rows, games, players, width = _measure(files)
    if train_rows == 0:
        raise ValueError("Corpus has no train games")
    if validation_rows == 0:
        raise ValueError("Corpus has no validation games")
    work.mkdir(parents=True, exist_ok=True)
    train_features = _open(work / "train-features.npy", train_rows, width)
    validation_features = _open(work / "validation-features.npy", validation_rows, width)
    train_won = np.lib.format.open_memmap(
        work / "train-won.npy", mode="w+", dtype=np.float32, shape=(train_rows,)
    )
    validation_won = np.lib.format.open_memmap(
        work / "validation-won.npy", mode="w+", dtype=np.float32, shape=(validation_rows,)
    )
    _fill(files, train_features, train_won, validation_features, validation_won)
    return MaterializedMixture(
        train_features=train_features,
        train_won=train_won,
        validation_features=validation_features,
        validation_won=validation_won,
        n_games=games,
        n_players=players,
    )


def _corpus_files(paths: Sequence[Path | str]) -> list[tuple[int, Path]]:
    from catan_coach.engine.corpus import require_trainable_corpus

    files: list[tuple[int, Path]] = []
    for corpus_index, path in enumerate(paths):
        games = sorted((Path(path) / _GAMES).glob("*.parquet"))
        if not games:
            raise ValueError(f"no Corpus games in {path}")
        require_trainable_corpus(path)
        files.extend((corpus_index, game) for game in games)
    return files


def _game_files(paths: Sequence[Path | str]) -> list[Path]:
    return [path for _, path in _corpus_files(paths)]


def _measure(files: Sequence[Path]) -> tuple[int, int, int, int, int]:
    train_rows = 0
    validation_rows = 0
    games: set[tuple[int, int]] = set()
    seats: set[str] = set()
    width = 0
    for source, path in enumerate(files):
        frame = pd.read_parquet(path, columns=["game_id", "split", "seat"])
        if width == 0:
            sample = pd.read_parquet(path, columns=["observation"])
            width = len(sample["observation"].iloc[0])
        train = frame["split"] == TRAIN
        validation = frame["split"] == VALIDATION
        train_rows += int(train.sum())
        validation_rows += int(validation.sum())
        for game_id in frame.loc[train | validation, "game_id"].unique():
            games.add((source, int(game_id)))
        seats.update(str(seat) for seat in frame["seat"].unique())
        if (source + 1) % 500 == 0:
            print(f"Measured {source + 1} of {len(files)} games", flush=True)
    return train_rows, validation_rows, len(games), len(seats), width


def _fill(
    files: Sequence[Path],
    train_features: np.ndarray,
    train_won: np.ndarray,
    validation_features: np.ndarray,
    validation_won: np.ndarray,
) -> None:
    train_at = 0
    validation_at = 0
    for index, path in enumerate(files, start=1):
        frame = pd.read_parquet(path, columns=["split", "won", "observation"])
        train_at = _write(frame, TRAIN, train_features, train_won, train_at)
        validation_at = _write(
            frame, VALIDATION, validation_features, validation_won, validation_at
        )
        if index % 500 == 0:
            _flush(train_features)
            _flush(validation_features)
            print(f"Copied {index} of {len(files)} games", flush=True)
    _flush(train_features)
    _flush(validation_features)
    _flush(train_won)
    _flush(validation_won)


def _write(
    frame: pd.DataFrame,
    split: str,
    features: np.ndarray,
    won: np.ndarray,
    cursor: int,
) -> int:
    part = frame.loc[frame["split"] == split]
    if part.empty:
        return cursor
    block = np.asarray(part["observation"].to_list(), dtype=np.float32)
    count = int(block.shape[0])
    features[cursor : cursor + count] = block
    won[cursor : cursor + count] = part["won"].to_numpy(dtype=np.float32)
    return cursor + count


def _flush(array: np.ndarray) -> None:
    flush = getattr(array, "flush", None)
    if callable(flush):
        flush()


def _open(path: Path, rows: int, width: int) -> np.ndarray:
    return np.lib.format.open_memmap(path, mode="w+", dtype=np.float32, shape=(rows, width))
