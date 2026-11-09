from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from catan_coach.domain.calibration import (
    GameBrierInterval,
    calibration_report,
    game_brier_difference,
)
from catan_coach.domain.corpus import TRAIN, VALIDATION, Corpus
from catan_coach.domain.prediction import FeatureMatrix, Probabilities
from catan_coach.models.baselines import ConstantModel, VictoryPointShareModel
from catan_coach.models.train import (
    BaselineComparison,
    clears_adoption,
    compare_predictions,
    compare_to_baselines,
    format_comparison,
    install_candidate,
    train,
)

VP_COLUMNS = (0, 1, 2, 3)
N_PLAYERS = 4


def _corpus(*, train_games: int = 40, val_games: int = 12, seed: int = 0) -> Corpus:
    """Labels follow a hidden column the VP baseline cannot see."""
    rng = np.random.default_rng(seed)
    games: list[int] = []
    splits: list[str] = []
    seats: list[str] = []
    won: list[float] = []
    rows: list[np.ndarray] = []
    names = ("RED", "BLUE", "WHITE", "ORANGE")

    def add_game(game_id: int, split: str) -> None:
        winner = int(rng.integers(0, N_PLAYERS))
        for _ply in range(3):
            for seat_index, seat in enumerate(names):
                vps = rng.integers(0, 6, size=N_PLAYERS).astype(np.float64)
                vps[winner] += 3
                hidden = rng.normal(0.0, 0.1, size=N_PLAYERS)
                hidden[winner] = 8.0
                # P0 is the perspective Seat, matching a real Observation.
                observation = np.concatenate(
                    [np.roll(vps, -seat_index), np.roll(hidden, -seat_index)]
                )
                games.append(game_id)
                splits.append(split)
                seats.append(seat)
                won.append(float(seat_index == winner))
                rows.append(observation)

    for game_id in range(train_games):
        add_game(game_id, TRAIN)
    for game_id in range(train_games, train_games + val_games):
        add_game(game_id, VALIDATION)

    return Corpus(
        game_ids=np.array(games, dtype=np.int64),
        plies=np.zeros(len(games), dtype=np.int32),
        seats=np.array(seats, dtype=np.str_),
        splits=np.array(splits, dtype=np.str_),
        won=np.array(won, dtype=np.float64),
        observations=np.vstack(rows),
    )


