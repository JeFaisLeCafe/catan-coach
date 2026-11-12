"""Keep the published value-table calibration and strength report interpretable."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from catan_coach.domain.experiment_report import wilson
from catan_coach.domain.manifest import CorpusManifest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/experiments/value-table-candidate"


def test_published_value_table_report() -> None:
    report = json.loads((ARTIFACTS / "report.json").read_text())
    verification = json.loads((ARTIFACTS / "verification.json").read_text())
    plan = json.loads((ARTIFACTS / "plan.json").read_text())
    corpus = json.loads((ARTIFACTS / "corpus.json").read_text())
    preregistered = ROOT / ".scratch/strategy-lab/plans/11-value-table-strength.json"

    assert (ARTIFACTS / "plan.json").read_bytes() == preregistered.read_bytes()
    assert report["scheduled"] == report["completed"] == 2000
    assert report["dropped"] == report["terminal_failures"] == report["missing"] == 0
    assert report["valid"] and not report["source_dirty"]
    assert report["source_commit"] == verification["source_commit"]
    assert report["base_seed"] == plan["base_seed"] == 50000
    assert verification["seed_range"] == [50000, 51999]
    assert report["candidate"]["search_simulations"] == 4
    assert report["candidate"]["explore"] is False
    assert report["candidate"]["model_hash"] == verification["model_sha256"]
    assert report["candidate"]["sidecar_hash"] == verification["sidecar_sha256"]
    assert report["opponent"]["kind"] == "value"

    proportion = report["wins"]
    assert (proportion["successes"], proportion["count"]) == (125, 2000)
    expected = wilson(125, 2000)
    assert proportion["lower"] == pytest.approx(expected.lower)
    assert proportion["upper"] == pytest.approx(expected.upper)
    assert report["attrition_as_losses"] == report["attrition_as_wins"] == proportion
    assert proportion["upper"] < 0.25
    assert verification["decision"] == "loses"
    assert [seat["wins"] for seat in report["seats"]] == [41, 26, 39, 19]
    assert verification["pilot"]["outcomes_read"] is False

    manifest = CorpusManifest.from_json(json.dumps(corpus["manifest"]))
    assert manifest.player_kind == "mixed"
    assert manifest.opponent == "value"
    assert (manifest.search_simulations, manifest.exploration) == (4, False)
    assert (manifest.base_seed, manifest.requested_games) == (40000, 2000)
    assert (manifest.games_finished, manifest.games_dropped) == (2000, 0)
    assert not manifest.dirty_tree
    assert corpus["candidate_wins"] == 65
    assert corpus["games_by_split"] == {"train": 1576, "validation": 424}

    calibration = (ARTIFACTS / "calibration.txt").read_text()
    for name in ("constant(1/4)", "vp-share(T=2.0)", "installed"):
        line = next(
            row
            for row in calibration.splitlines()
            if row.startswith(f"brier difference, candidate minus {name}:")
        )
        upper = float(line.rsplit(",", 1)[1].strip(" ]"))
        assert upper < 0
    assert "Installed model.txt" in calibration
    for name, digest in verification["artifact_sha256"].items():
        assert hashlib.sha256((ARTIFACTS / name).read_bytes()).hexdigest() == digest
