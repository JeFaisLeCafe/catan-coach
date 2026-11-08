"""Anytime search: the model first, then play that can be stopped."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class Budget:
    mode: Literal["immediate", "timed", "continuous", "simulations"]
    seconds: float | None = None
    simulations: int | None = None

    def __post_init__(self) -> None:
        if self.mode == "timed" and (self.seconds is None or self.seconds <= 0):
            raise ValueError("a timed Search Budget needs a positive duration")
        if self.mode != "timed" and self.seconds is not None:
            raise ValueError("only a timed Search Budget has a duration")
        if self.mode == "simulations" and (self.simulations is None or self.simulations < 1):
            raise ValueError("a simulation Search Budget needs a positive count")
        if self.mode != "simulations" and self.simulations is not None:
            raise ValueError("only a simulation Search Budget has a count")


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

    def step(self, action: str, rng: random.Random, outcome: str | None = None) -> SearchState: ...

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
class _Roll:
    """Dice totals already tried after one roll, and the chance of every total."""

    weights: dict[str, float]
    worlds: dict[str, tuple[_Node, SearchState]]
    visits: dict[str, int] = field(default_factory=dict)


@dataclass
class _Node:
    """One reached Position. The child state is kept so a later visit is not copied again."""

    actions: tuple[str, ...] | None = None
    priors: dict[str, float] = field(default_factory=dict)
    children: dict[str, tuple[_Node, SearchState]] = field(default_factory=dict)
    rolls: dict[str, _Roll] = field(default_factory=dict)
    edges: dict[str, _Edge] = field(default_factory=dict)
    visits: int = 0


class SearchCache:
    """Completed snapshots, keyed by Position, model, and Search Budget."""

    def __init__(self) -> None:
        self._items: dict[str, Snapshot] = {}

    @staticmethod
    def key(position_id: str, model: str, budget: Budget) -> str:
        if budget.seconds is not None:
            extra = f":{budget.seconds}"
        elif budget.simulations is not None:
            extra = f":{budget.simulations}"
        else:
            extra = ""
        return f"{position_id}|{model}|{budget.mode}{extra}"

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
    max_depth: int = 200,
    policy_width: int = 3,
    max_nodes: int = 800_000,
) -> Iterator[Snapshot]:
    """Yield the model ranking, then extend a kept tree until the budget or `stop`.

    `stop` is checked before every snapshot, so a Position change drops a
    result that belongs to the Position that is already gone. The clock is
    checked between plies. The ply count advances only when every current
    move has been tried and the focused continuations have their own
    alternatives in the tree. Another look through the same roll takes a dice
    total that roll has not tried yet. The seat to move still keeps the
    continuation that wins for them.
    Once the tree cannot store another position, the search ends instead of
    replaying the positions it already has.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if policy_width < 1:
        raise ValueError("policy_width must be at least 1")
    if stop():
        return
    started = clock()
    limit = budget.seconds if budget.mode == "timed" else None
    simulation_limit = budget.simulations if budget.mode == "simulations" else None
    stats = {action: _Stats(prior=probability) for action, probability in prior}
    order = tuple(action for action, _ in prior)
    root_node = _Node(actions=order, priors=dict(prior))
    nodes = 0
    simulations = 0
    depth_limit = max_depth
    shown_depth = 1
    slots = max_nodes

    def halted() -> bool:
        if stop():
            return True
        if limit is not None and _elapsed(clock, started) >= limit:
            return True
        return simulation_limit is not None and simulations >= simulation_limit

    def allocate(count: int) -> bool:
        nonlocal slots
        if count < 1 or slots < count:
            return False
        slots -= count
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
            reward, depth, explored, _reached = _extend(
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
            if explored == 0 and _search_is_closed(slots, root_node, policy_width, max_depth):
                break
            nodes += explored
            row = stats[action]
            row.visits += 1
            row.total += reward
            row.sumsq += reward * reward
            simulations += 1
            completed += 1
        if completed == 0 or stop():
            return
        shown_depth = max(shown_depth, _span(root_node, 0, policy_width, root=True)[0])
        yield _snapshot(
            stats,
            order,
            seat=root_seat,
            simulations=simulations,
            nodes=nodes,
            elapsed=_elapsed(clock, started),
            horizon=float(shown_depth),
            source="search",
        )


@dataclass
class _Walk:
    pay: dict[str, float]
    depth: int
    created: int
    reached: bool


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
    allocate: Callable[[int], bool],
) -> tuple[float, int, int, bool]:
    walked = _follow(
        node,
        state,
        first,
        0,
        (root_seat,),
        rng,
        depth_limit=depth_limit,
        policy_width=policy_width,
        halt=halt,
        allocate=allocate,
    )
    if walked is None or walked.depth == 0:
        created = 0 if walked is None else walked.created
        return 0.0, 0, created, False
    return walked.pay[root_seat], walked.depth, walked.created, walked.reached