class TestTrain:
    def test_training_ignores_the_validation_split(self) -> None:
        corpus = _corpus()
        poisoned = Corpus(
            game_ids=corpus.game_ids,
            plies=corpus.plies,
            seats=corpus.seats,
            splits=corpus.splits,
            won=np.where(corpus.splits == VALIDATION, np.nan, corpus.won),
            observations=corpus.observations,
        )

        model = train(poisoned, seed=0)

        assert np.all(np.isfinite(model.predict(corpus.observations)))

    def test_the_saved_model_loads_through_the_port(self, tmp_path: Path) -> None:
        from catan_coach.domain.prediction import WinProbabilityModel
        from catan_coach.models.gbdt import GbdtModel

        corpus = _corpus()
        trained = train(corpus, seed=1)
        path = tmp_path / "model.txt"
        trained.save(path)
        loaded = GbdtModel.load(path)

        assert isinstance(loaded, WinProbabilityModel)
        assert loaded.predict(corpus.observations[:5]).shape == (5,)
        assert loaded.predict(corpus.observations[:5]) == pytest.approx(
            trained.predict(corpus.observations[:5]), abs=1e-9
        )

    def test_a_saved_map_reloads_with_the_model(self, tmp_path: Path) -> None:
        from catan_coach.domain.probability_map import fit_probability_map
        from catan_coach.models.gbdt import GbdtModel, calibration_sidecar

        corpus = _corpus(seed=11)
        path = tmp_path / "model.txt"
        raw = np.full(len(corpus.won), 0.2)
        mapped = train(corpus, seed=11).with_probability_map(
            fit_probability_map(raw, np.ones(len(raw)))
        )
        mapped.save(path)
        loaded = GbdtModel.load(path)

        assert calibration_sidecar(path).is_file()
        assert loaded.probability_map is not None
        assert float(loaded.predict(corpus.observations[:4]).mean()) > 0.9

    def test_writing_the_map_leaves_the_tree_file_unchanged(self, tmp_path: Path) -> None:
        from catan_coach.domain.probability_map import fit_probability_map
        from catan_coach.models.gbdt import GbdtModel, write_probability_map

        corpus = _corpus(seed=12)
        path = tmp_path / "model-v3.txt"
        train(corpus, seed=12).save(path)
        trees = path.read_bytes()
        write_probability_map(path, fit_probability_map(np.full(8, 0.2), np.ones(8)))

        assert path.read_bytes() == trees
        assert float(GbdtModel.load(path).predict(corpus.observations[:4]).mean()) > 0.9

    def test_the_model_beats_both_baselines_on_held_out_games(self) -> None:
        corpus = _corpus(train_games=60, val_games=20, seed=2)
        model = train(corpus, seed=2)
        comparison = compare_to_baselines(
            model,
            corpus,
            constant=ConstantModel(N_PLAYERS),
            vp_share=VictoryPointShareModel(VP_COLUMNS),
        )

        assert comparison.beats_constant
        assert comparison.beats_vp_share
        assert comparison.ece_better_than_vp_share

    def test_a_failure_to_clear_a_baseline_is_stated_in_the_report(self) -> None:
        corpus = _corpus(train_games=8, val_games=8, seed=3)
        comparison = compare_to_baselines(
            ConstantModel(N_PLAYERS),
            corpus,
            constant=ConstantModel(N_PLAYERS),
            vp_share=VictoryPointShareModel(VP_COLUMNS),
        )
        text = format_comparison(comparison, corpus_path="toy", n_games=corpus.n_games)

        assert comparison.beats_constant is False
        assert "does not beat" in text.lower()
        assert "toy" in text
        assert str(corpus.n_games) in text
        assert "brier" in text.lower()
        assert "ece" in text.lower()
        assert "Discrimination" in text

    def test_training_is_reproducible_from_a_seed(self) -> None:
        corpus = _corpus(seed=4)
        first = train(corpus, seed=7).predict(corpus.observations[:12])
        second = train(corpus, seed=7).predict(corpus.observations[:12])
        assert first == pytest.approx(second)

    def test_explanations_use_player_recognisable_labels(self, tmp_path: Path) -> None:
        from catan_coach.domain.reasons import PLAYER_LABELS
        from catan_coach.models.gbdt import GbdtModel

        corpus = _corpus(seed=5)
        names = (
            "P0_PUBLIC_VPS",
            "P1_PUBLIC_VPS",
            "P2_PUBLIC_VPS",
            "P3_PUBLIC_VPS",
            "TILE0_PROBA",
            "TILE1_PROBA",
            "P0_WHEAT_IN_HAND",
            "P0_HAS_ARMY",
        )
        path = tmp_path / "model.txt"
        train(corpus, seed=5).save(path)
        reasons = GbdtModel.load(path, feature_names=names).explain(corpus.observations[:3])

        assert len(reasons) == 3
        for group in reasons:
            assert {item.label for item in group} <= set(PLAYER_LABELS)


class _Overconfident:
    name = "overconfident"

    def predict(self, features: FeatureMatrix) -> Probabilities:
        return np.full(features.shape[0], 0.99, dtype=np.float64)


def test_a_candidate_must_beat_the_installed_model() -> None:
    corpus = _corpus(train_games=60, val_games=20, seed=6)
    model = train(corpus, seed=6)
    same = compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=model,
    )
    better = compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=_Overconfident(),
    )

    assert same.beats_installed is False
    assert same.ece_better_than_installed is False
    assert "does not beat overconfident" not in format_comparison(
        same, corpus_path="toy", n_games=corpus.n_games
    )
    assert "does not beat" in format_comparison(same, corpus_path="toy", n_games=1)
    assert clears_adoption(better)
    assert "beats overconfident on Brier skill" in format_comparison(
        better, corpus_path="toy", n_games=1
    )


