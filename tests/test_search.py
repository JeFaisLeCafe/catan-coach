"""Progressive search on a hand-built tree: stop, time, and cache."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator

import pytest

from catan_coach.domain.search import Budget, SearchCache, SearchState, Snapshot, progressive_search


class Tiny:
    def __init__(
        self,
        seat: str,
        actions: dict[str, Tiny] | None = None,
        values: dict[str, float] | None = None,
        winner: str | None = None,
        outcomes: dict[str, tuple[tuple[str, float], ...]] | None = None,
        worlds: dict[str, dict[str, Tiny]] | None = None,
    ) -> None:
        self._seat = seat
        self._actions = actions or {}
        self._values = values or {}
        self._winner = winner
        self._outcomes = outcomes or {}
        self._worlds = worlds or {}
        self.steps = 0
        self.seen: list[str | None] = []

    def seat(self) -> str:
        return self._seat

    def actions(self) -> tuple[str, ...]:
        return tuple(self._actions)

    def outcomes(self, action: str) -> tuple[tuple[str, float], ...] | None:
        return self._outcomes.get(action)

    def step(self, action: str, rng: random.Random, outcome: str | None = None) -> SearchState:
        del rng
        self.steps += 1
        self.seen.append(outcome)
        if outcome is None:
            return self._actions[action]
        return self._worlds[action][outcome]

    def winner(self) -> str | None:
        return self._winner

    def value(self, seat: str) -> float:
        return self._values[seat]


def _tree() -> Tiny:
    red_win = Tiny("RED", winner="RED", values={"RED": 1.0, "BLUE": 0.0})
    blue_win = Tiny("BLUE", winner="BLUE", values={"RED": 0.0, "BLUE": 1.0})
    return Tiny(
        "RED",
        actions={"good": red_win, "bad": blue_win},
        values={"RED": 0.4, "BLUE": 0.6},
    )


def _run(
    root: Tiny,
    budget: Budget,
    clock: Callable[[], float],
    stop: Callable[[], bool],
) -> Iterator[Snapshot]:
    return progressive_search(
        root,
        root_seat="RED",
        prior=(("good", 0.2), ("bad", 0.7)),
        budget=budget,
        clock=clock,
        rng=random.Random(0),
        stop=stop,
        batch_size=2,
        max_depth=4,
    )


def test_the_first_snapshot_is_the_model_ranking() -> None:
    first = next(_run(_tree(), Budget("immediate"), clock=lambda: 0.0, stop=lambda: False))

    assert first.source == "immediate"
    assert first.simulations == 0
    assert [line.action for line in first.lines] == ["bad", "good"]
    assert first.lines[0].win_probability == pytest.approx(0.7)
    assert first.uncertainty == 0.0


def test_a_simulation_budget_needs_a_count() -> None:
    with pytest.raises(ValueError, match="positive count"):
        Budget("simulations")


def test_a_simulation_budget_stops_at_the_count() -> None:
    snapshots = list(
        _run(_tree(), Budget("simulations", simulations=3), clock=lambda: 0.0, stop=lambda: False)
    )

    assert snapshots[-1].simulations == 3
    assert snapshots[-1].source == "search"


def test_a_timed_budget_stops_when_the_clock_passes_it() -> None:
    now = {"t": 0.0}
    generator = _run(_tree(), Budget("timed", 1.0), clock=lambda: now["t"], stop=lambda: False)
    first = next(generator)
    now["t"] = 2.0

    assert first.simulations == 0
    assert list(generator) == []


def test_stopping_drops_the_snapshot_still_in_progress() -> None:
    hold = {"stop": False}
    generator = _run(_tree(), Budget("continuous"), clock=lambda: 0.0, stop=lambda: hold["stop"])
    next(generator)
    hold["stop"] = True
    assert list(generator) == []


def test_work_increases_across_snapshots() -> None:
    snapshots = []
    generator = _run(_tree(), Budget("continuous"), clock=lambda: 0.0, stop=lambda: False)
    for _ in range(3):
        snapshots.append(next(generator))

    simulations = [snapshot.simulations for snapshot in snapshots]
    nodes = [snapshot.nodes for snapshot in snapshots]
    assert simulations == sorted(simulations)
    assert nodes == sorted(nodes)
    assert simulations[0] < simulations[-1]
    assert snapshots[-1].source == "search"
    assert snapshots[-1].horizon >= 1


def test_the_seat_to_move_keeps_the_result_that_wins_for_them() -> None:
    red_win = Tiny("BLUE", winner="RED")
    blue_win = Tiny("BLUE", winner="BLUE")
    blue_choice = Tiny("BLUE", actions={"help": red_win, "keep": blue_win})
    root = Tiny("RED", actions={"only": blue_choice})
    generator = progressive_search(
        root,
        root_seat="RED",
        prior=(("only", 0.9),),
        budget=Budget("continuous"),
        clock=lambda: 0.0,
        rng=random.Random(0),
        stop=lambda: False,
        batch_size=1,
        max_depth=3,
        policy_width=2,
    )
    immediate = next(generator)
    refined = next(generator)

    assert immediate.lines[0].win_probability == pytest.approx(0.9)
    assert refined.lines[0].win_probability == pytest.approx(0.45)
    assert refined.lines[0].visits == 1


def test_the_horizon_grows_as_lines_reach_the_frontier() -> None:
    node = Tiny("RED", winner="RED", values={"RED": 1.0})
    for ply in range(12):
        node = Tiny("RED", actions={f"ply-{ply}": node}, values={"RED": 0.2})
    snapshots = []
    generator = progressive_search(
        node,
        root_seat="RED",
        prior=((node.actions()[0], 0.5),),
        budget=Budget("continuous"),
        clock=lambda: 0.0,
        rng=random.Random(0),
        stop=lambda: False,
        batch_size=1,
        max_depth=12,
        policy_width=1,
    )
    for _ in range(8):
        snapshots.append(next(generator))

    horizons = [snapshot.horizon for snapshot in snapshots]
    assert horizons[0] == 1
    assert horizons == sorted(horizons)
    assert horizons[-1] > 4


def test_a_spent_node_budget_ends_the_search() -> None:
    snapshots = []
    generator = progressive_search(
        _tree(),
        root_seat="RED",
        prior=(("good", 0.2), ("bad", 0.7)),
        budget=Budget("continuous"),
        clock=lambda: 0.0,
        rng=random.Random(0),
        stop=lambda: False,
        batch_size=1,
        max_depth=4,
        max_nodes=1,
    )
    for snapshot in generator:
        snapshots.append(snapshot)
        if len(snapshots) > 20:
            break

    assert len(snapshots) < 20
    assert snapshots[-1].source == "search"
    assert snapshots[-1].nodes == 1


def test_a_finished_depth_ends_the_search() -> None:
    node = Tiny("RED", winner="RED", values={"RED": 1.0})
    for ply in range(6):
        node = Tiny("RED", actions={f"ply-{ply}": node}, values={"RED": 0.2})
    snapshots = []
    generator = progressive_search(
        node,
        root_seat="RED",
        prior=((node.actions()[0], 0.5),),
        budget=Budget("continuous"),
        clock=lambda: 0.0,
        rng=random.Random(0),
        stop=lambda: False,
        batch_size=1,
        max_depth=2,
        policy_width=1,
    )
    for snapshot in generator:
        snapshots.append(snapshot)
        if len(snapshots) > 20:
            break

    assert len(snapshots) < 20
    assert snapshots[-1].horizon <= 2


def test_another_simulation_tries_a_new_dice_total() -> None:
    high = Tiny("BLUE", winner="RED", values={"RED": 1.0})
    low = Tiny("BLUE", winner="BLUE", values={"RED": 0.0})
    root = Tiny(
        "RED",
        actions={"roll": low},
        values={"RED": 0.5},
        outcomes={"roll": (("low", 0.25), ("high", 0.75))},
        worlds={"roll": {"low": low, "high": high}},
    )
    generator = progressive_search(
        root,
        root_seat="RED",
        prior=(("roll", 0.5),),
        budget=Budget("continuous"),
        clock=lambda: 0.0,
        rng=random.Random(0),
        stop=lambda: False,
        batch_size=1,
        max_depth=2,
    )
    next(generator)
    first = next(generator)
    second = next(generator)

    assert root.seen == ["high", "low"]
    assert first.nodes == 1
    assert second.nodes == 2
    assert first.lines[0].visits == 1
    assert second.lines[0].visits == 2


def test_a_completed_snapshot_is_reused_without_stepping() -> None:
    root = _tree()
    finished = list(_run(root, Budget("immediate"), clock=lambda: 0.0, stop=lambda: False))[-1]
    cache = SearchCache()
    key = cache.key("position-1", "gbdt", Budget("immediate"))
    cache.put(key, finished)
    steps_before = root.steps

    found = cache.get(cache.key("position-1", "gbdt", Budget("immediate")))

    assert found == finished
    assert cache.get(cache.key("position-2", "gbdt", Budget("immediate"))) is None
    assert root.steps == steps_before
