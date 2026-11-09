"""Generate a Corpus of labelled Observations from self-play."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Sequence
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
from catan_coach.domain.manifest import (
    MANIFEST_NAME,
    CorpusManifest,
    PlayerKind,
    training_refusal,
)
from catan_coach.engine.board import corpus_map
from catan_coach.engine.features import feature_vector
from catan_coach.engine.model_player import (
    CORPUS_SEARCH_SIMULATIONS,
    WinProbabilityPlayer,
)
from catan_coach.models.gbdt import GbdtModel

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
    players: str
    model_path: str


def generate_corpus(
    output_dir: Path | str,
    *,
    n_games: int,
    ply_stride: int = 12,
    seed: int = 0,
    workers: int = 1,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
    max_turns: int | None = None,
    players: str = "value",
    model_path: Path | str | None = None,
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
    if players not in {"value", "model"}:
        raise ValueError("players must be 'value' or 'model'")
    if players == "model" and (model_path is None or not Path(model_path).is_file()):
        raise ValueError("model self-play needs a saved model file")
    model_file = "" if model_path is None else str(model_path)
    kind: PlayerKind = "model" if players == "model" else "value"
    revision, dirty = _git_identity()
    invocation = CorpusManifest(
        player_kind=kind,
        model_sha256=_file_sha256(Path(model_file)) if kind == "model" else "",
        search_simulations=CORPUS_SEARCH_SIMULATIONS if kind == "model" else 0,
        exploration=kind == "model",
        ply_stride=ply_stride,
        base_seed=seed,
        requested_games=n_games,
        validation_fraction=validation_fraction,
        max_turns=limit,
        git_revision=revision,
        dirty_tree=dirty,
        games_finished=0,
        games_dropped=0,
        drop_rate=0.0,
    )

    root = Path(output_dir)
    (root / _GAMES_DIR).mkdir(parents=True, exist_ok=True)
    (root / _DROPPED_DIR).mkdir(parents=True, exist_ok=True)
    _bind_manifest(root, invocation)

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
            players=players,
            model_path=model_file,
        )
        for game_id in range(seed, seed + n_games)
        if game_id not in finished and game_id not in already_dropped
    ]
    _run(jobs, workers)
    summary = _summarize(root)
    _write_manifest(root, invocation.with_outcomes(summary.games_played, summary.games_dropped))
    return summary


def read_corpora(paths: Sequence[Path | str]) -> Corpus:
    from catan_coach.domain.corpus import combine_corpora

    if not paths:
        raise ValueError("need at least one Corpus")
    return combine_corpora(tuple(read_corpus(path) for path in paths))


def read_corpus(output_dir: Path | str) -> Corpus:
    root = Path(output_dir)
    files = sorted((root / _GAMES_DIR).glob("*.parquet"))
    if not files:
        raise ValueError(f"no Corpus games in {output_dir}")
    require_trainable_corpus(root)
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


def require_trainable_corpus(output_dir: Path | str) -> None:
    """Refuse a Corpus whose manifest is missing or whose drop rate is above 1%."""
    root = Path(output_dir)
    reason = training_refusal(_read_manifest(root))
    if reason is not None:
        raise ValueError(f"{reason}: {root}")


def _bind_manifest(root: Path, invocation: CorpusManifest) -> None:
    existing = _read_manifest(root)
    if existing is None:
        if _has_recorded_games(root):
            raise ValueError(f"Corpus directory {root} has games but no manifest")
        _write_manifest(root, invocation)
        return
    conflicts = existing.resume_conflicts(invocation)
    if conflicts:
        fields = ", ".join(conflicts)
        raise ValueError(f"Corpus manifest disagrees with this invocation ({fields})")


def _read_manifest(root: Path) -> CorpusManifest | None:
    path = root / MANIFEST_NAME
    if not path.is_file():
        return None
    return CorpusManifest.from_json(path.read_text(encoding="utf-8"))


def _write_manifest(root: Path, manifest: CorpusManifest) -> None:
    dest = root / MANIFEST_NAME
    temporary = dest.with_name(f"{dest.name}.tmp")
    temporary.write_text(manifest.to_json(), encoding="utf-8")
    temporary.replace(dest)


def _has_recorded_games(root: Path) -> bool:
    games = root / _GAMES_DIR
    if games.is_dir() and any(games.glob("*.parquet")):
        return True
    dropped = root / _DROPPED_DIR
    return dropped.is_dir() and any(path.name.isdigit() for path in dropped.iterdir())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _git_identity() -> tuple[str, bool]:
    revision = _git_text(["rev-parse", "HEAD"])
    if revision is None:
        return "unknown", False
    status = _git_text(["status", "--porcelain"])
    if status is None:
        return revision, False
    return revision, status != ""


def _git_text(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


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
    sampled = _sample_game(
        job.game_id,
        job.ply_stride,
        job.max_turns,
        players=job.players,
        model_path=job.model_path,
    )
    root = Path(job.output_dir)
    if sampled is None:
        (root / _DROPPED_DIR / f"{job.game_id:05d}").write_text("")
        return
    winner, samples = sampled
    split = split_for_game(job.game_id, seed=job.seed, validation_fraction=job.validation_fraction)
    dest = root / _GAMES_DIR / f"{job.game_id:05d}.parquet"
    tmp = dest.with_name(f"{dest.name}.tmp")
    _rows_to_frame(job.game_id, split, winner, samples, seed=job.game_id).to_parquet(tmp)
    tmp.replace(dest)


def _sample_game(
    game_id: int,
    ply_stride: int,
    max_turns: int,
    *,
    players: str,
    model_path: str,
) -> tuple[str, list[tuple[int, str, np.ndarray]]] | None:
    game = Game(
        _seat_players(players, model_path, explore=players == "model"),
        seed=game_id,
        catan_map=corpus_map(game_id),
    )
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


_CACHED_MODEL: GbdtModel | None = None
_CACHED_MODEL_PATH = ""


def _seat_players(
    players: str,
    model_path: str,
    *,
    explore: bool = False,
) -> list[ValueFunctionPlayer | WinProbabilityPlayer]:
    if players == "value":
        return [ValueFunctionPlayer(color) for color in COLORS]
    return [
        WinProbabilityPlayer(
            color,
            _load_model(model_path),
            explore=explore,
            search_simulations=CORPUS_SEARCH_SIMULATIONS if explore else 0,
        )
        for color in COLORS
    ]


def _load_model(model_path: str) -> GbdtModel:
    global _CACHED_MODEL, _CACHED_MODEL_PATH
    if _CACHED_MODEL is None or model_path != _CACHED_MODEL_PATH:
        _CACHED_MODEL = GbdtModel.load(model_path)
        _CACHED_MODEL_PATH = model_path
    return _CACHED_MODEL


def _rows_to_frame(
    game_id: int,
    split: Split,
    winner: str,
    samples: list[tuple[int, str, np.ndarray]],
    *,
    seed: int,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [game_id] * len(samples),
            "ply": [ply for ply, _, _ in samples],
            "seat": [seat for _, seat, _ in samples],
            "split": [split] * len(samples),
            "won": [float(seat == winner) for _, seat, _ in samples],
            "seed": [seed] * len(samples),
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
    winners: dict[int, str] = {}
    rows = 0
    for path in files:
        frame = pd.read_parquet(path, columns=["game_id", "seat", "won"])
        rows += len(frame)
        won = frame.loc[frame["won"] == 1]
        if won.empty:
            continue
        winners[int(won["game_id"].iloc[0])] = str(won["seat"].iloc[0])
    played = len(winners)
    win_rate = dict(empty_rates)
    if played:
        for winner in winners.values():
            win_rate[winner] += 1.0 / played
    return CorpusSummary(
        games_played=played,
        games_dropped=dropped,
        rows_written=rows,
        win_rate_by_seat=win_rate,
    )
