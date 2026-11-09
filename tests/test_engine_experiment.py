from __future__ import annotations

import json
from pathlib import Path

import pytest
from catanatron.game import Game
from catanatron.models.player import Color, SimplePlayer

from catan_coach.domain.experiment import (
    DroppedGame,
    ExperimentPlan,
    FrozenPolicySpec,
    GameRules,
    PolicyPreference,
    SourceProvenance,
    schedule,
)
from catan_coach.engine.experiment import ENGINE_SHA, play_scheduled_game
from catan_coach.engine.preferences import selection_delta

pytestmark = pytest.mark.engine

COMMIT = "e" * 40
HASH = "a" * 64


def _plan(**updates: object) -> ExperimentPlan:
    values: dict[str, object] = {
        "name": "smoke",
        "candidate": FrozenPolicySpec("random", "random"),
        "opponent": FrozenPolicySpec("value", "value"),
        "games_per_candidate_seat": 1,
        "base_seed": 11,
        "source": SourceProvenance(COMMIT, False),
        "rules": GameRules(turn_limit=1),
    }
    values.update(updates)
    return ExperimentPlan(**values)  # type: ignore[arg-type]


def test_a_turn_limit_drops_without_a_winner_and_replays() -> None:
    game = schedule(_plan())[0]
    first = play_scheduled_game(game)
    second = play_scheduled_game(game)

    assert first == second
    assert isinstance(first, DroppedGame)
    assert first.reason == "turn_limit"
    assert len(first.seats) == 4
    assert first.candidate_seat == game.candidate_seat
    assert first.seats[game.candidate_seat].policy_name == "random"
    assert first.engine_sha == ENGINE_SHA
    assert first.seed == game.seed


def test_candidate_seat_survives_the_engine_shuffle() -> None:
    games = schedule(_plan(base_seed=40, games_per_candidate_seat=2))
    for game in games:
        result = play_scheduled_game(game)
        assert result.candidate_seat == game.candidate_seat
        assert result.seats[game.candidate_seat].policy_name == "random"
        assert [seat.policy_name for seat in result.seats].count("value") == 3


def test_different_seeds_have_different_result_keys() -> None:
    games = schedule(_plan())
    results = [play_scheduled_game(game) for game in games]
    assert len({result.result_key for result in results}) == 4


def test_a_changed_model_fails_before_play(tmp_path: Path) -> None:
    model = tmp_path / "model.txt"
    model.write_bytes(b"not a model")
    plan = _plan(
        candidate=FrozenPolicySpec(
            "candidate",
            "model",
            model_path=str(model),
            model_hash=HASH,
            search_simulations=0,
        ),
        rules=GameRules(turn_limit=1),
    )
    with pytest.raises(ValueError, match="model hash"):
        play_scheduled_game(schedule(plan)[0])


def test_a_preference_changes_the_chosen_action_and_not_the_probability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import numpy as np
    from catanatron.models.enums import Action, ActionType

    from catan_coach.domain.analysis import Analysis, RankedAction
    from catan_coach.domain.position import Action as Label
    from catan_coach.domain.position import Seat
    from catan_coach.engine import model_player
    from catan_coach.engine.model_player import WinProbabilityPlayer
    from catan_coach.engine.scoring import rank_resolved

    colors = (Color.RED, Color.BLUE, Color.ORANGE, Color.WHITE)
    game = Game([SimplePlayer(color) for color in colors], seed=3)
    city = Action(game.state.current_color(), ActionType.BUILD_CITY, 1)
    settlement = Action(game.state.current_color(), ActionType.BUILD_SETTLEMENT, 1)

    def choices(_game: Game, _actions: list[Action]) -> list[Action]:
        return [city, settlement]

    def ranked(_game: Game, _model: object) -> Analysis:
        return Analysis(
            Seat("RED"),
            (
                RankedAction(Label("BUILD_CITY 1"), 0.2, 0.0),
                RankedAction(Label("BUILD_SETTLEMENT 1"), 0.2, 0.0),
            ),
        )

    monkeypatch.setattr(model_player, "_choices", choices)
    monkeypatch.setattr(model_player, "rank_resolved", ranked)

    class Flat:
        name = "flat"

        def predict(self, features: np.ndarray) -> np.ndarray:
            return np.full(features.shape[0], 0.2)

    plain = WinProbabilityPlayer(game.state.current_color(), Flat())
    biased = WinProbabilityPlayer(
        game.state.current_color(),
        Flat(),
        preferences=lambda _game, action: (
            0.5 if action.action_type == ActionType.BUILD_SETTLEMENT else 0.0
        ),
    )
    assert plain.decide(game, [city, settlement]) == city
    assert biased.decide(game, [city, settlement]) == settlement
    analysis = rank_resolved(game, Flat())
    assert {row.win_probability for row in analysis.ranked} == {0.2}


def test_preferences_change_selection_without_changing_probabilities() -> None:
    colors = (Color.RED, Color.BLUE, Color.ORANGE, Color.WHITE)
    game = Game([SimplePlayer(color) for color in colors], seed=1)
    settlement = next(
        action for action in game.playable_actions if action.action_type.name == "BUILD_SETTLEMENT"
    )
    preference = (PolicyPreference("settlement", 0.05),)
    assert selection_delta(game, settlement, preference) == pytest.approx(0.05)
    assert selection_delta(game, settlement, (PolicyPreference("city", 0.05),)) == 0
    with pytest.raises(ValueError, match="zero search"):
        FrozenPolicySpec(
            "candidate",
            "model",
            model_path="model.txt",
            model_hash=HASH,
            search_simulations=4,
            declared_preferences=preference,
        )


