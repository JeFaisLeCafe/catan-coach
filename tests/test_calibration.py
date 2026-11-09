from __future__ import annotations

import numpy as np
import pytest

from catan_coach.domain.calibration import (
    brier_score,
    brier_skill_score,
    calibration_report,
    expected_calibration_error,
    format_report,
    game_brier_difference,
    log_loss,
    reference_cleared,
    reliability_bins,
)


def well_calibrated(n: int = 200_000, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """Predictions that are true by construction: outcome ~ Bernoulli(p)."""
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.0, 1.0, size=n)
    return p, (rng.uniform(size=n) < p).astype(np.float64)


class TestBrierScore:
    def test_perfect_predictions_score_zero(self) -> None:
        y = np.array([1.0, 0.0, 1.0, 0.0])
        assert brier_score(y, y) == 0.0

    def test_maximally_wrong_predictions_score_one(self) -> None:
        y = np.array([1.0, 0.0])
        assert brier_score(1.0 - y, y) == 1.0

    def test_coin_flip_on_balanced_outcomes_scores_a_quarter(self) -> None:
        y = np.array([1.0, 0.0, 1.0, 0.0])
        assert brier_score(np.full(4, 0.5), y) == pytest.approx(0.25)

    def test_matches_mean_variance_when_calibrated(self) -> None:
        p, y = well_calibrated()
        assert brier_score(p, y) == pytest.approx(np.mean(p * (1 - p)), abs=5e-3)


class TestLogLoss:
    def test_perfect_predictions_are_near_zero(self) -> None:
        y = np.array([1.0, 0.0, 1.0])
        assert log_loss(y, y) == pytest.approx(0.0, abs=1e-9)

    def test_confident_and_wrong_stays_finite(self) -> None:
        assert np.isfinite(log_loss(np.array([0.0]), np.array([1.0])))

    def test_punishes_confident_errors_harder_than_brier(self) -> None:
        y = np.array([1.0, 1.0])
        timid, bold = np.array([0.4, 0.4]), np.array([0.05, 0.75])
        assert brier_score(bold, y) > brier_score(timid, y)
        assert log_loss(bold, y) > log_loss(timid, y)


class TestReliabilityBins:
    def test_bins_partition_every_sample(self) -> None:
        p, y = well_calibrated(n=5_000)
        bins = reliability_bins(p, y, num_bins=10)
        assert sum(b.count for b in bins) == 5_000

    def test_probability_of_one_lands_in_the_final_bin(self) -> None:
        bins = reliability_bins(np.array([1.0]), np.array([1.0]), num_bins=10)
        assert bins[-1].count == 1
        assert sum(b.count for b in bins[:-1]) == 0

    def test_empty_bins_are_reported_with_zero_count(self) -> None:
        bins = reliability_bins(np.array([0.05]), np.array([0.0]), num_bins=10)
        assert bins[0].count == 1
        assert all(b.count == 0 for b in bins[1:])

    def test_calibrated_data_has_small_gaps(self) -> None:
        p, y = well_calibrated()
        for b in reliability_bins(p, y, num_bins=10):
            assert abs(b.gap) < 0.02


class TestExpectedCalibrationError:
    def test_calibrated_model_is_near_zero(self) -> None:
        p, y = well_calibrated()
        assert expected_calibration_error(reliability_bins(p, y)) < 0.01

    def test_overconfident_model_is_penalised(self) -> None:
        """Claims 95% on coin flips."""
        rng = np.random.default_rng(1)
        y = (rng.uniform(size=20_000) < 0.5).astype(np.float64)
        p = np.full(y.size, 0.95)
        assert expected_calibration_error(reliability_bins(p, y)) == pytest.approx(0.45, abs=0.02)

    def test_ignores_empty_bins(self) -> None:
        p = np.array([0.95, 0.95, 0.95, 0.95])
        y = np.array([1.0, 1.0, 1.0, 1.0])
        assert expected_calibration_error(reliability_bins(p, y)) == pytest.approx(0.05)


