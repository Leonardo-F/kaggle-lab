"""Solve Santa puzzles independently from the official puzzle CSV.

The default version is the newest fully validated solver. Add ``--checkpoint``
to solve V7/V8 through a durable SQLite checkpoint that can be resumed with
``--resume``; every exported submission is replayed by the independent verifier.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from importlib import import_module
import json
from pathlib import Path
import time

import checkpoint as checkpoint_engine
from verify import verify

DEFAULT_VERSION = "v7"


def solve_job(job):
    version, row, rounds, extra, parameters = job
    solver = import_module(f"algorithms.{version}")
    if version == "v6":
        return solver.optimize_v6((row, rounds, extra))[1]
    if version == "v7":
        return solver.optimize((row, parameters["portfolio"], parameters["path_rounds"],
                                parameters["schedule"], parameters["retain_v6_graphs"]))[1]
    if version == "v8":
        return solver.optimize(row)[1]
    if version == "v5":
        return solver.optimize_v5((row, True, True))[1]
    if version == "v4":
        return solver.optimize_v4((row, True))[1]
    return solver.optimize((row, True))[1]


def main():
    versions = sorted((p.stem for p in Path(__file__).with_name("algorithms").glob("v[0-9]*.py")
                       if p.stem[1:].isdigit()), key=lambda v: int(v[1:]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("--version", choices=versions, default=DEFAULT_VERSION)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=180, help="V6 node search rounds")
    parser.add_argument("--no-extra", action="store_true", help="V6: disable extra constructor")
    parser.add_argument("--portfolio", type=int, default=3, help="V7: extra constructor plans")
    parser.add_argument("--path-rounds", type=int, default=400, help="V7: path union annealing rounds")
    parser.add_argument("--retain-v6-graphs", action="store_true", help="V7: keep internal V6 graphs")
    parser.add_argument("--no-schedule", action="store_true", help="V7: disable register scheduling")
    parser.add_argument("--checkpoint", type=Path, help="V7/V8: durable SQLite checkpoint")
    parser.add_argument("--resume", action="store_true", help="resume the identified checkpoint")
    parser.add_argument("--stop-after", type=int, help="schedule at most N unsolved puzzles")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.rounds < 0 or args.portfolio < 0 or args.path_rounds < 0:
        parser.error("search parameters must be nonnegative")
    if args.stop_after is not None and args.stop_after < 0:
        parser.error("--stop-after must be nonnegative")
    if args.resume and args.checkpoint is None:
        parser.error("--resume requires --checkpoint")
    if args.stop_after is not None and args.checkpoint is None:
        parser.error("--stop-after requires --checkpoint")
    if args.checkpoint is not None and args.version not in checkpoint_engine.CONFIGS:
        parser.error("--checkpoint is only available for v7 and v8")
    if args.checkpoint is not None and args.output.exists() and not args.resume:
        parser.error(f"output already exists: {args.output}")
    if args.checkpoint is None and args.output.exists():
        parser.error(f"output already exists: {args.output}")

    with args.puzzles.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id", "starting_values", "targets", "value_limit", "registers"}
        if not required <= set(reader.fieldnames or []):
            parser.error("expected an official puzzle CSV")
        rows = list(reader)
    if not rows or len({row["id"] for row in rows}) != len(rows):
        parser.error("expected nonempty input with unique puzzle IDs")

    parameters = {
        "portfolio": args.portfolio,
        "path_rounds": args.path_rounds,
        "schedule": not args.no_schedule,
        "retain_v6_graphs": args.retain_v6_graphs,
    } if args.version == "v7" else None
    if args.checkpoint is not None:
        try:
            checkpoint_engine.run_checkpoint(
                args.puzzles, args.output, args.checkpoint, args.version,
                jobs=args.jobs, resume=args.resume, stop_after=args.stop_after,
                parameters=parameters,
            )
        except ValueError as exc:
            parser.exit(2, f"error: {exc}\n")
        return

    start = time.monotonic()
    jobs = ((args.version, row, args.rounds, not args.no_extra, parameters) for row in rows)
    score = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        programs = []
        for count, program in enumerate(executor.map(solve_job, jobs), start=1):
            programs.append(program)
            score += len(program)
            if count % 50 == 0 or count == len(rows):
                print(f"{count}/{len(rows)} · {score} instructions · "
                      f"{time.monotonic() - start:.1f}s", flush=True)

    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("id", "program"))
        for row, program in zip(rows, programs):
            writer.writerow((row["id"], json.dumps(program, separators=(",", ":"))))
    try:
        report = verify(args.puzzles, args.output)
    except Exception:
        args.output.unlink()
        raise
    report.update(version=args.version, jobs=args.jobs,
                  elapsed_seconds=round(time.monotonic() - start, 1))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