def test_brier_adopts_when_calibration_error_is_worse() -> None:
    report = calibration_report([0.4], [1.0])
    comparison = BaselineComparison(
        model_report=report,
        constant_report=report,
        vp_share_report=report,
        model_name="candidate",
        constant_name="constant(1/4)",
        vp_share_name="vp-share",
        beats_constant=True,
        beats_vp_share=True,
        ece_better_than_vp_share=False,
        skill_vs_constant=0.1,
        skill_vs_vp_share=0.1,
        installed_name="installed",
        beats_installed=True,
        ece_better_than_installed=False,
        skill_vs_installed=0.1,
    )

    assert clears_adoption(comparison)


def test_a_failed_candidate_is_not_copied_over_the_installed_model(tmp_path: Path) -> None:
    corpus = _corpus(train_games=40, val_games=12, seed=8)
    model = train(corpus, seed=8)
    comparison = compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=model,
    )
    installed = tmp_path / "model.txt"
    candidate = tmp_path / "candidate.txt"
    installed.write_bytes(b"kept")
    candidate.write_bytes(b"new")

    assert install_candidate(candidate, installed, comparison) is False
    assert installed.read_bytes() == b"kept"


def test_a_candidate_that_clears_the_bars_replaces_the_installed_model(tmp_path: Path) -> None:
    corpus = _corpus(train_games=60, val_games=20, seed=9)
    model = train(corpus, seed=9)
    comparison = compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=_Overconfident(),
    )
    installed = tmp_path / "model.txt"
    candidate = tmp_path / "candidate.txt"
    installed.write_bytes(b"old")
    candidate.write_bytes(b"new")

    assert install_candidate(candidate, installed, comparison) is True
    assert installed.read_bytes() == b"new"


def test_installing_copies_the_map_and_drops_a_stale_one(tmp_path: Path) -> None:
    from catan_coach.models.gbdt import calibration_sidecar

    corpus = _corpus(train_games=60, val_games=20, seed=9)
    model = train(corpus, seed=9)
    comparison = compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=_Overconfident(),
    )
    installed = tmp_path / "model.txt"
    candidate = tmp_path / "candidate.txt"
    installed.write_bytes(b"old")
    candidate.write_bytes(b"new")
    calibration_sidecar(installed).write_text("stale", encoding="utf-8")
    calibration_sidecar(candidate).write_text('{"knots": [[0, 0.2], [1, 0.8]]}', encoding="utf-8")

    assert install_candidate(candidate, installed, comparison) is True
    assert calibration_sidecar(installed).read_text(encoding="utf-8").startswith('{"knots"')

    other = tmp_path / "plain.txt"
    other.write_bytes(b"plain")
    installed.write_bytes(b"old")
    assert install_candidate(other, installed, comparison) is True
    assert not calibration_sidecar(installed).exists()


def test_the_installed_path_cannot_be_the_candidate_path(tmp_path: Path) -> None:
    corpus = _corpus(train_games=60, val_games=20, seed=10)
    model = train(corpus, seed=10)
    comparison = compare_to_baselines(
        model,
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=_Overconfident(),
    )
    path = tmp_path / "model.txt"
    path.write_bytes(b"same")

    with pytest.raises(ValueError, match="itself"):
        install_candidate(path, path, comparison)


def test_n_games_counts_games_not_rows() -> None:
    corpus = _corpus(train_games=3, val_games=2)
    assert corpus.n_games == 5
    assert len(corpus.won) > 5


def _row(probability: float, count: int) -> np.ndarray:
    return np.full(count, probability, dtype=np.float64)


def _compare(
    candidate: np.ndarray,
    outcomes: np.ndarray,
    *,
    constant_predicted: np.ndarray,
    vp_predicted: np.ndarray,
    installed_predicted: np.ndarray,
    priors: tuple[tuple[str, np.ndarray], ...] = (),
    game_ids: np.ndarray | None = None,
) -> BaselineComparison:
    return compare_predictions(
        candidate,
        outcomes,
        model_name="candidate",
        constant_predicted=constant_predicted,
        constant_name="constant(1/4)",
        vp_predicted=vp_predicted,
        vp_name="vp-share",
        installed_predicted=installed_predicted,
        installed_name="installed",
        priors=priors,
        game_ids=game_ids,
    )


