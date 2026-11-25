"""Independent Santa 2026 solver: the frozen V9 pipeline.

The current release exposes exactly one solver (``v9``).  Historical V1-V8
research implementations are preserved in Git; use a detached worktree of the
revision printed by ``--version <historical>`` to reproduce them.  The frozen
V9 sources build two C++17 constructor kernels before solving; the build is
preflighted once here so worker processes only read the same binaries.

Add ``--checkpoint`` for a durable SQLite run that can be resumed with
``--resume``; a submission is exported only when every input puzzle has been
solved and replayed by the independent verifier.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import time

import checkpoint as checkpoint_engine
from algorithms.native import build as native_build
from algorithms.solver import SOLVER_VERSION
from verify import verify

DEFAULT_VERSION = SOLVER_VERSION
LEGACY_REVISION = "9337a3549bea09257cbf36ae1f8da2cbd452942b"
HISTORICAL_REVISIONS = {**{f"v{i}": LEGACY_REVISION for i in range(1, 8)},
                        "v8": "287519977aa85a19ef9e3074e6bfd2b9e578b5c3"}


def solve_job(row):
    from algorithms.solver import solve
    return solve(row)[1]


def _reject_legacy_version(parser, version):
    revision = HISTORICAL_REVISIONS.get(version)
    if revision is None:
        parser.error(
            f"unknown solver version: {version!r}; the current solver is {DEFAULT_VERSION}. "
            f"Historical V1-V7 live at Git commit {LEGACY_REVISION} and V8 at "
            f"{HISTORICAL_REVISIONS['v8']}."
        )
    parser.error(
        f"--version {version} is not part of the current solver; only {DEFAULT_VERSION} is available. "
        f"Historical {version} is preserved at Git commit {revision}. "
        "Reproduce it from a detached worktree instead:\n"
        f"  git worktree add --detach ../kaggle-lab-santa-{version} {revision}\n"
        "  cd ../kaggle-lab-santa-"
        f"{version}/competitions/santa-2026\n"
        f"  python src/graph_solver.py <puzzles.csv> --version {version} "
        "--output <output.csv> --jobs 8"
    )


def preflight(parser):
    """Build (or verify) the frozen native constructors before any solving."""
    try:
        manifest = native_build.ensure_built()
    except (RuntimeError, OSError) as exc:
        parser.exit(2, f"error: native constructor build failed: {exc}\n")
    compiler = manifest["compiler"]
    print(f"native: {compiler['family']} {compiler['version']} · "
          f"build={native_build.BUILD_DIR}", flush=True)
    for kernel, info in manifest["binaries"].items():
        print(f"native: {kernel} sha256={info['sha256']}", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--checkpoint", type=Path, help="durable SQLite checkpoint")
    parser.add_argument("--resume", action="store_true", help="resume the identified checkpoint")
    parser.add_argument("--stop-after", type=int, help="schedule at most N unsolved puzzles")
    args = parser.parse_args()
    if args.version != DEFAULT_VERSION:
        _reject_legacy_version(parser, args.version)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.stop_after is not None and args.stop_after < 0:
        parser.error("--stop-after must be nonnegative")
    if args.resume and args.checkpoint is None:
        parser.error("--resume requires --checkpoint")
    if args.stop_after is not None and args.checkpoint is None:
        parser.error("--stop-after requires --checkpoint")
    if args.output.exists() and not args.resume:
        parser.error(f"output already exists: {args.output}")

    with args.puzzles.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id", "starting_values", "targets", "value_limit", "registers"}
        if not required <= set(reader.fieldnames or []):
            parser.error("expected an official puzzle CSV")
        rows = list(reader)
    if not rows or len({row["id"] for row in rows}) != len(rows):
        parser.error("expected nonempty input with unique puzzle IDs")

    preflight(parser)

    if args.checkpoint is not None:
        try:
            checkpoint_engine.run_checkpoint(
                args.puzzles, args.output, args.checkpoint, args.version,
                jobs=args.jobs, resume=args.resume, stop_after=args.stop_after,
            )
        except ValueError as exc:
            parser.exit(2, f"error: {exc}\n")
        return

    start = time.monotonic()
    score = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        programs = []
        for count, program in enumerate(executor.map(solve_job, rows), start=1):
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
