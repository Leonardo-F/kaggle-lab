"""Original dependency-free baseline generator and numerical geometry checker.

For final competition certification, use the organizer's official high-precision metric:
https://www.kaggle.com/code/metric/squares-in-squares
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

COLUMNS = ("id", "n", "square_id", "x", "y", "angle")
DECIMAL = re.compile(r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?\Z")


@dataclass(frozen=True)
class Tile:
    x: float
    y: float
    angle: float = 0.0


def grid_layout(n: int) -> list[Tile]:
    """Feasible row-major n-tile grid using ceil(sqrt(n)) columns."""
    if not 1 <= n <= 1000:
        raise ValueError("n must lie in [1, 1000]")
    columns = math.isqrt(n)
    if columns * columns < n:
        columns += 1
    return [Tile((i % columns) + 0.5, (i // columns) + 0.5, 0.0) for i in range(n)]


def extent(tiles: Iterable[Tile]) -> float:
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for tile in tiles:
        half = 0.5 * (abs(math.cos(tile.angle)) + abs(math.sin(tile.angle)))
        min_x = min(min_x, tile.x - half)
        max_x = max(max_x, tile.x + half)
        min_y = min(min_y, tile.y - half)
        max_y = max(max_y, tile.y + half)
    return max(max_x - min_x, max_y - min_y)


def _intersects(a: Tile, b: Tile, tolerance: float = 1e-9) -> bool:
    dx, dy = b.x - a.x, b.y - a.y
    if abs(dx) >= math.sqrt(2) + tolerance or abs(dy) >= math.sqrt(2) + tolerance:
        return False
    ca, sa = math.cos(a.angle), math.sin(a.angle)
    cb, sb = math.cos(b.angle), math.sin(b.angle)
    for ax, ay in ((ca, sa), (-sa, ca), (cb, sb), (-sb, cb)):
        ra = 0.5 * (abs(ca * ax + sa * ay) + abs(-sa * ax + ca * ay))
        rb = 0.5 * (abs(cb * ax + sb * ay) + abs(-sb * ax + cb * ay))
        projection = abs(dx * ax + dy * ay)
        if ra + rb - projection <= tolerance:
            return False
    return True


def validate_layout(tiles: list[Tile]) -> list[tuple[int, int]]:
    """Report intersecting tile index pairs using a 2-unit spatial hash.

    Uses floating-point SAT; not equivalent to Kaggle interval certification.
    """
    if not tiles or not all(all(math.isfinite(v) for v in (t.x, t.y, t.angle)) for t in tiles):
        raise ValueError("Layout is empty or contains non-finite parameters")
    buckets: dict[tuple[int, int], list[int]] = {}
    overlaps: list[tuple[int, int]] = []
    for i, tile in enumerate(tiles):
        bx, by = math.floor(tile.x / 2), math.floor(tile.y / 2)
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for j in buckets.get((bx + ox, by + oy), []):
                    if _intersects(tiles[j], tile):
                        overlaps.append((j, i))
        buckets.setdefault((bx, by), []).append(i)
    return overlaps


def write_baseline(output: Path, max_n: int = 1000) -> int:
    if not 1 <= max_n <= 1000:
        raise ValueError("max_n must lie in [1, 1000]")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        index = 0
        for n in range(1, max_n + 1):
            for square_id, tile in enumerate(grid_layout(n)):
                writer.writerow((index, n, square_id, tile.x, tile.y, tile.angle))
                index += 1
    return index


def _parse_float(text: str, line_no: int) -> float:
    if not DECIMAL.fullmatch(text.strip()):
        raise ValueError(f"line {line_no}: expected finite decimal literal: {text!r}")
    number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"line {line_no}: non-finite coordinate")
    return number


def validate_csv(input_path: Path, complete: bool = False) -> dict[str, float | int]:
    """Check row numbering, puzzle membership, geometry, and local sum score."""
    total_score, groups, rows = 0.0, 0, 0
    current_n = 0
    current_tiles: list[Tile] = []

    def finish() -> float:
        if not current_tiles:
            return 0.0
        if len(current_tiles) != current_n:
            raise ValueError(f"n={current_n}: expected {current_n} tiles, got {len(current_tiles)}")
        pairs = validate_layout(current_tiles)
        if pairs:
            raise ValueError(f"n={current_n}: {len(pairs)} intersecting pairs (first={pairs[0]})")
        length = extent(current_tiles)
        if length < math.sqrt(current_n) - 1e-7:
            raise ValueError(f"n={current_n}: enclosing side below area lower bound")
        return max(0.0, length / math.sqrt(current_n) - 1)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"Invalid CSV columns; expected {','.join(COLUMNS)}")
        for line_no, row in enumerate(reader, start=2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"line {line_no}: malformed CSV row")
            try:
                index, puzzle, square_id = int(row["id"]), int(row["n"]), int(row["square_id"])
            except ValueError as exc:
                raise ValueError(f"line {line_no}: non-integer id/n/square_id") from exc
            if index != rows:
                raise ValueError(f"line {line_no}: id expected {rows}, got {index}")
            if not 1 <= puzzle <= 1000:
                raise ValueError(f"line {line_no}: n outside range")
            if puzzle != current_n:
                if puzzle != current_n + 1:
                    if current_n == 0 and not complete:
                        pass  # permit a single-puzzle export, starting at any n
                    else:
                        raise ValueError(f"line {line_no}: n must progress consecutively")
                total_score += finish()
                groups += bool(current_tiles)
                current_n, current_tiles = puzzle, []
            if square_id != len(current_tiles):
                raise ValueError(f"line {line_no}: square_id expected {len(current_tiles)}, got {square_id}")
            current_tiles.append(Tile(_parse_float(row["x"], line_no), _parse_float(row["y"], line_no), _parse_float(row["angle"], line_no)))
            rows += 1
    total_score += finish()
    groups += bool(current_tiles)
    if complete and (groups != 1000 or rows != 500500):
        raise ValueError(f"Incomplete submission: {groups} puzzles / {rows} rows; expected 1000 / 500500")
    if groups == 0:
        raise ValueError("No data rows")
    return {"puzzles": groups, "rows": rows, "score_local": total_score}


def main() -> None:
    parser = argparse.ArgumentParser(description="Squares in Squares: original baseline and local validator")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("generate", help="Generate deterministic, valid baseline submission")
    make.add_argument("--output", type=Path, default=Path("submission.csv"))
    make.add_argument("--max-n", type=int, default=1000)
    check = sub.add_parser("validate", help="Validate a saved submission file")
    check.add_argument("--input", type=Path, required=True)
    check.add_argument("--complete", action="store_true", help="Require n=1..1000 and all 500,500 rows")
    args = parser.parse_args()
    if args.command == "generate":
        count = write_baseline(args.output, args.max_n)
        print(f"Created {args.output}: {count:,} rows")
    elif args.command == "validate":
        summary = validate_csv(args.input, args.complete)
        print("Local numerical validation passed:", summary)
        print("NOTE: Run the official Kaggle metric for high-precision collision certification.")


if __name__ == "__main__":
    main()