def test_adoption_resamples_games_rather_than_rows() -> None:
    outcomes = np.ones(6)
    candidate = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    reference = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.0])
    game_ids = np.array([0, 0, 0, 0, 0, 1])
    comparison = compare_predictions(
        candidate,
        outcomes,
        model_name="candidate",
        constant_predicted=reference,
        constant_name="constant(1/4)",
        vp_predicted=reference,
        vp_name="vp-share",
        installed_predicted=reference,
        installed_name="installed",
        game_ids=game_ids,
    )
    expected = game_brier_difference([1.0, 0.0], [0.0, 1.0], [5.0, 1.0], seed=0)

    assert comparison.constant_interval == expected
    assert comparison.constant_interval is not None
    assert comparison.constant_interval.point == pytest.approx(4.0 / 6.0)


def test_a_point_estimate_win_whose_interval_reaches_zero_is_not_adopted(tmp_path: Path) -> None:
    good = 1.0 - np.sqrt(0.24)
    bad = 1.0 - np.sqrt(0.43)
    candidate = np.concatenate([_row(float(good), 19), _row(float(bad), 1)])
    outcomes = np.ones(candidate.shape[0])
    constant = _row(0.5, candidate.shape[0])
    weaker = _row(0.2, candidate.shape[0])
    point = _compare(
        candidate,
        outcomes,
        constant_predicted=constant,
        vp_predicted=weaker,
        installed_predicted=weaker,
    )
    games = _compare(
        candidate,
        outcomes,
        constant_predicted=constant,
        vp_predicted=weaker,
        installed_predicted=weaker,
        game_ids=np.arange(candidate.shape[0]),
    )

    assert point.constant_interval is None
    assert point.beats_constant
    assert clears_adoption(point)
    assert games.constant_interval is not None
    assert games.constant_interval.point < 0.0
    assert games.constant_interval.point == pytest.approx(
        games.model_report.brier_score - games.constant_report.brier_score
    )
    assert games.constant_interval.upper > 0.0
    assert games.beats_vp_share
    assert games.beats_installed is True
    assert games.beats_constant is False
    assert clears_adoption(games) is False

    installed = tmp_path / "model.txt"
    candidate_path = tmp_path / "candidate.txt"
    installed.write_bytes(b"kept")
    candidate_path.write_bytes(b"new")
    assert install_candidate(candidate_path, installed, games) is False
    assert installed.read_bytes() == b"kept"


def test_every_supplied_prior_must_clear_the_interval(tmp_path: Path) -> None:
    outcomes = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    candidate = np.array([0.8, 0.8, 0.8, 0.2, 0.2, 0.2])
    constant = _row(0.25, 6)
    vp = _row(0.5, 6)
    installed = np.array([0.6, 0.6, 0.6, 0.4, 0.4, 0.4])
    game_ids = np.arange(6)
    blocked = compare_predictions(
        candidate,
        outcomes,
        model_name="candidate",
        constant_predicted=constant,
        constant_name="constant(1/4)",
        vp_predicted=vp,
        vp_name="vp-share",
        installed_predicted=installed,
        installed_name="installed",
        priors=(("generation-3", np.array([0.95, 0.95, 0.95, 0.05, 0.05, 0.05])),),
        game_ids=game_ids,
    )
    cleared = compare_predictions(
        candidate,
        outcomes,
        model_name="candidate",
        constant_predicted=constant,
        constant_name="constant(1/4)",
        vp_predicted=vp,
        vp_name="vp-share",
        installed_predicted=installed,
        installed_name="installed",
        priors=(("generation-3", np.array([0.7, 0.7, 0.7, 0.3, 0.3, 0.3])),),
        game_ids=game_ids,
    )

    assert blocked.beats_constant
    assert blocked.beats_vp_share
    assert blocked.beats_installed is True
    assert blocked.priors[0].beats is False
    assert blocked.ece_better_than_vp_share is False
    assert clears_adoption(blocked) is False
    assert cleared.priors[0].beats is True
    assert cleared.ece_better_than_vp_share is False
    assert clears_adoption(cleared)

    installed_path = tmp_path / "model.txt"
    candidate_path = tmp_path / "candidate.txt"
    installed_path.write_bytes(b"kept")
    candidate_path.write_bytes(b"new")
    assert install_candidate(candidate_path, installed_path, blocked) is False
    assert installed_path.read_bytes() == b"kept"
    assert install_candidate(candidate_path, installed_path, cleared) is True
    assert installed_path.read_bytes() == b"new"

    text = format_comparison(cleared, corpus_path="toy", n_games=6)
    lines = text.splitlines()
    header = next(index for index, line in enumerate(lines) if line.startswith("candidate:"))
    assert "brier=" in lines[header]
    assert "logloss=" in lines[header]
    assert "ece=" in lines[header]
    assert lines[header + 1].startswith("brier difference")
    assert "95%" in lines[header + 1]
    assert "generation-3" in text


