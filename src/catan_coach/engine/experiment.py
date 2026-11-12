"""Play one scheduled Strategy Lab game on the pinned Catanatron engine."""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import lightgbm as lgb
from catanatron.game import Game
from catanatron.models.enums import Action
from catanatron.models.player import Color, Player
from catanatron.players.value import ValueFunctionPlayer

from catan_coach.domain.experiment import (
    CompletedGame,
    DroppedGame,
    FrozenPolicySpec,
    PartialSeatResult,
    ScheduledGame,
    SeatResult,
)
from catan_coach.domain.probability_map import ProbabilityMap
from catan_coach.engine.behavior import BehaviorTracker
from catan_coach.engine.board import corpus_map
from catan_coach.engine.model_player import WinProbabilityPlayer
from catan_coach.engine.position import action_label
from catan_coach.engine.preferences import selection_delta
from catan_coach.engine.trades import install_trade_replies
from catan_coach.models.gbdt import GbdtModel

# The engine pin in pyproject.toml. A different checkout must not silently play.
ENGINE_SHA = "ecf931181b9a65bb4116a2153fb78c16f1438e00"
_SEAT_COLORS = (Color.RED, Color.BLUE, Color.ORANGE, Color.WHITE)
_MODELS: dict[tuple[str, str | None], GbdtModel] = {}


class _RandomPolicy(Player):  # type: ignore[misc]
    """Smoke-test Policy. It draws from the game's own random stream."""

    def decide(self, game: Game, playable_actions: list[object]) -> object:
        return game.state.random.choice(playable_actions)


# Called before each Ply with the number of Plies already played.
PlyObserver = Callable[[int, Game], None]


def play_scheduled_game(
    scheduled: ScheduledGame,
    observe: PlyObserver | None = None,
) -> CompletedGame | DroppedGame:
    """Play `scheduled` once. Exceptions propagate; the caller records a retry.

    `observe` sees the Position before every Ply. It must not change the game
    or draw from its random stream, or the replay is a different game.
    """
    # Workers are fresh processes. Without this, a refused offer is handed to
    # its proposer because the upstream reply scan does not skip that Seat.
    install_trade_replies()
    if scheduled.map_policy != "corpus":
        raise ValueError("version 1 uses the corpus map")
    players = [
        _player(policy, color)
        for policy, color in zip(scheduled.policies, _SEAT_COLORS, strict=True)
    ]
    game = Game(
        _invert_seating(players, scheduled.seed),
        seed=scheduled.seed,
        discard_limit=scheduled.rules.discard_limit,
        friendly_robber=scheduled.rules.friendly_robber,
        vps_to_win=scheduled.rules.vps_to_win,
        catan_map=corpus_map(scheduled.seed),
    )
    actual = tuple(player.color for player in game.state.players)
    if actual != _SEAT_COLORS:
        raise RuntimeError("Catanatron seated the Policies out of schedule order")
    tracker = BehaviorTracker.start(game)
    plies = 0
    while game.winning_color() is None and game.state.num_turns < scheduled.rules.turn_limit:
        if observe is not None:
            observe(plies, game)
        initial_build = game.state.is_initial_build_phase
        # ValueFunctionPlayer breaks ties using the first legal Action.
        # Catanatron's set-backed choices otherwise depend on process hashes.
        actions = sorted(game.playable_actions, key=action_label)
        action = game.state.current_player().decide(game, actions)
        record = game.execute(action)
        tracker.observe(initial_build, action, record, game)
        plies += 1
    identity = {
        "result_key": scheduled.result_key,
        "pairing_key": scheduled.pairing_key,
        "seed": scheduled.seed,
        "map_seed": scheduled.seed,
        "candidate_seat": scheduled.candidate_seat,
        "policies": scheduled.policies,
        "map_policy": scheduled.map_policy,
        "rules": scheduled.rules,
        "source": scheduled.source,
        "engine_version": _engine_version(),
        "engine_sha": ENGINE_SHA,
        "plies": plies,
        "turns": game.state.num_turns,
    }
    if game.winning_color() is None:
        partial = tracker.finish_partial(game)
        return DroppedGame(
            **identity,
            reason="turn_limit",
            seats=tuple(
                PartialSeatResult(index, color.value, scheduled.policies[index].name, profile)
                for index, (color, profile) in enumerate(
                    zip(game.state.colors, partial, strict=True)
                )
            ),
        )
    finished = tracker.finish(game)
    winner = game.state.color_to_index[game.winning_color()]
    return CompletedGame(
        **identity,
        winner=winner,
        seats=tuple(
            SeatResult(index, color.value, scheduled.policies[index].name, profile)
            for index, (color, profile) in enumerate(zip(game.state.colors, finished, strict=True))
        ),
    )


def _player(policy: FrozenPolicySpec, color: Color) -> Player:
    if policy.declared_preferences and policy.search_simulations > 0:
        raise ValueError(f"{policy.name} combines preferences with search")
    if policy.kind == "value":
        return ValueFunctionPlayer(color)
    if policy.kind == "random":
        return _RandomPolicy(color)
    if policy.kind != "model":
        raise ValueError(f"unknown Policy kind {policy.kind}")
    model = _load_model(policy)
    adjust: Callable[[Game, Action], float] | None = None
    if policy.declared_preferences:
        declared = policy.declared_preferences

        def adjust(game: Game, action: Action) -> float:
            return selection_delta(game, action, declared)

    return WinProbabilityPlayer(
        color,
        model,
        explore=policy.explore,
        search_simulations=policy.search_simulations,
        preferences=adjust,
    )


def _load_model(policy: FrozenPolicySpec) -> GbdtModel:
    if policy.model_path is None or policy.model_hash is None:
        raise ValueError(f"{policy.name} has no frozen model")
    path = Path(policy.model_path)
    if not path.is_file():
        raise ValueError(f"missing model file {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != policy.model_hash:
        raise ValueError(f"model hash for {policy.name} does not match {path}")
    sidecar_hash: str | None = None
    probability_map = None
    if policy.sidecar_path is not None:
        sidecar = Path(policy.sidecar_path)
        if not sidecar.is_file():
            raise ValueError(f"missing calibration sidecar {sidecar}")
        sidecar_hash = hashlib.sha256(sidecar.read_bytes()).hexdigest()
        if sidecar_hash != policy.sidecar_hash:
            raise ValueError(f"sidecar hash for {policy.name} does not match {sidecar}")
        probability_map = ProbabilityMap.from_json_knots(json.loads(sidecar.read_text())["knots"])
    key = (digest, sidecar_hash)
    cached = _MODELS.get(key)
    if cached is not None:
        return cached
    model = GbdtModel(
        lgb.Booster(model_file=str(path)),
        name=policy.name,
        probability_map=probability_map,
    )
    _MODELS[key] = model
    return model


def _invert_seating(players: list[Player], seed: int) -> list[Player]:
    desired = [player.color for player in players]
    for candidate in itertools.permutations(players):
        seated = random.Random(seed).sample(list(candidate), len(candidate))
        if [player.color for player in seated] == desired:
            return list(candidate)
    raise RuntimeError("Catanatron seating shuffle could not be inverted")


def _engine_version() -> str:
    try:
        return version("catanatron")
    except PackageNotFoundError:
        return "unknown"
