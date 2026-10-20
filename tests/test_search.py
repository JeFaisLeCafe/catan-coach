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
    ) -> None:
        self._seat = seat
        self._actions = actions or {}
        self._values = values or {}
        self._winner = winner
        self.steps = 0

    def seat(self) -> str:
        return self._seat

    def actions(self) -> tuple[str, ...]:
        return tuple(self._actions)

    def step(self, action: str, rng: random.Random) -> SearchState:
        del rng
        self.steps += 1
        return self._actions[action]

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
