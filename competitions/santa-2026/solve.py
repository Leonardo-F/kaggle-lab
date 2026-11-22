"""Build or validate Kaggle Santa 2026 calculator programs (standard library)."""

import argparse
import csv
import json
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from collections.abc import Iterator
from math import isqrt
from pathlib import Path

REGISTERS = 48
MAX_STEPS = 4096
MAX_BYTES = 131072
BASES = (2, 3, 4, 5, 7, 8, 11, 16)
WIDE_BASES = ((31, 12), (48, 16), (64, 16), (81, 12), (128, 16), (256, 16), (512, 16))
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
        self.limit = puzzle.limit
        self.missing = set(puzzle.targets).difference(puzzle.starting)
        self.live = OrderedDict((value, slot) for slot, value in enumerate(puzzle.starting))
        self.free = sorted(set(range(REGISTERS)).difference(self.live.values()), reverse=True)
        self.pinned: set[int] = set()
        self.program: Program = []

    def emit(self, value: int, op: str, a: int, b: int, keep: int | None = None) -> None:
        i, j = self.live[a], self.live[b]
        self.live.move_to_end(a)
        self.live.move_to_end(b)
        if self.free:
            dest = self.free.pop()
        else:
            discard = next(v for v in self.live if v not in self.pinned and v != keep)
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

    def split(self, target: int, base: int, signed: bool) -> tuple[int, int, str]:
        quotient, digit = divmod(target, base)
        if (signed and digit and (quotient + 1) * base <= self.limit
                and quotient not in self.live
                and (digit > base // 2 or quotient + 1 in self.live)):
            return quotient + 1, base - digit, "-"
        return quotient, digit, "+"

    def join_digits(self, target: int, base: int, quotient: int, digit: int, op: str) -> None:
        multiple = quotient * base
        if multiple not in self.live:
            self.emit(multiple, "*", quotient, base, keep=digit)
        if digit and target not in self.live:
            self.emit(target, op, multiple, digit)

    def build(self, target: int, base: int, signed: bool = False) -> None:
        if self.direct(target):
            return
        quotient, digit, op = self.split(target, base, signed)
        self.build(quotient, base, signed)
        self.join_digits(target, base, quotient, digit, op)

    def build_wide(self, target: int, base: int, digit_base: int, signed: bool) -> None:
        if target < base:
            self.build(target, digit_base, signed)
            return
        if self.direct(target):
            return
        quotient, digit, op = self.split(target, base, signed)
        if digit:
            self.build(digit, digit_base, signed)
        temporary_pin = digit and digit not in self.pinned
        if temporary_pin:
            self.pinned.add(digit)
        self.build_wide(quotient, base, digit_base, signed)
        if temporary_pin:
            self.pinned.remove(digit)
        self.join_digits(target, base, quotient, digit, op)

    def frontier(self) -> dict[int, tuple[str, int, int]]:
        """List distinct legal values reachable with one instruction."""
        values = sorted(self.live)
        reachable = {}
        for i, high in enumerate(values):
            for j in range(i + 1):
                low = values[j]
                for value, op in ((high + low, "+"), (high * low, "*"), (high - low, "-")):
                    if 0 < value <= self.limit and value not in self.live:
                        reachable.setdefault(value, (op, high, low))
                if high % low == 0 and high // low not in self.live:
                    reachable.setdefault(high // low, ("/", high, low))
        return reachable

    def bridge(self, reverse: bool) -> bool:
        """Make one intermediate that unlocks one or more missing targets."""
        reachable = self.frontier()
        links: dict[int, list[tuple[int, str, int, int]]] = defaultdict(list)
        for target in sorted(self.missing, reverse=reverse):
            producers = {}
            if target % 2 == 0:
                producers[target // 2] = ("+", target // 2, target // 2)
            root = isqrt(target)
            if root * root == target:
                producers[root] = ("*", root, root)
            for a in self.live:
                if target > a:
                    producers[target - a] = ("+", a, target - a)
                if a > target:
                    producers[a - target] = ("-", a, a - target)
                producers[target + a] = ("-", target + a, a)
                producers[target * a] = ("/", target * a, a)
                if target % a == 0:
                    producers[target // a] = ("*", a, target // a)
                if a % target == 0:
                    producers[a // target] = ("/", a, a // target)
            for mid in producers.keys() & reachable.keys():
                links[mid].append((target, *producers[mid]))
        if not links:
            return False
        mid = max(links, key=lambda value: (len(links[value]), -value))
        target, op, a, b = links[mid][0]
        keep = b if a == mid else a
        self.emit(mid, *reachable[mid], keep=keep)
        self.emit(target, op, a, b)
        return True

    def prepare_radix(self, base: int) -> None:
        if 1 not in self.live:
            seed = next(iter(self.live))
            self.emit(1, "/", seed, seed)
        self.pinned.update(value for value in self.live if value <= base)
        for digit in range(2, base + 1):
            if not self.missing:
                return
            if not self.direct(digit):
                self.emit(digit, "+", digit - 1, 1)
            self.pinned.add(digit)

    def run(self, base: int, reverse: bool, use_bridge: bool = False) -> Program:
        self.sweep(reverse)
        if not self.missing:
            return self.program
        if use_bridge:
            while self.missing and self.bridge(reverse):
                self.sweep(reverse)
            if not self.missing:
                return self.program
        base = min(base, max(self.missing))
        self.prepare_radix(base)
        self.sweep(reverse)
        for target in sorted(self.missing, reverse=reverse):
            if use_bridge:
                while self.missing and self.bridge(reverse):
                    self.sweep(reverse)
            if target in self.missing:
                self.build(target, base, signed=use_bridge)
                if use_bridge:
                    self.sweep(reverse)
        return self.program

    def run_wide(self, base: int, digit_base: int, reverse: bool, signed: bool) -> Program | None:
        self.sweep(reverse)
        if not self.missing or max(self.missing) < base:
            return None
        self.prepare_radix(digit_base)
        self.build(base, digit_base, signed)
        self.pinned.add(base)
        self.sweep(reverse)
        for target in sorted(self.missing, reverse=reverse):
            if target in self.missing:
                self.build_wide(target, base, digit_base, signed)
                self.sweep(reverse)
        return self.program


def trace_values(puzzle: Puzzle, program: Program) -> Iterator[tuple[str, int, int, int]]:
    """Decode an already constructed or validated program into value operations."""
    slots = list(puzzle.starting) + [None] * (REGISTERS - len(puzzle.starting))
    for op, i, j, d in program:
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
        yield op, a, b, value


def prune(puzzle: Puzzle, program: Program) -> Program:
    """Keep first target writes and the register definitions they depend on."""
    missing = set(puzzle.targets).difference(puzzle.starting)
    first_writes = set()
    for step, (_, _, _, value) in enumerate(trace_values(puzzle, program)):
        if value in missing:
            first_writes.add(step)
            missing.remove(value)

    needed = set()
    kept = []
    for step in range(len(program) - 1, -1, -1):
        op, i, j, d = program[step]
        if step in first_writes or d in needed:
            kept.append(program[step])
            needed.discard(d)
            needed.update((i, j))
    return kept[::-1]


def reuse_registers(puzzle: Puzzle, program: Program) -> Program:
    """Keep values across redundant definitions when register capacity permits."""
    trace = list(trace_values(puzzle, program))
    events = defaultdict(deque)
    for step, (_, a, b, value) in enumerate(trace):
        for operand in {a, b}:
            events[operand].append((step, True))
        events[value].append((step, False))

    live = {value: i for i, value in enumerate(puzzle.starting)}
    free = sorted(set(range(REGISTERS)).difference(live.values()), reverse=True)
    result = []
    for step, (op, a, b, value) in enumerate(trace):
        for touched in {a, b, value}:
            queue = events[touched]
            while queue and queue[0][0] == step:
                queue.popleft()
        if value in live:
            continue
        i, j = live[a], live[b]
        if free:
            dest = free.pop()
        else:
            discard = max(
                (v for v in live if not events[v] or not events[v][0][1]),
                key=lambda v: events[v][0][0] if events[v] else len(trace),
            )
            dest = live.pop(discard)
        live[value] = dest
        result.append((op, i, j, dest))
    return prune(puzzle, result)


def candidate_programs(puzzle: Puzzle) -> Iterator[Program | None]:
    for base in BASES:
        for reverse in (False, True):
            yield Builder(puzzle).run(base, reverse)
    for base in (5, 12, 20):
        for reverse in (False, True):
            yield Builder(puzzle).run(base, reverse, use_bridge=True)
    for base, digit_base in WIDE_BASES:
        for reverse, signed in ((False, False), (False, True), (True, True)):
            yield Builder(puzzle).run_wide(base, digit_base, reverse, signed)


def optimize(puzzle: Puzzle, reference: Program | None = None) -> Program:
    best = None
    if reference is not None:
        replay(puzzle, reference)
        best = prune(puzzle, reference)
        best = reuse_registers(puzzle, best)
        replay(puzzle, best)
    lower_bound = len(set(puzzle.targets).difference(puzzle.starting))
    if best is not None and len(best) == lower_bound:
        return best
    for raw in candidate_programs(puzzle):
        if raw is None:
            continue
        candidate = prune(puzzle, raw)
        if len(candidate) > MAX_STEPS:
            continue
        candidate = reuse_registers(puzzle, candidate)
        if len(encode(candidate)) > MAX_BYTES:
            continue
        replay(puzzle, candidate)
        if best is None or len(candidate) < len(best):
            best = candidate
            if len(best) == lower_bound:
                return best
    if best is None:
        raise ValueError("no program fits the limits; supply the official sample")
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


def solve_row(job: tuple[Puzzle, Program | None]) -> tuple[str, Program]:
    puzzle, reference = job
    try:
        return puzzle.id, optimize(puzzle, reference)
    except ValueError as error:
        raise ValueError(f"{puzzle.id}: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="generate programs")
    mode.add_argument("--check", type=Path, help="validate an existing program CSV")
    parser.add_argument("--reference", type=Path, help="optional official sample submission")
    parser.add_argument("--jobs", type=int, default=1, help="parallel solver workers")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    if args.check and args.reference:
        parser.error("--reference requires --output")
    try:
        puzzles = load_puzzles(args.puzzles)
        if args.check:
            programs = load_programs(args.check, puzzles)
        else:
            reference = load_programs(args.reference, puzzles) if args.reference else {}
            jobs = ((puzzle, reference.get(puzzle_id)) for puzzle_id, puzzle in puzzles.items())
            if args.jobs == 1:
                programs = dict(map(solve_row, jobs))
            else:
                with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                    programs = dict(pool.map(solve_row, jobs, chunksize=4))
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
