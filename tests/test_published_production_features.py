"""Keep the published production-features strength report interpretable."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from catan_coach.domain.experiment_report import wilson

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/experiments/production-features"


def test_published_production_features_report() -> None:
    report = json.loads((ARTIFACTS / "report.json").read_text())
    verification = json.loads((ARTIFACTS / "verification.json").read_text())
    preregistered = ROOT / ".scratch/strategy-lab/plans/12-production-features.json"

    assert (ARTIFACTS / "plan.json").read_bytes() == preregistered.read_bytes()
    assert report["scheduled"] == report["completed"] == 2000
    assert report["dropped"] == report["terminal_failures"] == report["missing"] == 0
    assert report["valid"] and not report["source_dirty"]
    assert report["source_commit"] == verification["source_commit"]
    assert report["base_seed"] == 80000
    assert report["candidate"]["search_simulations"] == 4
    assert report["candidate"]["explore"] is False
    assert report["candidate"]["model_hash"] == verification["model_sha256"]
    assert report["candidate"]["sidecar_hash"] == verification["sidecar_sha256"]
    assert report["opponent"]["kind"] == "value"

    wins = report["wins"]
    assert (wins["successes"], wins["count"]) == (1025, 2000)
    expected = wilson(1025, 2000)
    assert wins["lower"] == pytest.approx(expected.lower)
    assert report["attrition_as_losses"] == report["attrition_as_wins"] == wins
    assert wins["lower"] > verification["threshold"] == 0.30
    assert verification["decision"] == "reaches 30%"
    assert [seat["wins"] for seat in report["seats"]] == [280, 256, 243, 246]
    assert verification["pilot"]["outcomes_read"] is False
    for name, digest in verification["artifact_sha256"].items():
        assert hashlib.sha256((ARTIFACTS / name).read_bytes()).hexdigest() == digest
