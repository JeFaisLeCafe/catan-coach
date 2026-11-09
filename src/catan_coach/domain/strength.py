"""Game-level win rate for one candidate rotated through every Seat.

Games are the observations. Unfinished games stay out of the completed-game
rate and re-enter the attrition check as losses, and again as wins. A short
sample is labelled exploratory and is not the preregistered decision.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from catan_coach.domain.dice import summarize_rolls

# Two-sided 95% standard-normal quantile, Φ^{-1}(0.975).
_Z_95 = 1.959963984540054

FAIR_SHARE = 0.25
PREREGISTERED_GAMES = 2_000
BASE_SEED = 20_000
SEATS = ("RED", "BLUE", "WHITE", "ORANGE")
_DROP_LIMIT = 0.01

Conclusion = Literal["beats", "loses", "inconclusive", "invalid"]


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class Proportion:
    wins: int
    games: int
    win_rate: float | None
    interval: WilsonInterval | None


@dataclass(frozen=True, slots=True)
class SeatStrength:
    seat: str
    wins: int
    games_completed: int
    unfinished: int
    win_rate: float | None
    interval: WilsonInterval | None


@dataclass(frozen=True, slots=True)
class GameRecord:
    seed: int
    candidate_seat: str
    winner_seat: str | None
    turn_count: int
    rolls: tuple[int, ...] | None

    def __post_init__(self) -> None:
        if self.candidate_seat not in SEATS:
            raise ValueError(f"unknown candidate seat {self.candidate_seat}")
        if self.winner_seat is not None and self.winner_seat not in SEATS:
            raise ValueError(f"unknown winner seat {self.winner_seat}")
        if self.turn_count < 0:
            raise ValueError("turn_count must be non-negative")
        if self.rolls is not None:
            summarize_rolls(self.rolls)


@dataclass(frozen=True, slots=True)
class StrengthReport:
    wins: int
    games_completed: int
    unfinished: int
    win_rate: float | None
    interval: WilsonInterval | None
    by_seat: tuple[SeatStrength, ...]
    attrition_as_losses: Proportion
    attrition_as_wins: Proportion


def wilson_interval(wins: int, games: int) -> WilsonInterval:
    """Two-sided 95% Wilson score interval.

    With ``p = wins / games`` and ``z = 1.959963984540054``:

        center = (p + z² / (2n)) / (1 + z² / n)
        half = z / (1 + z² / n) * sqrt(p(1 - p) / n + z² / (4n²))

    Bounds are clipped to [0, 1]. No games leaves the interval undefined.
    """
    if isinstance(wins, bool) or isinstance(games, bool):
        raise ValueError("wins and games must be integers")
    if not isinstance(wins, int) or not isinstance(games, int):
        raise ValueError("wins and games must be integers")
    if games < 1:
        raise ValueError("Wilson interval needs at least one game")
    if wins < 0 or wins > games:
        raise ValueError("wins must lie between 0 and the number of games")
    probability = wins / games
    z2 = _Z_95 * _Z_95
    denominator = 1.0 + z2 / games
    center = (probability + z2 / (2.0 * games)) / denominator
    margin = (_Z_95 / denominator) * math.sqrt(
        probability * (1.0 - probability) / games + z2 / (4.0 * games * games)
    )
    return WilsonInterval(max(0.0, center - margin), min(1.0, center + margin))


def candidate_seat_for_seed(seed: int, *, base_seed: int = BASE_SEED) -> str:
    """Rotate RED, BLUE, WHITE, ORANGE once per seed, starting at ``base_seed``."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if seed < base_seed:
        raise ValueError(f"seed {seed} is before base seed {base_seed}")
    return SEATS[(seed - base_seed) % len(SEATS)]


def strength_report(games: Sequence[GameRecord]) -> StrengthReport:
    """Aggregate candidate wins. Rolls are ignored, so a dice flag cannot drop a game."""
    completed = [game for game in games if game.winner_seat is not None]
    unfinished = len(games) - len(completed)
    wins = sum(game.winner_seat == game.candidate_seat for game in completed)
    proportion = _proportion(wins, len(completed))
    return StrengthReport(
        wins=wins,
        games_completed=len(completed),
        unfinished=unfinished,
        win_rate=proportion.win_rate,
        interval=proportion.interval,
        by_seat=tuple(_seat_strength(seat, games) for seat in SEATS),
        attrition_as_losses=_proportion(wins, len(games)),
        attrition_as_wins=_proportion(wins + unfinished, len(games)),
    )


def clears_fair_share(report: StrengthReport, *, fair_share: float = FAIR_SHARE) -> bool:
    """The preregistered "beats" bar: both lower bounds strictly above fair share.

    The second bound counts every unfinished game as a candidate loss.
    """
    completed = report.interval
    attrition = report.attrition_as_losses.interval
    if completed is None or attrition is None:
        return False
    return completed.lower > fair_share and attrition.lower > fair_share


def falls_below_fair_share(report: StrengthReport, *, fair_share: float = FAIR_SHARE) -> bool:
    """The preregistered "loses" bar: both upper bounds strictly below fair share.

    The second bound counts every unfinished game as a candidate win.
    """
    completed = report.interval
    attrition = report.attrition_as_wins.interval
    if completed is None or attrition is None:
        return False
    return completed.upper < fair_share and attrition.upper < fair_share


def attrition_invalidates(report: StrengthReport) -> bool:
    """More than 1% unfinished games invalidates a strength conclusion."""
    total = report.games_completed + report.unfinished
    if total == 0:
        return False
    return report.unfinished / total > _DROP_LIMIT


