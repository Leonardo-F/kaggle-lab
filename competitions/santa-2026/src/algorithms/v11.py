"""Adapter for the frozen R16 portfolio and its official split runner."""
from pathlib import Path
import subprocess
import sys

from .common import replay

ROOT = Path(__file__).with_name("v11_frozen_fulltest")


def solve(row, config=None):
    if config:
        raise ValueError("V11 uses the frozen search configuration")
    from .v11_frozen_fulltest.variants.frozen17.run import ROUTES, work

    candidates = {}
    for group in ROUTES:
        result = work(group, row)
        for name, program in result["programs"].items():
            candidates[f"{group}/{name}"] = program
    scores = {name: replay(row, program) for name, program in candidates.items()}
    winner = min(scores, key=scores.get)
    return row["id"], candidates[winner], {"winner": winner, "scores": scores}


def batch(puzzles, db, output, jobs, split, limit):
    command = [
        sys.executable, "-E", str(ROOT / "variants/frozen17/run.py"),
        str(puzzles), "--db", str(db), "--jobs", str(jobs), "--split", split,
    ]
    if limit is None:
        command += ["--export", str(output)]
    else:
        command += ["--limit", str(limit)]
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, check=True)
