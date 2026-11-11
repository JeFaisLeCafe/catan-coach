"""The model chooses a legal Action, the same one Analysis ranks first.

Initial settlements are chosen by production pips instead.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.engine

catanatron = pytest.importorskip("catanatron")

from catanatron.game import Game  # noqa: E402
from catanatron.models.player import Color, SimplePlayer  # noqa: E402

from catan_coach.domain.analysis import analyze  # noqa: E402
from catan_coach.engine.features import public_vp_indices  # noqa: E402
from catan_coach.engine.model_player import WinProbabilityPlayer  # noqa: E402
from catan_coach.engine.position import EnginePosition, action_label  # noqa: E402
from catan_coach.models.baselines import VictoryPointShareModel  # noqa: E402


def test_opening_settlement_follows_production_even_when_search_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from catanatron.models.enums import ActionType

    from catan_coach.engine.behavior import opening_pips

    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    game = Game([SimplePlayer(color) for color in colors], seed=1)
    settlements = [
        action
        for action in game.playable_actions
        if action.action_type == ActionType.BUILD_SETTLEMENT
    ]

    def unused(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("opening settlement must not consult the model")

    monkeypatch.setattr("catan_coach.engine.model_player.refine_position", unused)
    monkeypatch.setattr("catan_coach.engine.model_player.rank_resolved", unused)
    chosen = WinProbabilityPlayer(
        game.state.current_color(),
        VictoryPointShareModel(public_vp_indices(4)),
        search_simulations=4,
    ).decide(game, game.playable_actions)

    assert chosen in settlements
    assert opening_pips(game, int(chosen.value)) == max(
        opening_pips(game, int(action.value)) for action in settlements
    )


def test_initial_road_still_matches_the_analysis() -> None:
    from catanatron.models.enums import ActionType

    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    game = Game([SimplePlayer(color) for color in colors], seed=1)
    model = VictoryPointShareModel(public_vp_indices(4))
    player = WinProbabilityPlayer(game.state.current_color(), model)
    settlement = player.decide(game, game.playable_actions)
    assert settlement.action_type == ActionType.BUILD_SETTLEMENT
    game.execute(settlement)

    chosen = player.decide(game, game.playable_actions)
    assert chosen.action_type == ActionType.BUILD_ROAD
    assert action_label(chosen) == analyze(EnginePosition(game), model).ranked[0].action.label


def test_the_same_seed_replays_a_near_tie() -> None:
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    model = VictoryPointShareModel(public_vp_indices(4))

    def labels(seed: int) -> list[str]:
        game = Game(
            [WinProbabilityPlayer(color, model, explore=True) for color in colors],
            seed=seed,
        )
        played: list[str] = []
        for _ in range(8):
            game.play_tick()
            played.append(action_label(game.state.action_records[-1].action))
        return played

    assert labels(5) == labels(5)


def test_the_same_seed_replays_a_searched_game() -> None:
    from catan_coach.engine.model_player import CORPUS_SEARCH_SIMULATIONS

    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    model = VictoryPointShareModel(public_vp_indices(4))

    def labels(seed: int) -> list[str]:
        game = Game(
            [
                WinProbabilityPlayer(
                    color,
                    model,
                    explore=True,
                    search_simulations=CORPUS_SEARCH_SIMULATIONS,
                )
                for color in colors
            ],
            seed=seed,
        )
        played: list[str] = []
        for _ in range(4):
            game.play_tick()
            played.append(action_label(game.state.action_records[-1].action))
        return played

    assert labels(5) == labels(5)


def test_a_forced_action_skips_the_search(monkeypatch: pytest.MonkeyPatch) -> None:
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    game = Game([SimplePlayer(color) for color in colors], seed=1)
    only = game.playable_actions[0]
    calls: list[object] = []

    monkeypatch.setattr(
        "catan_coach.engine.model_player._choices",
        lambda _game, _playable: [only],
    )
    monkeypatch.setattr(
        "catan_coach.engine.model_player.refine_position",
        lambda *_args, **_kwargs: calls.append(1),
    )
    chosen = WinProbabilityPlayer(
        game.state.current_color(),
        VictoryPointShareModel(public_vp_indices(4)),
        explore=True,
        search_simulations=4,
    ).decide(game, game.playable_actions)

    assert chosen == only
    assert calls == []


def test_a_trade_reply_uses_the_fixed_search(monkeypatch: pytest.MonkeyPatch) -> None:
    from catanatron.models.enums import ActionPrompt

    from catan_coach.domain.search import Budget, Line, Snapshot
    from catan_coach.engine.model_player import CORPUS_SEARCH_DEPTH

    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    game = Game([SimplePlayer(color) for color in colors], seed=1)
    game.state.is_initial_build_phase = False
    game.state.current_prompt = ActionPrompt.DECIDE_TRADE
    seen: dict[str, object] = {}

    def refine(*_args: object, **kwargs: object) -> object:
        seen["budget"] = kwargs["budget"]
        seen["depth"] = kwargs["max_depth"]
        lines = tuple(
            Line(
                action=action_label(action),
                win_probability=1.0 if index == 0 else 0.0,
                loss=0.0 if index == 0 else 1.0,
                visits=4,
            )
            for index, action in enumerate(game.playable_actions)
        )
        return iter(
            (
                Snapshot(
                    source="search",
                    seat="RED",
                    lines=lines,
                    simulations=4,
                    nodes=1,
                    elapsed=0.0,
                    horizon=1.0,
                    uncertainty=0.0,
                ),
            )
        )

    def one_ply_guess(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("one-ply trade guess")

    monkeypatch.setattr("catan_coach.engine.model_player.refine_position", refine)
    monkeypatch.setattr("catan_coach.engine.model_player.reply_helps", one_ply_guess)
    chosen = WinProbabilityPlayer(
        game.state.current_color(),
        VictoryPointShareModel(public_vp_indices(4)),
        explore=True,
        search_simulations=4,
    ).decide(game, game.playable_actions)

    assert chosen == game.playable_actions[0]
    assert seen["budget"] == Budget("simulations", simulations=4)
    assert seen["depth"] == CORPUS_SEARCH_DEPTH
