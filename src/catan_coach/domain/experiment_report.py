"""Game-level Strength Reports and Intervention Comparisons.

Games are the observations. Plies, Positions, and Seat rows never enter a
proportion. A report can be incomplete; it must not invent a strength claim.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, fields, is_dataclass

import numpy as np

from catan_coach.domain.experiment import (
    BehaviorProfile,
    CompletedGame,
    DroppedGame,
    ExperimentPlan,
    ScheduledGame,
    TechnicalFailure,
)

_Z = 1.959963984540054
_BOOTSTRAP_REPLICATES = 10_000
_DROP_LIMIT = 0.01

Outcome = CompletedGame | DroppedGame


@dataclass(frozen=True, slots=True)
class Proportion:
    successes: int
    count: int
    rate: float | None
    lower: float | None
    upper: float | None


@dataclass(frozen=True, slots=True)
class BehaviorAggregate:
    games: int
    initial_resources: float | None
    initial_pips: float | None
    adjacent_port_rate: float | None
    settlements: float | None
    cities: float | None
    roads: float | None
    development_cards: float | None
    knights: float | None
    offers: float | None
    acceptances: float | None
    completed_trades: float | None
    maritime_trades: float | None
    longest_road_rate: float | None
    largest_army_rate: float | None
    public_victory_points: float | None
    actual_victory_points: float | None
    first_build: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class SeatReport:
    seat: int
    completed: int
    wins: int
    dropped: int
    terminal_failures: int
    missing: int
    proportion: Proportion


@dataclass(frozen=True, slots=True)
class PolicySettings:
    name: str
    kind: str
    search_simulations: int
    explore: bool
    model_hash: str | None
    sidecar_hash: str | None
    preferences: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    plan_name: str
    candidate: PolicySettings
    opponent: PolicySettings
    map_policy: str
    base_seed: int
    games_per_candidate_seat: int
    vps_to_win: int
    discard_limit: int
    friendly_robber: bool
    turn_limit: int
    source_commit: str
    source_dirty: bool
    scheduled: int
    completed: int
    dropped: int
    terminal_failures: int
    missing: int
    valid: bool
    wins: Proportion
    attrition_as_losses: Proportion
    attrition_as_wins: Proportion
    seats: tuple[SeatReport, ...]
    candidate_victory_points: tuple[tuple[int, int], ...]
    candidate_victory_point_mean: float | None
    opponent_victory_points: tuple[tuple[int, int], ...]
    opponent_victory_point_mean: float | None
    candidate_wins: BehaviorAggregate
    candidate_losses: BehaviorAggregate
    opponents: BehaviorAggregate
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffectEstimate:
    pairs: int
    difference: float
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class VariantComparison:
    name: str
    preferences: tuple[tuple[str, float], ...]
    completed_pairs: int
    unresolved_pairs: int
    valid: bool
    claim: str
    estimate: EffectEstimate
    lower_bound: EffectEstimate
    upper_bound: EffectEstimate
    seats: tuple[tuple[int, EffectEstimate], ...]
    behavior_deltas: tuple[tuple[str, float], ...]
    dropped_reference: int
    dropped_variant: int
    terminal_reference: int
    terminal_variant: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InterventionReport:
    reference_name: str
    opponent_name: str
    seed: int
    replicates: int
    variants: tuple[VariantComparison, ...]


def wilson(successes: int, count: int) -> Proportion:
    """Two-sided 95% Wilson interval for `successes` events in `count` games."""
    if count < 0 or successes < 0 or successes > count:
        raise ValueError("Wilson inputs must satisfy 0 <= successes <= count")
    if count == 0:
        return Proportion(0, 0, None, None, None)
    probability = successes / count
    z2 = _Z * _Z
    denominator = 1.0 + z2 / count
    center = (probability + z2 / (2.0 * count)) / denominator
    margin = (
        _Z
        * math.sqrt(probability * (1.0 - probability) / count + z2 / (4.0 * count * count))
        / denominator
    )
    return Proportion(
        successes,
        count,
        probability,
        max(0.0, center - margin),
        min(1.0, center + margin),
    )


def summarize(
    plan: ExperimentPlan,
    scheduled: Sequence[ScheduledGame],
    outcomes: Sequence[Outcome],
    failures: Sequence[TechnicalFailure],
) -> ExperimentReport:
    by_key = _index_schedule(scheduled)
    finished = _index_outcomes(outcomes, by_key)
    attempts = _index_failures(failures, by_key)
    completed = [game for game in finished.values() if isinstance(game, CompletedGame)]
    dropped = [game for game in finished.values() if isinstance(game, DroppedGame)]
    terminal = {
        key
        for key, tries in attempts.items()
        if any(failure.attempt == 2 for failure in tries) and key not in finished
    }
    missing = [key for key in by_key if key not in finished]
    wins = sum(1 for game in completed if _candidate_won(game))
    scheduled_count = len(by_key)
    unresolved = scheduled_count - len(completed)
    drop_rate = len(dropped) / scheduled_count if scheduled_count else 1.0
    warnings: list[str] = []
    if missing:
        warnings.append(f"{len(missing)} scheduled games have no result")
    if terminal:
        warnings.append(f"{len(terminal)} games failed on both attempts")
    if drop_rate > _DROP_LIMIT:
        warnings.append("dropped games exceed 1% of the schedule")
    seats: list[SeatReport] = []
    for seat in range(4):
        seat_games = [game for game in by_key.values() if game.candidate_seat == seat]
        seat_keys = {game.result_key for game in seat_games}
        seat_completed = [game for game in completed if game.candidate_seat == seat]
        seat_wins = sum(1 for game in seat_completed if _candidate_won(game))
        seat_dropped = sum(1 for game in dropped if game.candidate_seat == seat)
        seat_terminal = len(terminal & seat_keys)
        seat_missing = sum(1 for key in missing if by_key[key].candidate_seat == seat)
        if not seat_completed:
            warnings.append(f"Seat {seat} has no completed games")
        seats.append(
            SeatReport(
                seat,
                len(seat_completed),
                seat_wins,
                seat_dropped,
                seat_terminal,
                seat_missing,
                wilson(seat_wins, len(seat_completed)),
            )
        )
    candidate_points = [_candidate_points(game) for game in completed]
    opponent_points = [
        seat.profile.actual_victory_points
        for game in completed
        for seat in game.seats
        if seat.seat_index != game.candidate_seat
    ]
    valid = not terminal and drop_rate <= _DROP_LIMIT and not missing and scheduled_count > 0
    return ExperimentReport(
        plan_name=plan.name,
        candidate=_settings(plan.candidate),
        opponent=_settings(plan.opponent),
        map_policy=plan.map_policy,
        base_seed=plan.base_seed,
        games_per_candidate_seat=plan.games_per_candidate_seat,
        vps_to_win=plan.rules.vps_to_win,
        discard_limit=plan.rules.discard_limit,
        friendly_robber=plan.rules.friendly_robber,
        turn_limit=plan.rules.turn_limit,
        source_commit=plan.source.commit,
        source_dirty=plan.source.dirty,
        scheduled=scheduled_count,
        completed=len(completed),
        dropped=len(dropped),
        terminal_failures=len(terminal),
        missing=len(missing),
        valid=valid,
        wins=wilson(wins, len(completed)),
        attrition_as_losses=wilson(wins, scheduled_count),
        attrition_as_wins=wilson(wins + unresolved, scheduled_count),
        seats=tuple(seats),
        candidate_victory_points=_distribution(candidate_points),
        candidate_victory_point_mean=_mean(candidate_points),
        opponent_victory_points=_distribution(opponent_points),
        opponent_victory_point_mean=_mean(opponent_points),
        candidate_wins=_aggregate(
            [_candidate_profile(game) for game in completed if _candidate_won(game)]
        ),
        candidate_losses=_aggregate(
            [_candidate_profile(game) for game in completed if not _candidate_won(game)]
        ),
        opponents=_aggregate(
            [
                seat.profile
                for game in completed
                for seat in game.seats
                if seat.seat_index != game.candidate_seat
            ]
        ),
        warnings=tuple(warnings),
    )


def compare(
    reference: ExperimentPlan,
    variants: Sequence[ExperimentPlan],
    schedules: Sequence[Sequence[ScheduledGame]],
    outcomes: Sequence[Sequence[Outcome]],
    failures: Sequence[Sequence[TechnicalFailure]],
    *,
    seed: int,
) -> InterventionReport:
    """Paired difference of each variant against the reference plan.

    `schedules`, `outcomes`, and `failures` are aligned: index 0 is the
    reference and each later index is the variant in the same position.
    """
    if not variants:
        raise ValueError("an Intervention Comparison needs at least one variant")
    if len(schedules) != len(variants) + 1 or len(outcomes) != len(schedules):
        raise ValueError("schedules and outcomes must include the reference and every variant")
    if len(failures) != len(schedules):
        raise ValueError("failures must include the reference and every variant")
    reference_schedule = _index_schedule(schedules[0])
    compared: list[VariantComparison] = []
    for index, variant in enumerate(variants, start=1):
        _require_compatible(reference, variant, reference_schedule, schedules[index])
        compared.append(
            _compare_variant(
                variant,
                reference_schedule,
                _index_schedule(schedules[index]),
                outcomes[0],
                outcomes[index],
                failures[0],
                failures[index],
                seed,
            )
        )
    return InterventionReport(
        reference.name,
        reference.opponent.name,
        seed,
        _BOOTSTRAP_REPLICATES,
        tuple(compared),
    )


def report_to_json(report: ExperimentReport | InterventionReport) -> dict[str, object]:
    return _jsonable(report)  # type: ignore[return-value]


def format_report(report: ExperimentReport) -> str:
    rate = _percent(report.wins.rate)
    interval = _interval(report.wins)
    population = report.opponent.name
    lines = [
        (
            f"{report.candidate.name} won {rate} of completed games against {population} "
            f"({interval}, {report.wins.successes}/{report.wins.count} games)."
        ),
        (
            "This is a seat-balanced win rate against that Opponent Population. "
            "It is not a rating against every player."
        ),
        "",
        "## Seat",
    ]
    for seat in report.seats:
        lines.append(
            f"- Seat {seat.seat}: {_percent(seat.proportion.rate)} "
            f"({_interval(seat.proportion)}, {seat.wins}/{seat.completed} completed, "
            f"{seat.dropped} dropped, {seat.terminal_failures} failed, {seat.missing} missing)"
        )
    lines.extend(
        [
            "",
            "## Failures",
            (
                f"{report.completed} completed, {report.dropped} dropped, "
                f"{report.terminal_failures} terminal failures, {report.missing} missing, "
                f"out of {report.scheduled} scheduled."
            ),
            (
                "Attrition as losses: "
                f"{_percent(report.attrition_as_losses.rate)} "
                f"({_interval(report.attrition_as_losses)})."
            ),
            (
                "Attrition as wins: "
                f"{_percent(report.attrition_as_wins.rate)} "
                f"({_interval(report.attrition_as_wins)})."
            ),
            "Valid for a strength claim." if report.valid else "Not valid for a strength claim.",
            "",
            "## Behavior",
            "Descriptive association only; this does not show that the behavior caused wins.",
            "Candidate wins "
            f"({report.candidate_wins.games} games): {_behavior_line(report.candidate_wins)}",
            (
                f"Candidate losses ({report.candidate_losses.games} games): "
                f"{_behavior_line(report.candidate_losses)}"
            ),
            (
                f"Opponents ({report.opponents.games} seats in completed games): "
                f"{_behavior_line(report.opponents)}"
            ),
            "",
            "## Provenance",
            (
                f"{report.candidate.name} kind={report.candidate.kind} "
                f"search={report.candidate.search_simulations} explore={report.candidate.explore} "
                f"model={report.candidate.model_hash} sidecar={report.candidate.sidecar_hash}"
            ),
            (
                f"{report.opponent.name} kind={report.opponent.kind} "
                f"search={report.opponent.search_simulations} explore={report.opponent.explore}"
            ),
            (
                f"map={report.map_policy} base_seed={report.base_seed} "
                f"games_per_seat={report.games_per_candidate_seat} "
                f"vp={report.vps_to_win} discard={report.discard_limit} "
                f"friendly_robber={report.friendly_robber} turn_limit={report.turn_limit}"
            ),
            f"source={report.source_commit} dirty={report.source_dirty}",
        ]
    )
    if report.warnings:
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in report.warnings]])
    return "\n".join(lines) + "\n"


def format_comparison(report: InterventionReport) -> str:
    lines = [
        (
            f"Intervention against {report.reference_name}, "
            f"Opponent Population {report.opponent_name}."
        ),
        (
            "This Intervention estimates an effect inside the declared simulator and "
            "Opponent Population. It is not automatically a causal claim about human games."
        ),
        "",
    ]
    for variant in report.variants:
        preference = ", ".join(f"{name} {delta:+.2f}" for name, delta in variant.preferences)
        lines.extend(
            [
                f"## {variant.name}: {preference or 'no preference'}",
                (
                    f"Win-rate difference {variant.estimate.difference:+.4f} "
                    f"({variant.estimate.lower:+.4f} to {variant.estimate.upper:+.4f}, "
                    f"{variant.completed_pairs} completed pairs)."
                ),
                (
                    f"Worst-case lower bound {variant.lower_bound.difference:+.4f} "
                    f"({variant.lower_bound.lower:+.4f} to {variant.lower_bound.upper:+.4f})."
                ),
                (
                    f"Worst-case upper bound {variant.upper_bound.difference:+.4f} "
                    f"({variant.upper_bound.lower:+.4f} to {variant.upper_bound.upper:+.4f})."
                ),
                f"Claim: {variant.claim}.",
                (
                    "Valid for an effect claim."
                    if variant.valid
                    else "Not valid for an effect claim."
                ),
                (
                    f"Dropped {variant.dropped_reference} reference, "
                    f"{variant.dropped_variant} variant. "
                    f"Terminal failures {variant.terminal_reference} reference, "
                    f"{variant.terminal_variant} variant."
                ),
                "Descriptive association only; this does not show that the behavior caused wins.",
            ]
        )
        if variant.seats:
            lines.extend(
                f"- Seat {seat}: {estimate.difference:+.4f} "
                f"({estimate.lower:+.4f} to {estimate.upper:+.4f}, {estimate.pairs} pairs)"
                for seat, estimate in variant.seats
            )
        else:
            lines.append("- No Seat has a completed pair.")
        if variant.behavior_deltas:
            changes = ", ".join(f"{name} {delta:+.2f}" for name, delta in variant.behavior_deltas)
            lines.append(f"Behavior change per completed pair: {changes}.")
        else:
            lines.append("Behavior change per completed pair: none.")
        lines.extend(f"- {warning}" for warning in variant.warnings)
    return "\n".join(lines) + "\n"


def _compare_variant(
    variant: ExperimentPlan,
    reference_schedule: dict[str, ScheduledGame],
    variant_schedule: dict[str, ScheduledGame],
    reference_outcomes: Sequence[Outcome],
    variant_outcomes: Sequence[Outcome],
    reference_failures: Sequence[TechnicalFailure],
    variant_failures: Sequence[TechnicalFailure],
    seed: int,
) -> VariantComparison:
    reference_by_pair = {game.pairing_key: game for game in reference_schedule.values()}
    variant_by_pair = {game.pairing_key: game for game in variant_schedule.values()}
    if set(reference_by_pair) != set(variant_by_pair):
        raise ValueError("variant pairing keys do not match the reference schedule")
    reference_done = _index_outcomes(reference_outcomes, reference_schedule)
    variant_done = _index_outcomes(variant_outcomes, variant_schedule)
    reference_attempts = _index_failures(reference_failures, reference_schedule)
    variant_attempts = _index_failures(variant_failures, variant_schedule)
    keys = tuple(reference_by_pair)
    completed_pairs = []
    assigned_lower: list[float] = []
    assigned_upper: list[float] = []
    seats: dict[int, list[float]] = {seat: [] for seat in range(4)}
    behavior_left: list[BehaviorProfile] = []
    behavior_right: list[BehaviorProfile] = []
    unresolved = 0
    for key in keys:
        seat = reference_by_pair[key].candidate_seat
        left = reference_done.get(reference_by_pair[key].result_key)
        right = variant_done.get(variant_by_pair[key].result_key)
        left_win = _resolved_win(left)
        right_win = _resolved_win(right)
        if left_win is None or right_win is None:
            unresolved += 1
        else:
            difference = float(right_win) - float(left_win)
            completed_pairs.append(difference)
            seats[seat].append(difference)
            assert isinstance(left, CompletedGame) and isinstance(right, CompletedGame)
            behavior_left.append(_candidate_profile(left))
            behavior_right.append(_candidate_profile(right))
        assigned_lower.append(float(right_win or 0) - float(1 if left_win is None else left_win))
        assigned_upper.append(float(1 if right_win is None else right_win) - float(left_win or 0))
    if not keys:
        raise ValueError("a comparison needs at least one pairing key")
    if not completed_pairs:
        raise ValueError("a comparison needs at least one completed pair")
    estimate = _bootstrap(completed_pairs, seed)
    lower = _bootstrap(assigned_lower, seed)
    upper = _bootstrap(assigned_upper, seed + 1)
    seat_estimates = tuple(
        (seat, _bootstrap(values, seed + 2 + seat)) for seat, values in seats.items() if values
    )
    dropped_reference = sum(isinstance(game, DroppedGame) for game in reference_done.values())
    dropped_variant = sum(isinstance(game, DroppedGame) for game in variant_done.values())
    terminal_reference = _terminal_count(reference_attempts, reference_done)
    terminal_variant = _terminal_count(variant_attempts, variant_done)
    scheduled = len(keys)
    valid = (
        terminal_reference == 0
        and terminal_variant == 0
        and dropped_reference / scheduled <= _DROP_LIMIT
        and dropped_variant / scheduled <= _DROP_LIMIT
    )
    claim = "none"
    if valid and lower.lower > 0:
        claim = "positive"
    elif valid and upper.upper < 0:
        claim = "negative"
    warnings: list[str] = []
    if not valid:
        warnings.append("comparison is not valid for an effect claim")
    if unresolved:
        warnings.append(f"{unresolved} pairing keys are unresolved on at least one side")
    return VariantComparison(
        variant.name,
        tuple((item.category, item.delta) for item in variant.candidate.declared_preferences),
        len(completed_pairs),
        unresolved,
        valid,
        claim,
        estimate,
        lower,
        upper,
        seat_estimates,
        _behavior_delta(behavior_left, behavior_right),
        dropped_reference,
        dropped_variant,
        terminal_reference,
        terminal_variant,
        tuple(warnings),
    )


def _bootstrap(values: Sequence[float], seed: int) -> EffectEstimate:
    if not values:
        raise ValueError("a paired bootstrap needs at least one pairing key")
    observed = float(np.mean(np.asarray(values, dtype=np.float64)))
    if len(values) == 1 or all(value == values[0] for value in values):
        return EffectEstimate(len(values), observed, observed, observed)
    generator = np.random.Generator(np.random.PCG64(seed))
    sample = np.asarray(values, dtype=np.float64)
    draws = generator.integers(0, len(sample), size=(_BOOTSTRAP_REPLICATES, len(sample)))
    means = sample[draws].mean(axis=1)
    lower, upper = np.quantile(means, (0.025, 0.975), method="linear")
    return EffectEstimate(len(values), observed, float(lower), float(upper))


def _changed_preferences(reference: ExperimentPlan, variant: ExperimentPlan) -> tuple[str, ...]:
    left = {item.category: item.delta for item in reference.candidate.declared_preferences}
    right = {item.category: item.delta for item in variant.candidate.declared_preferences}
    return tuple(
        category
        for category in dict.fromkeys((*left, *right))
        if left.get(category) != right.get(category)
    )


def _require_compatible(
    reference: ExperimentPlan,
    variant: ExperimentPlan,
    reference_schedule: dict[str, ScheduledGame],
    variant_games: Sequence[ScheduledGame],
) -> None:
    mismatches: list[str] = []
    if reference.opponent != variant.opponent:
        mismatches.append("opponent")
    if reference.rules != variant.rules:
        mismatches.append("rules")
    if reference.map_policy != variant.map_policy:
        mismatches.append("map_policy")
    if reference.base_seed != variant.base_seed:
        mismatches.append("base_seed")
    if reference.games_per_candidate_seat != variant.games_per_candidate_seat:
        mismatches.append("games_per_candidate_seat")
    if reference.source != variant.source:
        mismatches.append("source")
    if reference.candidate.kind != variant.candidate.kind:
        mismatches.append("candidate.kind")
    if reference.candidate.model_hash != variant.candidate.model_hash:
        mismatches.append("candidate.model_hash")
    if reference.candidate.sidecar_hash != variant.candidate.sidecar_hash:
        mismatches.append("candidate.sidecar_hash")
    if reference.candidate.search_simulations != variant.candidate.search_simulations:
        mismatches.append("candidate.search_simulations")
    if reference.candidate.explore != variant.candidate.explore:
        mismatches.append("candidate.explore")
    if reference.candidate.search_simulations > 0 and variant.candidate.declared_preferences:
        mismatches.append("preferences with search")
    if len(_changed_preferences(reference, variant)) != 1:
        mismatches.append("preferences")
    by_pair = {game.pairing_key: game for game in variant_games}
    if set(by_pair) != {game.pairing_key for game in reference_schedule.values()}:
        mismatches.append("pairing_key")
    else:
        for key, game in reference_schedule.items():
            other = by_pair[game.pairing_key]
            if other.seed != game.seed or other.candidate_seat != game.candidate_seat:
                mismatches.append(f"schedule[{key}]")
                break
    if mismatches:
        raise ValueError("incompatible Intervention plans: " + ", ".join(mismatches))


def _index_schedule(scheduled: Sequence[ScheduledGame]) -> dict[str, ScheduledGame]:
    indexed: dict[str, ScheduledGame] = {}
    for game in scheduled:
        if game.result_key in indexed:
            raise ValueError(f"duplicate scheduled result key {game.result_key}")
        indexed[game.result_key] = game
    return indexed


def _index_outcomes(
    outcomes: Sequence[Outcome], schedule: dict[str, ScheduledGame]
) -> dict[str, Outcome]:
    indexed: dict[str, Outcome] = {}
    for game in outcomes:
        scheduled = schedule.get(game.result_key)
        if scheduled is None:
            raise ValueError(f"result {game.result_key} is not in the schedule")
        if game.result_key in indexed:
            raise ValueError(f"duplicate result {game.result_key}")
        if (
            game.pairing_key != scheduled.pairing_key
            or game.candidate_seat != scheduled.candidate_seat
        ):
            raise ValueError(f"result {game.result_key} does not match its scheduled game")
        indexed[game.result_key] = game
    return indexed


def _index_failures(
    failures: Sequence[TechnicalFailure], schedule: dict[str, ScheduledGame]
) -> dict[str, tuple[TechnicalFailure, ...]]:
    grouped: dict[str, list[TechnicalFailure]] = {}
    for failure in failures:
        if failure.result_key not in schedule:
            raise ValueError(f"failure {failure.result_key} is not in the schedule")
        if failure.pairing_key != schedule[failure.result_key].pairing_key:
            raise ValueError(f"failure {failure.result_key} does not match its pairing key")
        grouped.setdefault(failure.result_key, []).append(failure)
    indexed: dict[str, tuple[TechnicalFailure, ...]] = {}
    for key, attempts in grouped.items():
        numbers = [failure.attempt for failure in attempts]
        if len(numbers) != len(set(numbers)) or numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"failure attempts for {key} are duplicated or out of order")
        indexed[key] = tuple(attempts)
    return indexed


def _terminal_count(
    attempts: dict[str, tuple[TechnicalFailure, ...]], done: dict[str, Outcome]
) -> int:
    return sum(
        any(failure.attempt == 2 for failure in tries) and key not in done
        for key, tries in attempts.items()
    )


def _resolved_win(game: Outcome | None) -> int | None:
    if not isinstance(game, CompletedGame):
        return None
    return int(_candidate_won(game))


def _candidate_won(game: CompletedGame) -> bool:
    return game.seats[game.candidate_seat].profile.won


def _candidate_points(game: CompletedGame) -> int:
    return game.seats[game.candidate_seat].profile.actual_victory_points


def _candidate_profile(game: CompletedGame) -> BehaviorProfile:
    return game.seats[game.candidate_seat].profile


def _settings(policy: object) -> PolicySettings:
    from catan_coach.domain.experiment import FrozenPolicySpec

    if not isinstance(policy, FrozenPolicySpec):
        raise TypeError("expected a frozen Policy")
    return PolicySettings(
        policy.name,
        policy.kind,
        policy.search_simulations,
        policy.explore,
        policy.model_hash,
        policy.sidecar_hash,
        tuple((item.category, item.delta) for item in policy.declared_preferences),
    )


def _distribution(values: Sequence[int]) -> tuple[tuple[int, int], ...]:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items()))


def _mean(values: Sequence[int]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _aggregate(profiles: Sequence[BehaviorProfile]) -> BehaviorAggregate:
    if not profiles:
        return BehaviorAggregate(
            0,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (),
        )
    count = len(profiles)
    first: dict[str, int] = {}
    for profile in profiles:
        label = profile.counts.first_build or "none"
        first[label] = first.get(label, 0) + 1

    def average(selector: object) -> float:
        assert callable(selector)
        return float(sum(selector(profile) for profile in profiles) / count)

    return BehaviorAggregate(
        count,
        average(lambda profile: profile.counts.initial_resources),
        average(lambda profile: profile.counts.initial_pips),
        average(lambda profile: float(profile.counts.adjacent_port)),
        average(lambda profile: profile.counts.settlements),
        average(lambda profile: profile.counts.cities),
        average(lambda profile: profile.counts.roads),
        average(lambda profile: profile.counts.development_cards),
        average(lambda profile: profile.counts.knights),
        average(lambda profile: profile.counts.offers),
        average(lambda profile: profile.counts.acceptances),
        average(lambda profile: profile.counts.completed_trades),
        average(lambda profile: profile.counts.maritime_trades),
        average(lambda profile: float(profile.longest_road)),
        average(lambda profile: float(profile.largest_army)),
        average(lambda profile: profile.public_victory_points),
        average(lambda profile: profile.actual_victory_points),
        tuple(sorted(first.items())),
    )


def _behavior_delta(
    reference: Sequence[BehaviorProfile], variant: Sequence[BehaviorProfile]
) -> tuple[tuple[str, float], ...]:
    if not reference:
        return ()
    left = _aggregate(reference)
    right = _aggregate(variant)
    names = (
        "settlements",
        "cities",
        "roads",
        "development_cards",
        "knights",
        "offers",
        "acceptances",
        "completed_trades",
        "maritime_trades",
        "initial_pips",
        "longest_road_rate",
        "largest_army_rate",
    )
    return tuple(
        (name, float(getattr(right, name) - getattr(left, name)))
        for name in names
        if getattr(left, name) is not None and getattr(right, name) is not None
    )


def _behavior_line(aggregate: BehaviorAggregate) -> str:
    if aggregate.games == 0:
        return "no games"
    return (
        f"settlements {aggregate.settlements:.2f}, cities {aggregate.cities:.2f}, "
        f"roads {aggregate.roads:.2f}, development cards {aggregate.development_cards:.2f} "
        f"per game"
    )


def _percent(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.1f}%"


def _interval(proportion: Proportion) -> str:
    if proportion.lower is None or proportion.upper is None:
        return "no interval"
    return f"95% Wilson {proportion.lower * 100:.1f}% to {proportion.upper * 100:.1f}%"


def _jsonable(value: object) -> object:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("report JSON cannot contain NaN or infinity")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    raise TypeError(f"cannot serialize {type(value).__name__}")