def test_without_game_ids_a_prior_uses_the_point_estimate() -> None:
    outcomes = np.array([1.0, 0.0])
    candidate = np.array([0.7, 0.3])
    constant = np.array([0.25, 0.25])
    vp = np.array([0.4, 0.6])
    installed = np.array([0.6, 0.4])
    tied = _compare(
        candidate,
        outcomes,
        constant_predicted=constant,
        vp_predicted=vp,
        installed_predicted=installed,
        priors=(("generation-3", candidate.copy()),),
    )
    beaten = _compare(
        candidate,
        outcomes,
        constant_predicted=constant,
        vp_predicted=vp,
        installed_predicted=installed,
        priors=(("generation-3", np.array([0.5, 0.5])),),
    )

    assert tied.constant_interval is None
    assert tied.priors[0].interval is None
    assert tied.priors[0].beats is False
    assert clears_adoption(tied) is False
    assert beaten.priors[0].beats is True
    assert clears_adoption(beaten)


def test_a_supplied_interval_that_reaches_zero_blocks_adoption() -> None:
    report = calibration_report([0.4], [1.0])
    reached = GameBrierInterval(point=-0.0019, lower=-0.0065, upper=0.0030)
    cleared = GameBrierInterval(point=-0.0200, lower=-0.0300, upper=-0.0100)
    comparison = BaselineComparison(
        model_report=report,
        constant_report=report,
        vp_share_report=report,
        model_name="candidate",
        constant_name="constant(1/4)",
        vp_share_name="vp-share",
        beats_constant=True,
        beats_vp_share=True,
        ece_better_than_vp_share=False,
        skill_vs_constant=0.1,
        skill_vs_vp_share=0.1,
        installed_name="installed",
        beats_installed=True,
        ece_better_than_installed=False,
        skill_vs_installed=0.1,
        constant_interval=reached,
        vp_share_interval=cleared,
        installed_interval=cleared,
    )

    assert clears_adoption(comparison) is False


def test_validation_game_ids_turn_the_interval_on() -> None:
    corpus = _corpus(train_games=4, val_games=4, seed=1)
    mask = corpus.splits == VALIDATION
    comparison = compare_to_baselines(
        ConstantModel(N_PLAYERS),
        corpus,
        constant=ConstantModel(N_PLAYERS),
        vp_share=VictoryPointShareModel(VP_COLUMNS),
        installed=_Overconfident(),
        priors=(_Overconfident(),),
        game_ids=corpus.game_ids[mask],
    )

    assert comparison.constant_interval is not None
    assert comparison.vp_share_interval is not None
    assert comparison.installed_interval is not None
    assert comparison.priors[0].name == "overconfident"
    assert comparison.priors[0].interval is not None
    assert "95%" in format_comparison(comparison, corpus_path="toy", n_games=4)