class TestBrierSkillScore:
    def test_matching_the_reference_scores_zero(self) -> None:
        assert brier_skill_score(0.25, 0.25) == 0.0

    def test_perfect_model_scores_one(self) -> None:
        assert brier_skill_score(0.0, 0.25) == 1.0

    def test_worse_than_reference_goes_negative(self) -> None:
        assert brier_skill_score(0.30, 0.25) < 0.0

    def test_rejects_a_useless_reference(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            brier_skill_score(0.1, 0.0)


class TestValidation:
    @pytest.mark.parametrize(
        ("predicted", "outcomes", "message"),
        [
            ([], [], "at least one"),
            ([0.5, 0.5], [1.0], "differ in length"),
            ([1.5], [1.0], r"\[0, 1\]"),
            ([-0.1], [1.0], r"\[0, 1\]"),
            ([np.nan], [1.0], "non-finite"),
            ([0.5], [2.0], "must be 0 or 1"),
        ],
    )
    def test_rejects_bad_input(
        self, predicted: list[float], outcomes: list[float], message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            brier_score(predicted, outcomes)

    def test_rejects_zero_bins(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            reliability_bins([0.5], [1.0], num_bins=0)


class TestCalibrationReport:
    def test_bundles_the_metrics(self) -> None:
        p, y = well_calibrated(n=10_000)
        report = calibration_report(p, y)
        assert report.count == 10_000
        assert report.brier_score == pytest.approx(brier_score(p, y))
        assert report.expected_calibration_error < 0.02
        assert len(report.populated_bins) == 10

    def test_formats_without_blowing_up_on_sparse_bins(self) -> None:
        text = format_report(calibration_report([0.5, 0.5], [1.0, 0.0]), name="coin")
        assert "coin" in text
        assert "brier=0.2500" in text


def test_a_low_raw_probability_is_pulled_toward_the_outcome() -> None:
    from catan_coach.domain.probability_map import fit_probability_map

    raw = np.full(30, 0.2)
    mapped = fit_probability_map(raw, np.ones(30)).apply(raw)

    assert float(mapped.mean()) > 0.8


def test_the_map_never_decreases() -> None:
    from catan_coach.domain.probability_map import fit_probability_map

    rng = np.random.default_rng(0)
    raw = rng.uniform(0.0, 1.0, size=300)
    outcomes = (rng.uniform(size=300) < 0.7).astype(np.float64)
    applied = fit_probability_map(raw, outcomes).apply(np.linspace(0.0, 1.0, 40))

    assert np.all(np.diff(applied) >= -1e-12)


def test_equal_raw_probabilities_share_their_observed_rate() -> None:
    from catan_coach.domain.probability_map import fit_probability_map

    raw = np.array([0.2, 0.2, 0.8, 0.8])
    outcomes = np.array([1.0, 0.0, 1.0, 1.0])
    mapped = fit_probability_map(raw, outcomes).apply([0.2, 0.8])

    assert mapped == pytest.approx([0.5, 1.0])


def test_equal_raw_probabilities_are_independent_of_row_order() -> None:
    from catan_coach.domain.probability_map import fit_probability_map

    raw = np.array([0.2, 0.2, 0.8, 0.8])
    outcomes = np.array([1.0, 0.0, 1.0, 1.0])
    reordered = np.array([1, 0, 3, 2])

    first = fit_probability_map(raw, outcomes)
    second = fit_probability_map(raw[reordered], outcomes[reordered])

    assert first.knots == second.knots


def test_one_game_keeps_a_single_calibration_half() -> None:
    from catan_coach.domain.probability_map import calibration_half

    assert calibration_half(4, seed=2, source=1) == calibration_half(4, seed=2, source=1)


def test_the_map_is_fit_only_on_its_half() -> None:
    from catan_coach.domain.probability_map import calibration_half, fit_probability_map

    game_ids = np.repeat(np.arange(20), 5)
    rng = np.random.default_rng(1)
    raw = rng.uniform(0.0, 1.0, size=game_ids.size)
    outcomes = (rng.uniform(size=game_ids.size) < raw).astype(np.float64)
    fit = np.array(
        [calibration_half(int(game_id), seed=0, source=0) == "fit" for game_id in game_ids]
    )
    for game_id in np.unique(game_ids):
        assert len(set(fit[game_ids == game_id].tolist())) == 1
    assert np.any(fit) and np.any(~fit)

    first = fit_probability_map(raw[fit], outcomes[fit])
    flipped = outcomes.copy()
    flipped[~fit] = 1.0 - flipped[~fit]
    second = fit_probability_map(raw[fit], flipped[fit])

    assert first.knots == second.knots


def test_a_candidate_worse_on_every_game_does_not_clear() -> None:
    interval = game_brier_difference(
        [0.40, 0.55, 0.30],
        [0.10, 0.20, 0.05],
        [1.0, 4.0, 2.0],
    )

    assert interval.point > 0.0
    assert reference_cleared(interval) is False


def test_a_candidate_better_on_every_game_clears() -> None:
    interval = game_brier_difference(
        [0.10, 0.20, 0.05],
        [0.40, 0.55, 0.30],
        [1.0, 4.0, 2.0],
    )

    assert interval.point < 0.0
    assert interval.upper < 0.0
    assert reference_cleared(interval) is True


def test_a_tie_does_not_clear() -> None:
    interval = game_brier_difference([0.2, 0.4], [0.2, 0.4], [3.0, 1.0])

    assert interval.point == pytest.approx(0.0)
    assert interval.upper == pytest.approx(0.0)
    assert reference_cleared(interval) is False


def test_the_interval_contains_the_point_estimate() -> None:
    candidate = np.array([0.20, 0.50, 0.10, 0.40])
    reference = np.array([0.25, 0.30, 0.30, 0.20])
    weights = np.array([1.0, 5.0, 2.0, 4.0])
    interval = game_brier_difference(candidate, reference, weights)
    point = float(np.sum(weights * (candidate - reference)) / np.sum(weights))

    assert interval.point == pytest.approx(point)
    assert interval.lower <= interval.point <= interval.upper
    assert interval.lower < interval.upper


def test_the_resampling_seed_repeats() -> None:
    candidate = np.array([0.20, 0.50, 0.10, 0.40, 0.33])
    reference = np.array([0.25, 0.30, 0.30, 0.20, 0.10])
    weights = np.array([1.0, 5.0, 2.0, 4.0, 3.0])

    assert game_brier_difference(candidate, reference, weights, seed=0) == game_brier_difference(
        candidate, reference, weights, seed=0
    )
    assert game_brier_difference(
        candidate, reference, weights, resamples=25, seed=0
    ) != game_brier_difference(candidate, reference, weights, resamples=25, seed=1)
