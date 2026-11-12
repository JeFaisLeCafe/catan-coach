"""The calibrate gate, and keeping a failed candidate's map beside it."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.engine

pytest.importorskip("catanatron")

from catan_coach.domain.manifest import MANIFEST_NAME, CorpusManifest  # noqa: E402
from catan_coach.engine.calibrate import calibrate_model  # noqa: E402
from catan_coach.engine.features import feature_names, public_vp_indices  # noqa: E402
from catan_coach.models.gbdt import calibration_sidecar  # noqa: E402
from catan_coach.models.train import train_matrix  # noqa: E402

SEATS = ("RED", "BLUE", "WHITE", "ORANGE")


def _corpus(root: Path, games: int, rng: np.random.Generator) -> None:
    width = len(feature_names(4))
    vp = public_vp_indices(4)
    (root / "games").mkdir(parents=True)
    for game_id in range(games):
        observations = rng.random((4, width))
        winner = int(rng.integers(4))
        for row in range(4):
            observations[row, vp[0]] = 9.0 if row == winner else 2.0
        pd.DataFrame(
            {
                "game_id": [game_id] * 4,
                "ply": [0] * 4,
                "seat": list(SEATS),
                "split": ["validation"] * 4,
                "won": [float(row == winner) for row in range(4)],
                "seed": [game_id] * 4,
                "observation": [observations[row].tolist() for row in range(4)],
            }
        ).to_parquet(root / "games" / f"{game_id:05d}.parquet")
    manifest = CorpusManifest(
        player_kind="value",
        model_sha256="",
        search_simulations=0,
        exploration=False,
        ply_stride=12,
        base_seed=0,
        requested_games=games,
        validation_fraction=0.2,
        max_turns=1000,
        git_revision="unknown",
        dirty_tree=False,
        games_finished=games,
        games_dropped=0,
        drop_rate=0.0,
    )
    (root / MANIFEST_NAME).write_text(manifest.to_json(), encoding="utf-8")


def _noise_model(path: Path, rng: np.random.Generator) -> Path:
    width = len(feature_names(4))
    train_matrix(rng.random((400, width)), rng.integers(0, 2, 400).astype(float)).save(path)
    return path


def test_a_failed_candidate_keeps_its_map_and_the_installed_model_is_untouched(
    tmp_path: Path,
) -> None:
    rng = np.random.default_rng(0)
    corpus = tmp_path / "corpus"
    _corpus(corpus, 80, rng)
    candidate = _noise_model(tmp_path / "candidate" / "model.txt", rng)
    installed = _noise_model(tmp_path / "installed.txt", rng)
    before = installed.read_bytes()

    comparison, fit, report, replaced = calibrate_model(
        candidate, [corpus], installed_path=installed, out=installed, keep_map=True
    )

    assert not replaced
    assert not comparison.beats_vp_share
    assert fit + report == 80
    assert calibration_sidecar(candidate).is_file()
    assert installed.read_bytes() == before
    assert not calibration_sidecar(installed).exists()


def test_keeping_the_map_refuses_to_touch_the_installed_model(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)
    corpus = tmp_path / "corpus"
    _corpus(corpus, 8, rng)
    installed = _noise_model(tmp_path / "installed.txt", rng)

    with pytest.raises(ValueError, match="installed model"):
        calibrate_model(
            installed, [corpus], installed_path=installed, out=tmp_path / "out.txt", keep_map=True
        )
    assert not calibration_sidecar(installed).exists()
