"""Build or validate Kaggle Santa 2026 calculator programs (standard library)."""

import argparse
import csv
import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

REGISTERS = 48
MAX_STEPS = 4096
MAX_BYTES = 131072
BASES = (2, 3, 4, 5, 7, 8, 11, 16)
Instruction = tuple[str, int, int, int]
Program = list[Instruction]


@dataclass(frozen=True)
class Puzzle:
    id: str
    starting: tuple[int, ...]
    targets: tuple[int, ...]
    limit: int


def encode(program: Program) -> str:
    return json.dumps(program, separators=(",", ":"))


def replay(puzzle: Puzzle, program: Program) -> int:
    """Validate every instruction, including instructions after target coverage."""
    if not isinstance(program, list) or len(program) > MAX_STEPS:
        raise ValueError("invalid program length or type")
    slots = list(puzzle.starting) + [None] * (REGISTERS - len(puzzle.starting))
    missing = set(puzzle.targets).difference(puzzle.starting)
    for step, instruction in enumerate(program, 1):
        if not isinstance(instruction, (list, tuple)) or len(instruction) != 4:
            raise ValueError(f"step {step}: expected four instruction fields")
        op, i, j, d = instruction
        if any(type(k) is not int or not 0 <= k < REGISTERS for k in (i, j, d)):
            raise ValueError(f"step {step}: invalid register index")
        a, b = slots[i], slots[j]
        if a is None or b is None:
            raise ValueError(f"step {step}: undefined source register")
        if op == "+":
            value = a + b
        elif op == "-":
            value = a - b
        elif op == "*":
            value = a * b
        elif op == "/" and a % b == 0:
            value = a // b
        else:
            raise ValueError(f"step {step}: unknown operator or inexact division")
        if not 1 <= value <= puzzle.limit:
            raise ValueError(f"step {step}: result out of range")
        slots[d] = value
        missing.discard(value)
    if missing:
        raise ValueError(f"{len(missing)} missing targets, first: {min(missing)}")
    return len(program)


