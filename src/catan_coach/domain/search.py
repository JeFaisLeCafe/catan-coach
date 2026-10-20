"""Anytime search: the model first, then sampled play that can be stopped."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class Budget:
    mode: Literal["immediate", "timed", "continuous"]
    seconds: float | None = None

    def __post_init__(self) -> None:
        if self.mode == "timed" and (self.seconds is None or self.seconds <= 0):
            raise ValueError("a timed Search Budget needs a positive duration")
        if self.mode != "timed" and self.seconds is not None:
            raise ValueError("only a timed Search Budget has a duration")


@dataclass(frozen=True, slots=True)
class Line:
    action: str
    win_probability: float
    loss: float
    visits: int


@dataclass(frozen=True, slots=True)
class Snapshot:
    source: Literal["immediate", "search"]
    seat: str
    lines: tuple[Line, ...]
    simulations: int
    nodes: int
    elapsed: float
    horizon: float
    uncertainty: float


class SearchState(Protocol):
    def seat(self) -> str: ...

    def actions(self) -> tuple[str, ...]: ...

    def step(self, action: str, rng: random.Random) -> SearchState: ...

    def winner(self) -> str | None: ...

    def value(self, seat: str) -> float: ...


@dataclass
class _Stats:
    prior: float
    visits: int = 0
    total: float = 0.0
    sumsq: float = 0.0


@dataclass
class _Edge:
    visits: int = 0
    total: float = 0.0


@dataclass
class _Node:
    """One reached Position. The child state is kept so a later visit is not copied again."""

    actions: tuple[str, ...] = ()
    priors: dict[str, float] = field(default_factory=dict)
    children: dict[str, tuple[_Node, SearchState]] = field(default_factory=dict)
    edges: dict[str, _Edge] = field(default_factory=dict)
    visits: int = 0


class SearchCache:
    """Completed snapshots, keyed by Position, model, and Search Budget."""

    def __init__(self) -> None:
        self._items: dict[str, Snapshot] = {}

    @staticmethod
    def key(position_id: str, model: str, budget: Budget) -> str:
        duration = "" if budget.seconds is None else f":{budget.seconds}"
        return f"{position_id}|{model}|{budget.mode}{duration}"

    def get(self, key: str) -> Snapshot | None:
        return self._items.get(key)

    def put(self, key: str, snapshot: Snapshot) -> None:
        self._items[key] = snapshot


def progressive_search(
    root: SearchState,
    *,
    root_seat: str,
    prior: Sequence[tuple[str, float]],
    budget: Budget,
    clock: Callable[[], float],
    rng: random.Random,
    stop: Callable[[], bool],
    batch_size: int = 8,
    max_depth: int = 24,
    policy_width: int = 3,
    max_nodes: int = 40_000,
) -> Iterator[Snapshot]:
    """Yield the model ranking, then extend a kept tree until the budget or `stop`.

    `stop` is checked before every snapshot, so a Position change drops a
    result that belongs to the Position that is already gone. The clock is
    checked between plies. Depth starts at 2 and grows once several lines
    have reached the frontier, so extra time looks further ahead instead of
    replaying the same short paths. Each stored node is one sampled future;
    the seat to move still keeps the continuation that wins for them.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if policy_width < 1:
        raise ValueError("policy_width must be at least 1")
    if stop():
        return
    started = clock()
    limit = budget.seconds if budget.mode == "timed" else None
    stats = {action: _Stats(prior=probability) for action, probability in prior}
    order = tuple(action for action, _ in prior)
    root_node = _Node(actions=order, priors=dict(prior))
    nodes = 0
    simulations = 0
    deepest = 1
    depth_limit = min(2, max_depth)
    frontier_hits = 0
    coverage = min(len(order), max(4, policy_width)) if order else 1
    slots = max_nodes

    def halted() -> bool:
        if stop():
            return True
        return limit is not None and _elapsed(clock, started) >= limit

    def allocate() -> bool:
        nonlocal slots
        if slots <= 0:
            return False
        slots -= 1
        return True

    yield _snapshot(
        stats,
        order,
        seat=root_seat,
        simulations=0,
        nodes=nodes,
        elapsed=_elapsed(clock, started),
        horizon=1.0,
        source="immediate",
    )
    if budget.mode == "immediate":
        return

    while not halted():
        if not order:
            return
        completed = 0
        for _ in range(batch_size):
            if halted():
                break
            action = _select(stats, order, simulations)
            reward, depth, explored, reached = _extend(
                root_node,
                root,
                action,
                root_seat,
                rng,
                depth_limit=depth_limit,
                policy_width=policy_width,
                halt=halted,
                allocate=allocate,
            )
            if depth == 0:
                break
            nodes += explored
            deepest = max(deepest, depth)
            if reached:
                frontier_hits += 1
            row = stats[action]
            row.visits += 1
            row.total += reward
            row.sumsq += reward * reward
            simulations += 1
            completed += 1
            if frontier_hits >= coverage and depth_limit < max_depth:
                depth_limit += 1
                frontier_hits = 0
        if completed == 0 or stop():
            return
        yield _snapshot(
            stats,
            order,
            seat=root_seat,
            simulations=simulations,
            nodes=nodes,
            elapsed=_elapsed(clock, started),
            horizon=float(deepest),
            source="search",
        )


