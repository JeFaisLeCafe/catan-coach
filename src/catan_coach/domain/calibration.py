"""Measures whether predicted win probabilities are honest.

A model that says "70%" should win about 70% of the time. Everything else in
this project is downstream of that claim, so this module exists before any
model does, and no model is adopted without beating a baseline here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

Probabilities = NDArray[np.float64]
Outcomes = NDArray[np.float64]

DEFAULT_NUM_BINS = 10

# Keeps log loss finite when a model predicts exactly 0 or 1 and is wrong.
_LOG_LOSS_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_frequency: float

    @property
    def gap(self) -> float:
        return self.observed_frequency - self.mean_predicted


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    count: int
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    bins: tuple[ReliabilityBin, ...]

    @property
    def populated_bins(self) -> tuple[ReliabilityBin, ...]:
        return tuple(b for b in self.bins if b.count > 0)


def _as_arrays(predicted: ArrayLike, outcomes: ArrayLike) -> tuple[Probabilities, Outcomes]:
    p = np.asarray(predicted, dtype=np.float64).ravel()
    y = np.asarray(outcomes, dtype=np.float64).ravel()

    if p.size == 0:
        raise ValueError("need at least one prediction")
    if p.shape != y.shape:
        raise ValueError(f"predicted and outcomes differ in length: {p.shape} vs {y.shape}")
    if not np.all(np.isfinite(p)):
        raise ValueError("predicted contains non-finite values")
    if np.any(p < 0.0) or np.any(p > 1.0):
        raise ValueError("predicted must lie in [0, 1]")
    if not np.all(np.isin(y, (0.0, 1.0))):
        raise ValueError("outcomes must be 0 or 1")

    return p, y


def brier_score(predicted: ArrayLike, outcomes: ArrayLike) -> float:
    """Mean squared error of probability against outcome. Lower is better."""
    p, y = _as_arrays(predicted, outcomes)
    return float(np.mean((p - y) ** 2))


def log_loss(predicted: ArrayLike, outcomes: ArrayLike) -> float:
    """Punishes confident mistakes far harder than Brier does."""
    p, y = _as_arrays(predicted, outcomes)
    clipped = np.clip(p, _LOG_LOSS_EPSILON, 1.0 - _LOG_LOSS_EPSILON)
    return float(-np.mean(y * np.log(clipped) + (1.0 - y) * np.log(1.0 - clipped)))


def brier_skill_score(model_brier: float, reference_brier: float) -> float:
    """Fraction of the reference's error removed. 0 means no better than the
    reference, 1 means perfect, negative means worse."""
    if reference_brier <= 0.0:
        raise ValueError("reference_brier must be positive to compare against")
    return 1.0 - model_brier / reference_brier


def reliability_bins(
    predicted: ArrayLike,
    outcomes: ArrayLike,
    num_bins: int = DEFAULT_NUM_BINS,
) -> tuple[ReliabilityBin, ...]:
    """Group predictions into equal-width probability bands and compare each
    band's mean prediction to how often it actually happened."""
    if num_bins < 1:
        raise ValueError("num_bins must be at least 1")
    p, y = _as_arrays(predicted, outcomes)

    edges = np.linspace(0.0, 1.0, num_bins + 1)
    # floor(p * num_bins) except p == 1.0, which would otherwise fall past the end.
    indices = np.minimum((p * num_bins).astype(np.int64), num_bins - 1)

    bins: list[ReliabilityBin] = []
    for i in range(num_bins):
        mask = indices == i
        count = int(np.count_nonzero(mask))
        bins.append(
            ReliabilityBin(
                lower=float(edges[i]),
                upper=float(edges[i + 1]),
                count=count,
                mean_predicted=float(np.mean(p[mask])) if count else 0.0,
                observed_frequency=float(np.mean(y[mask])) if count else 0.0,
            )
        )
    return tuple(bins)


def expected_calibration_error(bins: tuple[ReliabilityBin, ...]) -> float:
    """Average distance between promise and reality, weighted by bin population."""
    total = sum(b.count for b in bins)
    if total == 0:
        raise ValueError("bins are empty")
    return sum(b.count / total * abs(b.gap) for b in bins)


def calibration_report(
    predicted: ArrayLike,
    outcomes: ArrayLike,
    num_bins: int = DEFAULT_NUM_BINS,
) -> CalibrationReport:
    p, y = _as_arrays(predicted, outcomes)
    bins = reliability_bins(p, y, num_bins)
    return CalibrationReport(
        count=int(p.size),
        brier_score=brier_score(p, y),
        log_loss=log_loss(p, y),
        expected_calibration_error=expected_calibration_error(bins),
        bins=bins,
    )


def format_report(report: CalibrationReport, name: str = "model") -> str:
    lines = [
        f"{name}: n={report.count}  brier={report.brier_score:.4f}  "
        f"logloss={report.log_loss:.4f}  ece={report.expected_calibration_error:.4f}",
        f"{'band':>12}  {'n':>8}  {'predicted':>9}  {'actual':>7}  {'gap':>7}",
    ]
    for b in report.populated_bins:
        lines.append(
            f"  [{b.lower:.1f},{b.upper:.1f})  {b.count:>8}  "
            f"{b.mean_predicted:>9.3f}  {b.observed_frequency:>7.3f}  {b.gap:>+7.3f}"
        )
    return "\n".join(lines)
