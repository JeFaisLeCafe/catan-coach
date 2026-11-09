"""Play one scheduled game of generation 7 against three value-function seats."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from catanatron import Game
from catanatron.models.enums import ActionType
from catanatron.players.value import ValueFunctionPlayer

from catan_coach.domain.strength import (
    SEATS,
    GameRecord,
    candidate_seat_for_seed,
    game_record_from_json,
    game_record_to_json,
)
from catan_coach.engine.board import corpus_map
from catan_coach.engine.corpus import COLORS
from catan_coach.engine.model_player import WinProbabilityPlayer
from catan_coach.models.gbdt import GbdtModel

AUDIT_SEARCH_SIMULATIONS = 4
_MODELS: dict[str, GbdtModel] = {}


def play_audit(
    output_dir: Path | str,
    *,
    model_path: Path | str,
    games: int,
    base_seed: int = 20_000,
) -> None:
    """Play ``games`` seeds from ``base_seed``, skipping seeds that already have a file."""
    if games < 1:
        raise ValueError("games must be at least 1")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    model = _load_model(Path(model_path))
    for offset in range(games):
        play_scheduled_game(
            base_seed + offset,
            root,
            model=model,
            base_seed=base_seed,
        )


def play_scheduled_game(
    seed: int,
    output_dir: Path | str,
    *,
    model_path: Path | str | None = None,
    model: GbdtModel | None = None,
    base_seed: int = 20_000,
    vps_to_win: int = 10,
    search_simulations: int = AUDIT_SEARCH_SIMULATIONS,
) -> Path:
    """Play one seed and write its JSON atomically. An existing file is left untouched."""
    if vps_to_win < 1:
        raise ValueError("vps_to_win must be at least 1")
    if search_simulations < 0:
        raise ValueError("search_simulations must be non-negative")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"{seed}.json"
    candidate = candidate_seat_for_seed(seed, base_seed=base_seed)
    if dest.is_file():
        existing = game_record_from_path(dest)
        if existing.seed != seed or existing.candidate_seat != candidate:
            raise ValueError(f"{dest} does not match seed {seed} seat {candidate}")
        return dest
    if model is None:
        if model_path is None:
            raise ValueError("need a model file")
        model = _load_model(Path(model_path))
    record = _play(
        seed,
        candidate,
        model,
        vps_to_win=vps_to_win,
        search_simulations=search_simulations,
    )
    _write_atomic(dest, game_record_to_json(record))
    rolls = "unavailable" if record.rolls is None else str(len(record.rolls))
    print(
        f"saved seed {seed} seat {candidate} turns {record.turn_count} rolls {rolls}",
        file=sys.stderr,
    )
    return dest


def players_for_seat(
    candidate: str,
    model: GbdtModel,
    *,
    search_simulations: int = AUDIT_SEARCH_SIMULATIONS,
) -> list[ValueFunctionPlayer | WinProbabilityPlayer]:
    """Seat the candidate at one color. The other three seats are ValueFunctionPlayer."""
    if candidate not in SEATS:
        raise ValueError(f"unknown candidate seat {candidate}")
    names = tuple(color.name for color in COLORS)
    if names != SEATS:
        raise RuntimeError(f"seat order {names} does not match {SEATS}")
    seated: list[ValueFunctionPlayer | WinProbabilityPlayer] = []
    for color in COLORS:
        if color.name == candidate:
            seated.append(
                WinProbabilityPlayer(
                    color,
                    model,
                    explore=False,
                    search_simulations=search_simulations,
                )
            )
        else:
            seated.append(ValueFunctionPlayer(color))
    return seated


def game_record_from_path(path: Path) -> GameRecord:
    return game_record_from_json(json.loads(path.read_text(encoding="utf-8")))


def _play(
    seed: int,
    candidate: str,
    model: GbdtModel,
    *,
    vps_to_win: int,
    search_simulations: int,
) -> GameRecord:
    game = Game(
        players_for_seat(candidate, model, search_simulations=search_simulations),
        seed=seed,
        vps_to_win=vps_to_win,
        catan_map=corpus_map(seed),
    )
    game.play()
    winner = game.winning_color()
    return GameRecord(
        seed=seed,
        candidate_seat=candidate,
        winner_seat=None if winner is None else str(winner.name),
        turn_count=int(game.state.num_turns),
        rolls=_production_rolls(game),
    )


def _production_rolls(game: Game) -> tuple[int, ...] | None:
    sums: list[int] = []
    for record in game.state.action_records:
        action = record.action
        if action.action_type != ActionType.ROLL:
            continue
        total = _pair_sum(record.result)
        if total is None:
            return None
        sums.append(total)
    return tuple(sums)


def _pair_sum(result: object) -> int | None:
    if not isinstance(result, tuple | list) or len(result) != 2:
        return None
    left, right = result
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    if not isinstance(left, int) or not isinstance(right, int):
        return None
    total = left + right
    if total < 2 or total > 12:
        return None
    return total


def _load_model(path: Path) -> GbdtModel:
    if not path.is_file():
        raise ValueError(f"model file not found: {path}")
    key = str(path.resolve())
    cached = _MODELS.get(key)
    if cached is None:
        cached = GbdtModel.load(path)
        _MODELS[key] = cached
    return cached


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
