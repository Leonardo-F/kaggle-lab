"""Solve Santa puzzles independently from the official puzzle CSV."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from importlib import import_module
import json
from pathlib import Path
import time

from verify import verify


def solve_job(job):
    version, row = job
    solver = import_module(f"algorithms.{version}")
    if version == "v5":
        return solver.optimize_v5((row, True, True))[1]
    if version == "v4":
        return solver.optimize_v4((row, True))[1]
    return solver.optimize((row, True))[1]


def main():
    versions = sorted(path.stem for path in
                      Path(__file__).with_name("algorithms").glob("v[1-5].py"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("--version", choices=versions, default=versions[-1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    with args.puzzles.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id", "starting_values", "targets", "value_limit", "registers"}
        if not required <= set(reader.fieldnames or []):
            parser.error("expected an official puzzle CSV")
        rows = list(reader)
    if not rows or len({row["id"] for row in rows}) != len(rows):
        parser.error("expected nonempty input with unique puzzle IDs")

    start = time.monotonic()
    jobs = ((args.version, row) for row in rows)
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