class Builder:
    def __init__(self, puzzle: Puzzle):
        self.missing = set(puzzle.targets).difference(puzzle.starting)
        self.live = OrderedDict((value, slot) for slot, value in enumerate(puzzle.starting))
        self.free = sorted(set(range(REGISTERS)).difference(self.live.values()), reverse=True)
        self.pinned: set[int] = set()
        self.program: Program = []

    def emit(self, value: int, op: str, a: int, b: int) -> None:
        i, j = self.live[a], self.live[b]
        self.live.move_to_end(a)
        self.live.move_to_end(b)
        if self.free:
            dest = self.free.pop()
        else:
            discard = next(v for v in self.live if v not in self.pinned)
            dest = self.live.pop(discard)
        self.program.append((op, i, j, dest))
        self.live[value] = dest
        self.missing.discard(value)

    def direct(self, value: int) -> bool:
        """Find one operation that makes value from two live values."""
        if value in self.live:
            self.live.move_to_end(value)
            return True
        for a in reversed(self.live):
            if value > a and value - a in self.live:
                self.emit(value, "+", a, value - a)
            elif value + a in self.live:
                self.emit(value, "-", value + a, a)
            elif value % a == 0 and value // a in self.live:
                self.emit(value, "*", a, value // a)
            elif value * a in self.live:
                self.emit(value, "/", value * a, a)
            else:
                continue
            return True
        return False

    def sweep(self, reverse: bool) -> None:
        while self.missing:
            count = len(self.missing)
            for value in sorted(self.missing, reverse=reverse):
                self.direct(value)
            if len(self.missing) == count:
                break

    def build(self, target: int, base: int) -> None:
        if self.direct(target):
            return
        quotient, digit = divmod(target, base)
        self.build(quotient, base)
        multiple = quotient * base
        if multiple != target:
            if multiple not in self.live:
                self.emit(multiple, "*", quotient, base)
            if target not in self.live:
                self.emit(target, "+", multiple, digit)
        elif target not in self.live:
            self.emit(target, "*", quotient, base)

    def run(self, base: int, reverse: bool) -> Program:
        self.sweep(reverse)
        if not self.missing:
            return self.program
        base = min(base, max(self.missing))
        if 1 not in self.live:
            seed = next(iter(self.live))
            self.emit(1, "/", seed, seed)
        self.pinned.update(value for value in self.live if value <= base)
        for digit in range(2, base + 1):
            if not self.missing:
                return self.program
            if not self.direct(digit):
                self.emit(digit, "+", digit - 1, 1)
            self.pinned.add(digit)
        if base < 2:
            return self.program
        self.sweep(reverse)
        for target in sorted(self.missing, reverse=reverse):
            if target in self.missing:
                self.build(target, base)
        return self.program


def prune(puzzle: Puzzle, program: Program) -> Program:
    """Keep first target writes and the register definitions they depend on."""
    seen = set(puzzle.starting)
    targets = set(puzzle.targets)
    slots = list(puzzle.starting) + [None] * (REGISTERS - len(puzzle.starting))
    first_writes = set()
    for step, (op, i, j, d) in enumerate(program):
        a, b = slots[i], slots[j]
        if op == "+":
            value = a + b
        elif op == "-":
            value = a - b
        elif op == "*":
            value = a * b
        else:
            value = a // b
        slots[d] = value
        if value in targets and value not in seen:
            first_writes.add(step)
            seen.add(value)

    needed = set()
    kept = []
    for step in range(len(program) - 1, -1, -1):
        op, i, j, d = program[step]
        if step in first_writes or d in needed:
            kept.append(program[step])
            needed.discard(d)
            needed.update((i, j))
    return kept[::-1]


def optimize(puzzle: Puzzle, reference: Program | None = None) -> Program:
    best = None
    if reference is not None:
        replay(puzzle, reference)
        best = prune(puzzle, reference)
        replay(puzzle, best)
    lower_bound = len(set(puzzle.targets).difference(puzzle.starting))
    for base in BASES:
        if best is not None and len(best) == lower_bound:
            break
        for reverse in (False, True):
            raw = Builder(puzzle).run(base, reverse)
            candidate = prune(puzzle, raw)
            if len(candidate) > MAX_STEPS or len(encode(candidate)) > MAX_BYTES:
                continue
            replay(puzzle, candidate)
            if best is None or len(candidate) < len(best):
                best = candidate
            if len(best) == lower_bound:
                return best
    if best is None:
        raise ValueError("no baseline fits program limits; supply the official sample")
    return best


def load_puzzles(path: Path) -> dict[str, Puzzle]:
    puzzles = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            puzzle_id = row["id"]
            start = json.loads(row["starting_values"])
            targets = json.loads(row["targets"])
            limit = int(row["value_limit"])
            if (not puzzle_id or puzzle_id in puzzles or int(row["registers"]) != REGISTERS
                    or not 1 <= limit <= 10**18 or not isinstance(start, list)
                    or not 1 <= len(start) <= REGISTERS or not isinstance(targets, list)
                    or any(type(v) is not int or not 1 <= v <= limit for v in start + targets)):
                raise ValueError(f"invalid puzzle row: {puzzle_id}")
            puzzles[puzzle_id] = Puzzle(puzzle_id, tuple(start), tuple(targets), limit)
    if not puzzles:
        raise ValueError("puzzle file is empty")
    return puzzles


def load_programs(path: Path, puzzles: dict[str, Puzzle]) -> dict[str, Program]:
    programs = {}
    csv.field_size_limit(MAX_BYTES)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["id", "program"]:
            raise ValueError("expected CSV header id,program")
        for row in reader:
            puzzle_id, cell = row["id"], row["program"]
            if None in row or puzzle_id not in puzzles or puzzle_id in programs:
                raise ValueError(f"invalid or duplicate puzzle ID: {puzzle_id}")
            if cell is None or len(cell.encode("utf-8")) > MAX_BYTES:
                raise ValueError(f"{puzzle_id}: invalid program cell size")
            try:
                program = json.loads(cell)
                replay(puzzles[puzzle_id], program)
            except ValueError as error:
                raise ValueError(f"{puzzle_id}: {error}") from error
            programs[puzzle_id] = program
    if programs.keys() != puzzles.keys():
        raise ValueError(f"{len(puzzles.keys() - programs.keys())} puzzle IDs missing")
    return programs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="generate programs")
    mode.add_argument("--check", type=Path, help="validate an existing program CSV")
    parser.add_argument("--reference", type=Path, help="optional official sample submission")
    args = parser.parse_args()
    if args.check and args.reference:
        parser.error("--reference requires --output")
    try:
        puzzles = load_puzzles(args.puzzles)
        if args.check:
            programs = load_programs(args.check, puzzles)
        else:
            reference = load_programs(args.reference, puzzles) if args.reference else {}
            programs = {}
            for puzzle_id, puzzle in puzzles.items():
                try:
                    programs[puzzle_id] = optimize(puzzle, reference.get(puzzle_id))
                except ValueError as error:
                    raise ValueError(f"{puzzle_id}: {error}") from error
            with args.output.open("w", encoding="utf-8", newline="") as destination:
                writer = csv.writer(destination)
                writer.writerow(("id", "program"))
                writer.writerows((pid, encode(program)) for pid, program in programs.items())
            if reference:
                print(f"Reference instructions: {sum(map(len, reference.values())):,}")
        print(f"Puzzles: {len(programs):,} | Total instructions: {sum(map(len, programs.values())):,}")
    except (ValueError, OSError, KeyError, TypeError, csv.Error) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