def _follow(
    node: _Node,
    state: SearchState,
    action: str,
    depth: int,
    seats: tuple[str, ...],
    rng: random.Random,
    *,
    depth_limit: int,
    policy_width: int,
    halt: Callable[[], bool],
    allocate: Callable[[int], bool],
) -> _Walk | None:
    if halt():
        return None
    created = _ensure(node, state, action, rng, allocate)
    if action not in node.children and action not in node.rolls:
        return _Walk({}, 0, created, False)
    depth += 1
    actor = state.seat()
    if actor not in seats:
        seats = (*seats, actor)
    roll = node.rolls.get(action)
    if roll is not None:
        opened, name = _open_outcome(roll, state, action, rng, allocate)
        created += opened
        if name is None:
            return _Walk({}, 0, created, False)
        child_node, child_state = roll.worlds[name]
        if depth >= depth_limit:
            pay = _payoffs(child_state, seats)
            deepest = depth
            reached = True
        else:
            walked = _play_on(
                child_node,
                child_state,
                depth,
                seats,
                rng,
                depth_limit=depth_limit,
                policy_width=policy_width,
                halt=halt,
                allocate=allocate,
            )
            pay = walked.pay
            deepest = walked.depth
            created += walked.created
            reached = walked.reached
    else:
        child_node, child_state = node.children[action]
        walked = _play_on(
            child_node,
            child_state,
            depth,
            seats,
            rng,
            depth_limit=depth_limit,
            policy_width=policy_width,
            halt=halt,
            allocate=allocate,
        )
        pay = walked.pay
        deepest = walked.depth
        created += walked.created
        reached = walked.reached
    edge = node.edges[action]
    edge.visits += 1
    edge.total += pay.get(actor, 0.0)
    node.visits += 1
    return _Walk(pay, deepest, created, reached)


def _play_on(
    node: _Node,
    state: SearchState,
    depth: int,
    seats: tuple[str, ...],
    rng: random.Random,
    *,
    depth_limit: int,
    policy_width: int,
    halt: Callable[[], bool],
    allocate: Callable[[int], bool],
) -> _Walk:
    """Play one action from a position that the search has already stepped into.

    The first visits fill this position's window and stop. Later visits go one
    step further, so a ply is not counted from a single unbranched line.
    """
    ended = state.winner() is not None or not state.actions()
    if ended or depth >= depth_limit:
        return _Walk(_payoffs(state, seats), depth, 0, depth >= depth_limit)
    if node.actions is None:
        node.actions = state.actions()
    if len(node.edges) < min(len(node.actions), policy_width):
        created = _grow(node, state, rng, policy_width, allocate)
        seat = state.seat()
        return _Walk(_quote(node, seats, seat, state), depth, created, False)
    chosen, created = _choose(node, state, rng, policy_width, allocate)
    if chosen is None:
        return _Walk(_payoffs(state, seats), depth, created, False)
    walked = _follow(
        node,
        state,
        chosen,
        depth,
        seats,
        rng,
        depth_limit=depth_limit,
        policy_width=policy_width,
        halt=halt,
        allocate=allocate,
    )
    if walked is None:
        return _Walk(_payoffs(state, seats), depth, created, False)
    return _Walk(walked.pay, walked.depth, created + walked.created, walked.reached)


