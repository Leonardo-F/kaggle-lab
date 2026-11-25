"""Archive-time merger of two validated Santa 2026 submission CSVs.

This is post-processing tooling, not a solver and not an independent algorithm
version: it never generates programs and never reads a historical answer as a
solving input.  Both inputs are fully re-verified with the repository's single
``src/verify.py`` verifier before any program is compared.  For every puzzle the
shorter program wins (parsed JSON list length, not string/row length); the
second input wins ties because it is the newer/better candidate.  The merged
CSV is written to a temporary file in the output directory, independently
verified, and only then atomically published.

The module is not imported by ``algorithms/solver.py`` or the default solver
CLI (``graph_solver.py``), and ``checkpoint.py`` does not treat it as solver
source.

Usage::

    python src/merge_submissions.py <puzzles.csv> <first.csv> <second.csv> -o <output.csv> [--expect-score N]
"""

import argparse
import csv
import json
import os
from pathlib import Path
import tempfile

from verify import verify

PUZZLE_COLUMNS = {"id", "starting_values", "targets", "value_limit", "registers"}


def _read_puzzles(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not PUZZLE_COLUMNS <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: expected an official puzzle CSV")
        rows = list(reader)
    ids = [row["id"] for row in rows]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError(f"{path}: expected nonempty puzzles with unique IDs")
    return rows


def _read_programs(path, puzzle_ids):
    """Map id to parsed program; the path must already have passed verify()."""
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    programs = {row["id"]: json.loads(row["program"]) for row in rows}
    if set(programs) != puzzle_ids:
        raise ValueError(f"{path}: puzzle IDs do not match the puzzle file")
    return programs


def merge(puzzles_path, first_path, second_path, output_path, expect_score=None):
    """Merge two verified submissions and publish a verified output CSV.

    ``first`` is the older/worse candidate, ``second`` the newer/better one and
    the tie-breaker.  Returns the JSON summary printed by the CLI.
    """
    puzzles_path = Path(puzzles_path)
    first_path = Path(first_path)
    second_path = Path(second_path)
    output_path = Path(output_path)

    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}")

    rows = _read_puzzles(puzzles_path)
    puzzle_ids = [row["id"] for row in rows]

    first_report = verify(puzzles_path, first_path)
    second_report = verify(puzzles_path, second_path)
    first = _read_programs(first_path, set(puzzle_ids))
    second = _read_programs(second_path, set(puzzle_ids))

    merged = {}
    from_first = from_second = tie = 0
    for pid in puzzle_ids:
        if len(first[pid]) < len(second[pid]):
            merged[pid] = first[pid]
            from_first += 1
        else:
            merged[pid] = second[pid]
            from_second += 1
            if len(first[pid]) == len(second[pid]):
                tie += 1
    score = sum(len(program) for program in merged.values())
    max_steps = max((len(program) for program in merged.values()), default=0)
    if expect_score is not None and score != expect_score:
        raise ValueError(f"expected score {expect_score}, got {score}")

    descriptor, temp_name = tempfile.mkstemp(
        dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("id", "program"))
            for pid in puzzle_ids:
                writer.writerow((pid, json.dumps(merged[pid], separators=(",", ":"))))
        output_report = verify(puzzles_path, temp_path)
        if (
            output_report["validated"] != len(puzzle_ids)
            or output_report["score"] != score
            or output_report["max_steps"] != max_steps
        ):
            raise ValueError("merged output failed independent verification")
        os.replace(temp_path, output_path)
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise
    finally:
        temp_path.unlink(missing_ok=True)

    expect = None
    if expect_score is not None:
        expect = {"expected": expect_score, "actual": score, "ok": True}
    return {
        "puzzles": len(puzzle_ids),
        "validated": output_report["validated"],
        "score": score,
        "max_steps": max_steps,
        "from_first": from_first,
        "from_second": from_second,
        "tie": tie,
        "inputs": {
            "puzzles": {
                "path": str(puzzles_path),
                "sha256": first_report["puzzles_sha256"],
            },
            "first": {
                "path": str(first_path),
                "sha256": first_report["submission_sha256"],
                "score": first_report["score"],
                "max_steps": first_report["max_steps"],
            },
            "second": {
                "path": str(second_path),
                "sha256": second_report["submission_sha256"],
                "score": second_report["score"],
                "max_steps": second_report["max_steps"],
            },
        },
        "output": {
            "path": str(output_path),
            "sha256": output_report["submission_sha256"],
        },
        "expect_score": expect,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("first", type=Path, help="older or worse input")
    parser.add_argument("second", type=Path, help="newer or better input; wins ties")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument(
        "--expect-score",
        type=int,
        help="fail before writing unless the merged score matches",
    )
    args = parser.parse_args(argv)
    try:
        summary = merge(
            args.puzzles, args.first, args.second, args.output, args.expect_score
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    main()