def _extend(
    node: _Node,
    state: SearchState,
    first: str,
    root_seat: str,
    rng: random.Random,
    *,
    depth_limit: int,
    policy_width: int,
    halt: Callable[[], bool],
    allocate: Callable[[], bool],
) -> tuple[float, int, int, bool]:
    path: list[tuple[_Node, str, str]] = []
    current_node = node
    current_state = state
    next_action: str | None = first
    depth = 0
    created = 0
    while next_action is not None and depth < depth_limit:
        if halt():
            break
        seat = current_state.seat()
        if next_action not in current_node.children:
            if not allocate():
                break
            child_state = current_state.step(next_action, rng)
            current_node.children[next_action] = (_Node(), child_state)
            current_node.edges[next_action] = _Edge()
            created += 1
        child_node, child_state = current_node.children[next_action]
        path.append((current_node, next_action, seat))
        current_node = child_node
        current_state = child_state
        depth += 1
        if current_state.winner() is not None or not current_state.actions():
            break
        if depth >= depth_limit or halt():
            break
        next_action, extra = _choose(current_node, current_state, rng, policy_width, allocate)
        created += extra
    if depth == 0:
        return 0.0, 0, created, False
    for parent, action, seat in path:
        edge = parent.edges[action]
        edge.visits += 1
        edge.total += _reward(current_state, seat)
        parent.visits += 1
    return _reward(current_state, root_seat), depth, created, depth >= depth_limit


def _choose(
    node: _Node,
    state: SearchState,
    rng: random.Random,
    width: int,
    allocate: Callable[[], bool],
) -> tuple[str | None, int]:
    """The seat to move tries each new Action once, then keeps what wins for them."""
    created = _grow(node, state, rng, width, allocate)
    if not node.children:
        return None, created
    seat = state.seat()
    unvisited = [action for action, edge in node.edges.items() if edge.visits == 0]
    if unvisited:
        return _best_new_action(node, unvisited, seat), created
    return _best_visited_action(node), created


def _grow(
    node: _Node,
    state: SearchState,
    rng: random.Random,
    width: int,
    allocate: Callable[[], bool],
) -> int:
    if not node.actions:
        node.actions = state.actions()
    target = min(len(node.actions), 8, max(width, 1 + int(math.sqrt(node.visits))))
    created = 0
    while len(node.children) < target:
        missing = [action for action in node.actions if action not in node.children]
        if not missing or not allocate():
            break
        if node.priors:
            missing.sort(key=lambda action: (-node.priors.get(action, 0.0), action))
            choice = missing[0]
        else:
            choice = rng.choice(missing)
        child_state = state.step(choice, rng)
        node.children[choice] = (_Node(), child_state)
        node.edges[choice] = _Edge()
        created += 1
    return created


def _best_new_action(node: _Node, actions: list[str], seat: str) -> str:
    chosen = actions[0]
    best = -1.0
    for action in actions:
        score = _reward(node.children[action][1], seat)
        if score > best or (score == best and action < chosen):
            best = score
            chosen = action
    return chosen


def _best_visited_action(node: _Node) -> str:
    chosen = next(iter(node.edges))
    best = -1.0
    log_n = math.log(node.visits + 1)
    for action, edge in node.edges.items():
        mean = edge.total / edge.visits
        score = mean + 0.7 * math.sqrt(log_n / edge.visits)
        if score > best or (score == best and action < chosen):
            best = score
            chosen = action
    return chosen


def _reward(state: SearchState, seat: str) -> float:
    winner = state.winner()
    if winner is None:
        return state.value(seat)
    return 1.0 if winner == seat else 0.0


def _select(stats: dict[str, _Stats], order: tuple[str, ...], simulations: int) -> str:
    chosen = order[0]
    best = -1.0
    log_n = math.log(simulations + 1)
    for action in order:
        row = stats[action]
        if row.visits == 0:
            score = math.inf
        else:
            mean = row.total / row.visits
            score = mean + 0.7 * math.sqrt(log_n / row.visits)
        if score > best or (score == best and action < chosen):
            best = score
            chosen = action
    return chosen


def _snapshot(
    stats: dict[str, _Stats],
    order: tuple[str, ...],
    *,
    seat: str,
    simulations: int,
    nodes: int,
    elapsed: float,
    horizon: float,
    source: Literal["immediate", "search"],
) -> Snapshot:
    scored = [
        (
            action,
            _posterior(stats[action]),
            stats[action].visits,
            _error(stats[action]),
        )
        for action in order
    ]
    best = max((probability for _, probability, _, _ in scored), default=0.0)
    ranked = sorted(scored, key=lambda row: (-row[1], row[0]))
    uncertainty = ranked[0][3] if ranked else 0.0
    return Snapshot(
        source=source,
        seat=seat,
        lines=tuple(
            Line(
                action=action,
                win_probability=probability,
                loss=best - probability,
                visits=visits,
            )
            for action, probability, visits, _ in ranked
        ),
        simulations=simulations,
        nodes=nodes,
        elapsed=elapsed,
        horizon=horizon,
        uncertainty=uncertainty,
    )


def _posterior(row: _Stats) -> float:
    if row.visits == 0:
        return row.prior
    return (row.prior + row.total) / (1 + row.visits)


def _error(row: _Stats) -> float:
    if row.visits < 2:
        return 0.0
    mean = row.total / row.visits
    variance = max(0.0, (row.sumsq - row.visits * mean * mean) / (row.visits - 1))
    return math.sqrt(variance / row.visits)


def _elapsed(clock: Callable[[], float], started: float) -> float:
    return max(0.0, clock() - started)