def _open_outcome(
    roll: _Roll,
    state: SearchState,
    action: str,
    rng: random.Random,
    allocate: Callable[[int], bool],
) -> tuple[int, str | None]:
    """Step one dice total. A total already stored for this roll is not stepped again."""
    name = _next_outcome(roll)
    if name in roll.worlds:
        roll.visits[name] = roll.visits.get(name, 0) + 1
        return 0, name
    if not allocate(1):
        return 0, None
    child_state = state.step(action, rng, name)
    roll.worlds[name] = (_Node(actions=child_state.actions()), child_state)
    roll.visits[name] = 1
    return 1, name


def _next_outcome(roll: _Roll) -> str:
    missing = [name for name in roll.weights if name not in roll.worlds]
    if missing:
        missing.sort(key=lambda name: (-roll.weights[name], name))
        return missing[0]
    return min(
        roll.worlds,
        key=lambda name: (roll.visits.get(name, 0) / roll.weights[name], -roll.weights[name], name),
    )


def _ensure(
    node: _Node,
    state: SearchState,
    action: str,
    rng: random.Random,
    allocate: Callable[[int], bool],
) -> int:
    if action in node.children or action in node.rolls:
        return 0
    outcomes = _chance(state, action)
    if outcomes is not None:
        node.rolls[action] = _Roll(_weights(outcomes), {})
        node.edges[action] = _Edge()
        return 0
    if not allocate(1):
        return 0
    child_state = state.step(action, rng)
    node.children[action] = (_Node(actions=child_state.actions()), child_state)
    node.edges[action] = _Edge()
    return 1


def _chance(state: SearchState, action: str) -> tuple[tuple[str, float], ...] | None:
    method = getattr(state, "outcomes", None)
    if method is None:
        return None
    found = method(action)
    if not found:
        return None
    return tuple((str(name), float(weight)) for name, weight in found)


def _weights(outcomes: tuple[tuple[str, float], ...]) -> dict[str, float]:
    total = sum(weight for _, weight in outcomes)
    if total <= 0:
        share = 1.0 / len(outcomes)
        return {name: share for name, _ in outcomes}
    return {name: weight / total for name, weight in outcomes}


def _choose(
    node: _Node,
    state: SearchState,
    rng: random.Random,
    width: int,
    allocate: Callable[[int], bool],
) -> tuple[str | None, int]:
    """The seat to move tries each new Action once, then keeps what wins for them."""
    created = _grow(node, state, rng, width, allocate)
    if not node.edges:
        return None, created
    seat = state.seat()
    unvisited = [action for action, edge in node.edges.items() if edge.visits == 0]
    if unvisited:
        return _best_new_action(node, unvisited, seat, state), created
    return _best_visited_action(node), created


def _grow(
    node: _Node,
    state: SearchState,
    rng: random.Random,
    width: int,
    allocate: Callable[[int], bool],
) -> int:
    if node.actions is None:
        node.actions = state.actions()
    actions = node.actions
    target = min(len(actions), width)
    created = 0
    expanded = set(node.children) | set(node.rolls)
    while len(expanded) < target:
        missing = [action for action in actions if action not in expanded]
        if not missing:
            break
        if node.priors:
            missing.sort(key=lambda action: (-node.priors.get(action, 0.0), action))
            choice = missing[0]
        else:
            choice = rng.choice(missing)
        added = _ensure(node, state, choice, rng, allocate)
        if choice not in node.children and choice not in node.rolls:
            break
        expanded.add(choice)
        created += added
    return created


