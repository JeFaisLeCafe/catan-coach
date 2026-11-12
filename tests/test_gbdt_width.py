from __future__ import annotations

import numpy as np
import pytest

from catan_coach.domain.corpus import TRAIN, Corpus
from catan_coach.models.gbdt import GbdtModel
from catan_coach.models.train import train, train_matrix

_PREFIX_NAMES = (
    "P0_PUBLIC_VPS",
    "P1_PUBLIC_VPS",
    "P2_PUBLIC_VPS",
    "P3_PUBLIC_VPS",
    "P0_WHEAT_IN_HAND",
)
_EXTRA_NAMES = ("TILE0_PROBA", "EDGE0", "P0_HAS_ARMY")


def _separable(*, rows: int = 80, cols: int = 5, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(rows, cols)).astype(np.float64)
    won = np.zeros(rows, dtype=np.float64)
    won[: rows // 2] = 1.0
    features[: rows // 2, 0] += 6.0
    features[rows // 2 :, 0] -= 6.0
    return features, won


def test_a_wider_matrix_scores_the_trained_prefix() -> None:
    features, won = _separable()
    model = train_matrix(features, won, seed=0)
    extra = np.random.default_rng(1).normal(size=(features.shape[0], 3))
    wide = np.hstack([features, extra])

    assert model.width == 5
    assert np.array_equal(model.predict(wide), model.predict(features))


def test_a_narrower_matrix_names_both_widths() -> None:
    features, won = _separable()
    model = train_matrix(features, won, seed=0)
    narrow = features[:, :4]

    with pytest.raises(ValueError, match=r"4 columns but the model expects 5"):
        model.predict(narrow)
    with pytest.raises(ValueError, match=r"4 columns but the model expects 5"):
        model.explain(narrow)


def test_explain_uses_only_the_trained_prefix_of_names() -> None:
    features, won = _separable(seed=2)
    trained = train_matrix(features, won, seed=2)
    names = _PREFIX_NAMES + _EXTRA_NAMES
    wide_model = GbdtModel(trained._booster, feature_names=names)
    prefix_model = GbdtModel(trained._booster, feature_names=_PREFIX_NAMES)
    extra = np.random.default_rng(3).normal(size=(features.shape[0], 3))
    wide = np.hstack([features, extra])

    explained = wide_model.explain(wide)

    assert explained == prefix_model.explain(features)
    labels = {item.label for group in explained for item in group}
    assert labels <= {"points", "hand"}
    assert labels


def test_masked_columns_get_no_splits_and_the_input_stays_unchanged() -> None:
    rng = np.random.default_rng(4)
    features = rng.normal(size=(80, 4)).astype(np.float64)
    won = rng.integers(0, 2, size=80).astype(np.float64)
    perfect = 2
    features[:, perfect] = won
    original = features.copy()
    features.setflags(write=False)

    masked = train_matrix(features, won, seed=0, masked_columns=(perfect,))
    unmasked = train_matrix(original, won, seed=0)

    assert np.array_equal(features, original)
    assert masked._booster.feature_importance()[perfect] == 0
    assert unmasked._booster.feature_importance()[perfect] > 0


def test_an_empty_mask_matches_training_without_one() -> None:
    features, won = _separable(rows=40, seed=5)
    plain = train_matrix(features, won, seed=3)
    explicit = train_matrix(features, won, seed=3, masked_columns=())

    assert plain._booster.model_to_string() == explicit._booster.model_to_string()


def test_train_forwards_masked_columns() -> None:
    features, won = _separable(rows=40, cols=3, seed=6)
    perfect = 1
    features[:, perfect] = won
    corpus = Corpus(
        game_ids=np.arange(features.shape[0], dtype=np.int64),
        plies=np.zeros(features.shape[0], dtype=np.int32),
        seats=np.array(["RED"] * features.shape[0]),
        splits=np.array([TRAIN] * features.shape[0]),
        won=won,
        observations=features,
    )

    via_train = train(corpus, seed=1, masked_columns=(perfect,))
    via_matrix = train_matrix(features, won, seed=1, masked_columns=(perfect,))

    assert via_train._booster.model_to_string() == via_matrix._booster.model_to_string()
    assert via_train._booster.feature_importance()[perfect] == 0


def test_a_masked_column_outside_the_matrix_is_rejected() -> None:
    features = np.zeros((8, 3), dtype=np.float64)
    features.setflags(write=False)
    won = np.zeros(8, dtype=np.float64)

    with pytest.raises(ValueError, match=r"masked column 3 is outside the 3"):
        train_matrix(features, won, masked_columns=(3,))
    with pytest.raises(ValueError, match=r"masked column -1 is outside the 3"):
        train_matrix(features, won, masked_columns=(-1,))
