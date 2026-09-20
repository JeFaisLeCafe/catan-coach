"""Save and restore games with the engine's JSON serialization."""

from __future__ import annotations

import json
import random
from itertools import permutations
from pathlib import Path

from catanatron import Game
from catanatron.models.player import Color, SimplePlayer
from catanatron.serialization import state_from_json, state_to_json

from catan_coach.engine.position import EnginePosition


def write_game(game: Game, path: Path | str) -> None:
    Path(path).write_text(json.dumps(state_to_json(game)))


def read_game(path: Path | str) -> Game:
    document = json.loads(Path(path).read_text())
    players = [SimplePlayer(Color[color]) for color in document["colors"]]
    return state_from_json(document, players)


def position_at_ply(game: Game, ply: int) -> EnginePosition:
    records = game.state.action_records
    last = max(len(records) - 1, 0)
    if ply < 0 or ply > last:
        raise ValueError(f"Ply {ply} is out of range; valid plies are 0 to {last}")
    reconstructed = _opening_from(game)
    for record in records[:ply]:
        reconstructed.execute(record.action, validate_action=False, action_record=record)
    # Recorded dice and steals restore the board; they do not replay bot lookahead,
    # which in catanatron consumes the shared RNG on copies. Reseed so ROLL from
    # this Position is deterministic rather than leftover opening dice.
    rng = random.Random(f"{reconstructed.seed}:{ply}")
    reconstructed.random = rng
    reconstructed.state.random = rng
    return EnginePosition(reconstructed)


def _opening_from(game: Game) -> Game:
    seating = tuple(game.state.colors)
    for order in permutations(seating):
        candidate = Game(
            [SimplePlayer(color) for color in order],
            seed=game.seed,
            discard_limit=game.state.discard_limit,
            friendly_robber=game.friendly_robber,
            vps_to_win=game.vps_to_win,
        )
        if tuple(candidate.state.colors) == seating:
            return candidate
    raise ValueError("could not reconstruct the opening Position from this game's seed")