def _best_new_action(node: _Node, actions: list[str], seat: str, state: SearchState) -> str:
    chosen = actions[0]
    best = -1.0
    for action in actions:
        score = _lookahead(node, action, seat, state)
        if score > best or (score == best and action < chosen):
            best = score
            chosen = action
    return chosen


def _lookahead(node: _Node, action: str, seat: str, state: SearchState) -> float:
    roll = node.rolls.get(action)
    if roll is None:
        return _reward(node.children[action][1], seat)
    if not roll.worlds:
        return _reward(state, seat)
    return _blend_roll(roll, (seat,))[seat]


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


def _quote(node: _Node, seats: tuple[str, ...], seat: str, state: SearchState) -> dict[str, float]:
    """Value a freshly filled window by the action that seat would keep."""
    everyone = seats if seat in seats else (*seats, seat)
    if not node.edges:
        return {name: 0.0 for name in everyone}
    for action, edge in node.edges.items():
        if edge.visits == 0:
            quoted = _quoted_pay(node, action, everyone, state)
            edge.visits = 1
            edge.total = quoted.get(seat, 0.0)
    return _quoted_pay(node, _best_visited_action(node), everyone, state)


def _quoted_pay(
    node: _Node, action: str, seats: tuple[str, ...], state: SearchState
) -> dict[str, float]:
    roll = node.rolls.get(action)
    if roll is None:
        return _payoffs(node.children[action][1], seats)
    if not roll.worlds:
        return _payoffs(state, seats)
    return _blend_roll(roll, seats)


def _blend_roll(roll: _Roll, seats: tuple[str, ...]) -> dict[str, float]:
    total = sum(roll.weights[name] for name in roll.worlds)
    combined = {seat: 0.0 for seat in seats}
    if total <= 0:
        return combined
    for name, (_child, child_state) in roll.worlds.items():
        share = roll.weights[name] / total
        part = _payoffs(child_state, seats)
        for seat in seats:
            combined[seat] += share * part[seat]
    return combined


def _search_is_closed(slots: int, root: _Node, width: int, max_depth: int) -> bool:
    if slots <= 0:
        return True
    return _span(root, 0, width, root=True)[0] >= max_depth


def _span(node: _Node, depth: int, width: int, *, root: bool) -> tuple[int, bool]:
    """How far this window is filled, and whether every focused line has ended."""
    if node.actions is None:
        return depth, False
    if len(node.actions) == 0:
        return depth, True
    needed = len(node.actions) if root else min(len(node.actions), width)
    if len(node.edges) < needed:
        return depth, False
    focus = _focus(node, width) if root else tuple(node.edges)
    spans = [_edge_span(node, action, depth + 1, width) for action in focus]
    live = [item for item in spans if not item[1]]
    if live:
        return min(item[0] for item in live), False
    return max((item[0] for item in spans), default=depth), True


def _edge_span(node: _Node, action: str, depth: int, width: int) -> tuple[int, bool]:
    roll = node.rolls.get(action)
    if roll is None:
        child, _state = node.children[action]
        return _span(child, depth, width, root=False)
    if not roll.worlds:
        return depth, False
    spans = [_span(child, depth, width, root=False) for child, _state in roll.worlds.values()]
    live = [item for item in spans if not item[1]]
    if live:
        return min(item[0] for item in live), False
    return max((item[0] for item in spans), default=depth), True


def _focus(node: _Node, width: int) -> tuple[str, ...]:
    ranked = sorted(node.edges, key=lambda action: (-_mean(node.edges[action]), action))
    return tuple(ranked[:width])


def _mean(edge: _Edge) -> float:
    if edge.visits == 0:
        return 0.0
    return edge.total / edge.visits


def _payoffs(state: SearchState, seats: tuple[str, ...]) -> dict[str, float]:
    return {seat: _reward(state, seat) for seat in seats}


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
