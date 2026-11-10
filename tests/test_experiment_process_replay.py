"""The real model/search Policy must replay across fresh interpreter processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.engine
ROOT = Path(__file__).resolve().parents[1]

_PROBE = """
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from catan_coach.domain.experiment import SourceProvenance, schedule
from catan_coach.engine.experiment import play_scheduled_game
from catan_coach.engine.experiment_store import freeze_config
from catan_coach.engine.lab import load_config
config = load_config(Path('.scratch/strategy-lab/plans/08-generation-7.json'))
plan = freeze_config(config, SourceProvenance('c' * 40, False))
games = schedule(plan)[:4]
if os.environ['PROBE_WORKERS'] == '0':
    results = [play_scheduled_game(g) for g in games]
else:
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(play_scheduled_game, games))
print(json.dumps([asdict(result) for result in results], sort_keys=True))
"""


def test_model_search_replays_across_process_hash_seeds() -> None:
    documents = []
    for seed in ("0", "1"):
        result = subprocess.run(
            [sys.executable, "-c", _PROBE],
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONHASHSEED": seed,
                "PROBE_WORKERS": "0" if seed == "0" else "2",
            },
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        documents.append(json.loads(result.stdout))
    assert documents[0] == documents[1]
