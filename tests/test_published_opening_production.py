"""Keep the published opening-production report interpretable."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from pathlib import Path

import pytest

from catan_coach.domain.experiment_report import ExperimentReport, wilson

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/experiments/generation-7-opening-production"


def test_published_opening_production_report() -> None:
    report = json.loads((ARTIFACTS / "report.json").read_text())
    verification = json.loads((ARTIFACTS / "verification.json").read_text())
    plan = json.loads((ARTIFACTS / "plan.json").read_text())
    markdown = (ARTIFACTS / "report.md").read_text()

    assert set(report) == {field.name for field in fields(ExperimentReport)}
    assert report["scheduled"] == report["completed"] == 2000
    assert report["dropped"] == report["terminal_failures"] == report["missing"] == 0
    assert report["valid"] and not report["source_dirty"]
    assert report["source_commit"] == verification["source_commit"]
    assert report["base_seed"] == plan["base_seed"] == verification["seed_range"][0] == 40000
    assert verification["seed_range"][1] == 41999
    assert report["games_per_candidate_seat"] == plan["games_per_candidate_seat"] == 500
    assert report["candidate"]["search_simulations"] == 4
    assert report["candidate"]["explore"] is False
    assert report["candidate"]["model_hash"] == verification["model_sha256"]
    assert report["candidate"]["sidecar_hash"] == verification["sidecar_sha256"]
    assert report["opponent"]["kind"] == "value"
    assert report["vps_to_win"] == 10
    assert report["discard_limit"] == 7
    assert report["friendly_robber"] is False
    assert report["turn_limit"] == 1000

    proportion = report["wins"]
    assert proportion["successes"] == 65
    assert proportion["count"] == 2000
    expected = wilson(65, 2000)
    assert proportion["rate"] == pytest.approx(expected.rate)
    assert proportion["lower"] == pytest.approx(expected.lower)
    assert proportion["upper"] == pytest.approx(expected.upper)
    assert report["attrition_as_losses"] == report["attrition_as_wins"] == proportion
    assert proportion["upper"] < 0.25
    assert verification["decision"] == "loses"
    assert [seat["seat"] for seat in report["seats"]] == list(range(4))
    assert [seat["completed"] for seat in report["seats"]] == [500] * 4
    assert [seat["wins"] for seat in report["seats"]] == [18, 18, 15, 14]
    assert sum(seat["wins"] for seat in report["seats"]) == proportion["successes"]
    assert report["candidate_wins"]["games"] == 65
    assert report["candidate_losses"]["games"] == 1935
    assert report["opponents"]["games"] == 6000
    assert "65/2000 games" in markdown
    assert "2000 completed, 0 dropped, 0 terminal failures, 0 missing" in markdown
    for seat in report["seats"]:
        assert f"{seat['wins']}/{seat['completed']} completed" in markdown
    for name, digest in verification["artifact_sha256"].items():
        assert hashlib.sha256((ARTIFACTS / name).read_bytes()).hexdigest() == digest
