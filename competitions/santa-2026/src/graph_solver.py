"""Solve Santa puzzles independently with the current graph-search portfolio."""
import argparse
import csv
import json
import os
from pathlib import Path

# Match the frozen research runner's recommended single-threaded numerical libraries.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from algorithms.solver import SOLVER_VERSION
from algorithms.native import build as native_build
from checkpoint import run, sha

DEFAULT_VERSION = SOLVER_VERSION
SPLITS = Path(__file__).resolve().parent / "algorithms" / "splits.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default=SOLVER_VERSION, help="compatibility flag; only the current version is supported")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after", type=int, help="maximum new group tasks; two groups per puzzle; do not export")
    parser.add_argument("--split", choices=("dev", "holdout", "all"), default="all")
    args = parser.parse_args()
    if args.version != SOLVER_VERSION:
        parser.error(f"Only {SOLVER_VERSION} is supported; use Git history for old implementations")
    if args.jobs < 1 or (args.stop_after is not None and args.stop_after < 0):
        parser.error("jobs must be positive and stop-after nonnegative")
    if (args.resume or args.stop_after is not None) and args.checkpoint is None:
        parser.error("--resume and --stop-after require --checkpoint")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    if args.checkpoint is not None and args.checkpoint.exists() != args.resume:
        parser.error("use --resume with an existing checkpoint only")
    if args.checkpoint is not None and args.checkpoint.resolve() in (args.puzzles.resolve(), args.output.resolve()):
        parser.error("checkpoint, puzzle input and output must be different files")
    try:
        with args.puzzles.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not {"id", "starting_values", "targets", "value_limit", "registers"} <= set(reader.fieldnames or []):
                raise ValueError("expected an official puzzle CSV")
            raw = list(reader)
        rows = {row["id"]: row for row in raw}
        if not raw or len(raw) != len(rows):
            raise ValueError("expected nonempty input with unique puzzle IDs")
        if args.split != "all":
            splits = json.loads(SPLITS.read_text())
            if sha(args.puzzles) != splits["sha256"]:
                raise ValueError("dev/holdout require the exact official puzzle CSV")
            rows = {pid: rows[pid] for pid in splits[args.split]}
        manifest = native_build.ensure_built()
        report = run(args.puzzles, rows, args.output, manifest, checkpoint=args.checkpoint,
                     resume=args.resume, jobs=args.jobs, split=args.split, limit=args.stop_after)
        if report is not None:
            print(json.dumps(report, indent=2))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