def test_workers_replay_the_same_documents(tmp_path: Path) -> None:
    from catan_coach.cli import main

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "name": "smoke",
                "candidate": {"name": "random", "kind": "random"},
                "opponent": {"name": "value", "kind": "value"},
                "games_per_candidate_seat": 1,
                "base_seed": 11,
                "rules": {"turn_limit": 1},
            }
        ),
        encoding="utf-8",
    )
    first = tmp_path / "one"
    second = tmp_path / "two"
    assert (
        main(["lab", "run", str(plan_path), "--out", str(first), "--workers", "1", "--allow-dirty"])
        == 0
    )
    assert (
        main(
            ["lab", "run", str(plan_path), "--out", str(second), "--workers", "2", "--allow-dirty"]
        )
        == 0
    )
    assert (
        main(["lab", "run", str(plan_path), "--out", str(first), "--workers", "1", "--allow-dirty"])
        == 0
    )
    left = sorted((first / "games").glob("*.json"))
    right = sorted((second / "games").glob("*.json"))
    assert [path.read_text() for path in left] == [path.read_text() for path in right]
    report = main(["lab", "report", str(first)])
    assert report == 0


_TRADE_PROBE = """
from catanatron.game import Game
from catanatron.models.enums import Action, ActionPrompt, ActionType
from catanatron.models.player import Color, SimplePlayer
from catan_coach.domain.experiment import (
    ExperimentPlan,
    FrozenPolicySpec,
    GameRules,
    SourceProvenance,
    schedule,
)
from catan_coach.engine.experiment import play_scheduled_game

plan = ExperimentPlan(
    name="probe",
    candidate=FrozenPolicySpec("random", "random"),
    opponent=FrozenPolicySpec("value", "value"),
    games_per_candidate_seat=1,
    base_seed=1,
    source=SourceProvenance("e" * 40, False),
    rules=GameRules(turn_limit=1),
)
play_scheduled_game(schedule(plan)[0])
colors = (Color.RED, Color.BLUE, Color.ORANGE, Color.WHITE)
game = Game([SimplePlayer(color) for color in colors], seed=0)
state = game.state
offerer = state.colors[1]
state.is_initial_build_phase = False
state.current_prompt = ActionPrompt.PLAY_TURN
state.current_turn_index = 1
state.current_player_index = 1
game.execute(
    Action(offerer, ActionType.OFFER_TRADE, (1, 0, 0, 0, 0, 0, 1, 0, 0, 0)),
    validate_action=False,
)
assert state.current_player_index != 1
rejector = state.colors[state.current_player_index]
game.execute(Action(rejector, ActionType.REJECT_TRADE, None), validate_action=False)
still_deciding = state.current_prompt == ActionPrompt.DECIDE_TRADE
assert not still_deciding or state.current_player_index != 1
print("ok")
"""


def test_a_fresh_process_does_not_hand_an_offer_back_to_its_proposer() -> None:
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-c", _TRADE_PROBE],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_interrupt_does_not_keep_unstarted_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from catan_coach.engine.experiment_store import ExperimentStore
    from catan_coach.engine.lab import _play_all

    submitted: list[object] = []
    shutdown: dict[str, object] = {}

    class _Future:
        def result(self) -> None:
            raise AssertionError("a cancelled queue has no result")

        def cancel(self) -> bool:
            return True

    class _Pool:
        def __init__(self, max_workers: int) -> None:
            self.max_workers = max_workers

        def submit(self, _fn: object, game: object) -> _Future:
            submitted.append(game)
            return _Future()

        def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
            shutdown["wait"] = wait
            shutdown["cancel_futures"] = cancel_futures

    def _wait(
        futures: set[_Future], timeout: float | None = None, return_when: str | None = None
    ) -> tuple[set[_Future], set[_Future]]:
        raise KeyboardInterrupt

    monkeypatch.setattr("catan_coach.engine.lab.ProcessPoolExecutor", _Pool)
    monkeypatch.setattr("catan_coach.engine.lab.wait", _wait)
    plan = _plan()
    store = ExperimentStore.open(tmp_path, plan)
    with pytest.raises(KeyboardInterrupt):
        _play_all(store, list(schedule(plan)), 1, 0.0, tmp_path)

    assert len(schedule(plan)) > 1
    assert len(submitted) == 1
    assert shutdown == {"wait": False, "cancel_futures": True}


def test_an_assertion_is_not_recorded_as_a_game_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from catan_coach.engine.experiment_store import ExperimentStore
    from catan_coach.engine.lab import _play_all

    class _Future:
        def result(self) -> None:
            raise AssertionError("programmer")

    class _Pool:
        def __init__(self, max_workers: int) -> None:
            self.max_workers = max_workers

        def submit(self, _fn: object, _game: object) -> _Future:
            return _Future()

        def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
            return None

    def _wait(
        futures: set[_Future], timeout: float | None = None, return_when: str | None = None
    ) -> tuple[set[_Future], set[_Future]]:
        return set(futures), set()

    monkeypatch.setattr("catan_coach.engine.lab.ProcessPoolExecutor", _Pool)
    monkeypatch.setattr("catan_coach.engine.lab.wait", _wait)
    plan = _plan()
    store = ExperimentStore.open(tmp_path, plan)
    with pytest.raises(AssertionError, match="programmer"):
        _play_all(store, list(schedule(plan)), 1, 0.0, tmp_path)
    assert list((tmp_path / "failures").rglob("*.json")) == []