def strength_conclusion(report: StrengthReport) -> Conclusion:
    if attrition_invalidates(report):
        return "invalid"
    if clears_fair_share(report):
        return "beats"
    if falls_below_fair_share(report):
        return "loses"
    return "inconclusive"


def format_strength_report(
    report: StrengthReport,
    *,
    extreme_games: int,
    dice_unavailable: int = 0,
) -> str:
    """Direct answer first. A sample other than 2,000 completed games is exploratory."""
    total = report.games_completed + report.unfinished
    if extreme_games < 0 or dice_unavailable < 0 or extreme_games + dice_unavailable > total:
        raise ValueError("dice counts must fit the games in the report")
    lines: list[str] = []
    if report.games_completed != PREREGISTERED_GAMES:
        lines.append("Exploratory result: this is not the preregistered decision.")
    lines.append(_proportion_line("Win rate", _completed_proportion(report)))
    lines.extend(_seat_line(seat) for seat in report.by_seat)
    lines.append(f"Unfinished: {report.unfinished}")
    lines.append(f"Extreme dice: {extreme_games}")
    lines.append(f"Dice unavailable: {dice_unavailable}")
    lines.append(
        _proportion_line("Attrition, unresolved counted as losses", report.attrition_as_losses)
    )
    lines.append(
        _proportion_line("Attrition, unresolved counted as wins", report.attrition_as_wins)
    )
    if report.games_completed == PREREGISTERED_GAMES:
        lines.append(_decision_line(report))
    return "\n".join(lines) + "\n"


def game_record_to_json(record: GameRecord) -> dict[str, object]:
    return {
        "candidate_seat": record.candidate_seat,
        "rolls": None if record.rolls is None else list(record.rolls),
        "rolls_available": record.rolls is not None,
        "seed": record.seed,
        "turn_count": record.turn_count,
        "winner_seat": record.winner_seat,
    }


def game_record_from_json(payload: object) -> GameRecord:
    if not isinstance(payload, dict):
        raise ValueError("game record must be a JSON object")
    if "winner_seat" not in payload:
        raise ValueError("winner_seat is required")
    available = payload.get("rolls_available")
    if not isinstance(available, bool):
        raise ValueError("rolls_available must be a boolean")
    rolls_field = payload.get("rolls")
    if available:
        if not isinstance(rolls_field, list):
            raise ValueError("recorded rolls must be a list")
        rolls: tuple[int, ...] | None = tuple(_json_roll(item) for item in rolls_field)
    else:
        if rolls_field is not None:
            raise ValueError("unavailable rolls must be null")
        rolls = None
    winner = payload.get("winner_seat")
    return GameRecord(
        seed=_json_int(payload.get("seed"), "seed"),
        candidate_seat=_json_seat(payload.get("candidate_seat"), "candidate_seat"),
        winner_seat=None if winner is None else _json_seat(winner, "winner_seat"),
        turn_count=_json_int(payload.get("turn_count"), "turn_count"),
        rolls=rolls,
    )


def _completed_proportion(report: StrengthReport) -> Proportion:
    return _proportion(report.wins, report.games_completed)


def _proportion(wins: int, games: int) -> Proportion:
    if games == 0:
        return Proportion(wins=0, games=0, win_rate=None, interval=None)
    return Proportion(
        wins=wins,
        games=games,
        win_rate=wins / games,
        interval=wilson_interval(wins, games),
    )


def _seat_strength(seat: str, games: Sequence[GameRecord]) -> SeatStrength:
    seated = [game for game in games if game.candidate_seat == seat]
    completed = [game for game in seated if game.winner_seat is not None]
    wins = sum(game.winner_seat == seat for game in completed)
    unfinished = len(seated) - len(completed)
    proportion = _proportion(wins, len(completed))
    return SeatStrength(
        seat=seat,
        wins=wins,
        games_completed=len(completed),
        unfinished=unfinished,
        win_rate=proportion.win_rate,
        interval=proportion.interval,
    )


def _proportion_line(label: str, proportion: Proportion) -> str:
    if proportion.win_rate is None or proportion.interval is None:
        body = "win rate n/a  95% Wilson n/a  games 0"
    else:
        body = (
            f"win rate {proportion.win_rate:.6f}  "
            f"95% Wilson [{proportion.interval.lower:.6f}, {proportion.interval.upper:.6f}]  "
            f"games {proportion.games}"
        )
    return f"{label}: wins {proportion.wins}  {body}"


def _seat_line(seat: SeatStrength) -> str:
    if seat.win_rate is None or seat.interval is None:
        rate = "win rate n/a  95% Wilson n/a"
    else:
        rate = (
            f"win rate {seat.win_rate:.6f}  "
            f"95% Wilson [{seat.interval.lower:.6f}, {seat.interval.upper:.6f}]"
        )
    return (
        f"{seat.seat}  wins {seat.wins}  games {seat.games_completed}  "
        f"{rate}  unfinished {seat.unfinished}"
    )


def _decision_line(report: StrengthReport) -> str:
    conclusion = strength_conclusion(report)
    if conclusion == "beats":
        return (
            "Preregistered decision: beats. The completed-game Wilson lower bound and "
            "the attrition-as-losses lower bound are above 0.25."
        )
    if conclusion == "loses":
        return (
            "Preregistered decision: loses. The completed-game Wilson upper bound and "
            "the attrition-as-wins upper bound are below 0.25."
        )
    if conclusion == "invalid":
        return "Preregistered decision: invalid. Unfinished games exceed 1%."
    return "Preregistered decision: inconclusive."


def _json_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _json_seat(value: object, name: str) -> str:
    if not isinstance(value, str) or value not in SEATS:
        raise ValueError(f"{name} must be a seat")
    return value


def _json_roll(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("a production roll must be an integer from 2 to 12")
    return value
