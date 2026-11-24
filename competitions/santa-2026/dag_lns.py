"""Refine Santa calculator programs by large-neighborhood search on shared value DAGs."""

import argparse
import csv
import math
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from solve import (
    MAX_BYTES,
    MAX_STEPS,
    REGISTERS,
    encode,
    load_programs,
    load_puzzles,
    replay,
    trace_values,
)


def operand_options(target, known):
    """Write the target as one operation using the given known operand."""
    return (
        ("+", target - known, False),
        ("-", known - target, False),
        ("-", known + target, True),
        ("*", target // known if target % known == 0 else 0, False),
        ("/", target * known, True),
        ("/", known // target if known % target == 0 else 0, False),
    )


def emit(s, t, vals, idx, opts, choice, mode):
    """Allocate registers to the chosen DAG in one of three traversal orders."""
    ns = len(set(s))
    seen = set(range(ns))
    order = []
    roots = {idx[v] for v in t}

    def visit(i):
        if i in seen:
            return
        _, a, b = opts[i][choice[i]]
        visit(a)
        visit(b)
        seen.add(i)
        order.append(i)

    for i in sorted(
        roots, reverse=mode == 1, key=(lambda i: vals[i]) if mode == 2 else None
    ):
        visit(i)
    uses = [[] for _ in vals]
    cur = [0] * len(vals)
    for j, i in enumerate(order):
        _, a, b = opts[i][choice[i]]
        uses[a].append(j)
        uses[b].append(j)
    live = {idx[v]: i for i, v in enumerate(s)}
    prog = []

    def nextuse(i):
        return uses[i][cur[i]] if cur[i] < len(uses[i]) else 10**9

    def ensure(i, protect):
        if i in live:
            return
        o, a, b = opts[i][choice[i]]
        ensure(a, protect)
        ensure(b, protect | {a})
        ai, bi = live[a], live[b]
        free = set(range(REGISTERS)) - set(live.values())
        if free:
            d = min(free)
        else:
            cand = [k for k in live if k >= ns and k not in protect]
            if not cand:
                raise ValueError("pressure")
            d = live.pop(max(cand, key=nextuse))
        prog.append((o, ai, bi, d))
        live[i] = d
        if len(prog) > MAX_STEPS:
            raise ValueError("length")

    for i in order:
        _, a, b = opts[i][choice[i]]
        ensure(i, set())
        cur[a] += 1
        cur[b] += 1
        for k in list(live):
            if k >= ns and nextuse(k) == 10**9:
                live.pop(k)
    return prog


def search(puzzle, ref, rounds, seed):
    """Search alternative incoming edges of the reference program's value graph."""
    s, t, L = puzzle.starting, puzzle.targets, puzzle.limit
    vals = list(dict.fromkeys(s))
    idx = {v: i for i, v in enumerate(vals)}
    ns = len(vals)
    opts = [[] for _ in vals]
    for o, x, y, v in trace_values(puzzle, ref):
        if v not in idx:
            idx[v] = len(vals)
            vals.append(v)
            opts.append([(o, idx[x], idx[y])])
    N = len(vals)
    roots = {idx[v] for v in t}
    for j in range(ns, N):
        v = vals[j]
        seen = set(opts[j])
        get = idx.get
        for i in range(j):
            a = vals[i]
            for o, b, rev in operand_options(v, a):
                k = get(b, -1)
                if not 0 <= k < j:
                    continue
                e = (o, k, i) if rev else (o, i, k)
                if o in ("+", "*") and e[1] > e[2]:
                    e = (o, e[2], e[1])
                if e not in seen:
                    opts[j].append(e)
                    seen.add(e)
    # Construct a bounded pool of novel two-operation intermediates. Rank by
    # small numeric values, so arithmetic residues and divisors are well covered.
    # Each auxiliary depends only on original nodes earlier than its consumer.
    small = sorted(range(N), key=lambda i: (vals[i].bit_length(), i))[:72]
    pair = {}
    for ai, i in enumerate(small):
        a = vals[i]
        for k in small[: ai + 1]:
            b = vals[k]
            for v, o, x, y in (
                (a + b, "+", i, k),
                (a * b, "*", i, k),
                (a - b, "-", i, k),
                (b - a, "-", k, i),
                (a // b if a % b == 0 else 0, "/", i, k),
                (b // a if b % a == 0 else 0, "/", k, i),
            ):
                if not 0 < v <= L:
                    continue
                rank = max(i, k)
                oldpair = pair.get(v)
                if oldpair is None or rank < oldpair[0]:
                    pair[v] = (rank, o, x, y)
    aux = {}
    for j in range(ns, N):
        v = vals[j]
        seen = set(opts[j])
        candidates = []
        for i in range(j):
            a = vals[i]
            for o, b, rev in operand_options(v, a):
                if not 0 < b <= L:
                    continue
                if 0 <= idx.get(b, -1) < j:
                    continue
                hit = pair.get(b)
                if hit is None or hit[0] >= j:
                    continue
                _, op, x, y = hit
                candidates.append((max(i, x, y), i, o, b, rev, op, x, y))
        # Bound per-node branching; prefer a mix of earliest and random candidates.
        candidates.sort()
        rng0 = random.Random(seed + j)
        if len(candidates) > 24:
            candidates = candidates[:12] + rng0.sample(candidates[12:], 12)
        for _, i, o, b, rev, op, x, y in candidates:
            # Do not use an existing later value as a node: it can create cycles.
            key = (b, op, x, y)
            k = aux.get(key)
            if k is None:
                k = len(vals)
                aux[key] = k
                vals.append(b)
                opts.append([(op, x, y)])
            e = (o, k, i) if rev else (o, i, k)
            if e not in seen:
                opts[j].append(e)
                seen.add(e)
    N = len(vals)
    state = [0] * N
    refs = [0] * N
    cost = 0

    def add(i):
        nonlocal cost
        refs[i] += 1
        if refs[i] != 1 or i < ns:
            return
        cost += 1
        _, a, b = opts[i][state[i]]
        add(a)
        add(b)

    def rem(i):
        nonlocal cost
        refs[i] -= 1
        if refs[i] != 0 or i < ns:
            return
        cost -= 1
        _, a, b = opts[i][state[i]]
        rem(a)
        rem(b)

    def change(i, k):
        if state[i] == k:
            return
        active = refs[i] > 0
        if active:
            _, a, b = opts[i][state[i]]
            rem(a)
            rem(b)
        state[i] = k
        if active:
            _, a, b = opts[i][k]
            add(a)
            add(b)

    for i in roots:
        add(i)
    best_cost = cost
    best_state = state.copy()
    rng = random.Random(seed)
    mutable = [i for i in range(ns, N) if len(opts[i]) > 1]
    for step in range(rounds):
        active = [i for i in mutable if refs[i]]
        if not active:
            break
        sub = rng.sample(active, min(len(active), rng.choice([1, 2, 3, 5, 8])))
        prev = [(i, state[i]) for i in sub]
        before = cost
        for i in sub:
            if rng.random() < 0.35:
                change(i, rng.randrange(len(opts[i])))
        rng.shuffle(sub)
        for i in sub:
            ks = list(range(len(opts[i])))
            ks = ks if len(ks) <= 20 else rng.sample(ks, 20) + [state[i]]
            bk = state[i]
            c = cost
            for k in ks:
                change(i, k)
                if cost < c or (cost == c and rng.random() < 0.1):
                    bk, c = k, cost
            change(i, bk)
        temperature = max(0.12, 1.4 * (1 - step / rounds))
        if cost > before and rng.random() >= math.exp((before - cost) / temperature):
            for i, k in reversed(prev):
                change(i, k)
            assert cost == before
        if cost < best_cost:
            best_cost = cost
            best_state = state.copy()
    best = ref
    for m in range(3):
        try:
            candidate = emit(s, t, vals, idx, opts, best_state, m)
            if (
                replay(puzzle, candidate) < len(best)
                and len(encode(candidate).encode("utf-8")) <= MAX_BYTES
            ):
                best = candidate
        except (ValueError, RecursionError):
            pass
    return best


def optimize(job):
    puzzle, reference, rounds, seed = job
    try:
        return puzzle.id, search(puzzle, reference, rounds, seed)
    except RecursionError:
        # Long dependency chains can exceed Python's recursion limit.
        return puzzle.id, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if args.rounds < 0 or args.jobs < 1:
        parser.error("--rounds must be nonnegative and --jobs must be positive")

    try:
        puzzles = load_puzzles(args.puzzles)
        references = load_programs(args.reference, puzzles)
        jobs = (
            (puzzle, references[puzzle.id], args.rounds, args.seed + index)
            for index, puzzle in enumerate(puzzles.values(), 1)
        )
        if args.jobs == 1:
            programs = dict(map(optimize, jobs))
        else:
            with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                programs = dict(pool.map(optimize, jobs, chunksize=3))
        with args.output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("id", "program"))
            writer.writerows(
                (pid, encode(program)) for pid, program in programs.items()
            )
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"{error}\n")

    old_score = sum(map(len, references.values()))
    new_score = sum(map(len, programs.values()))
    print(
        f"Puzzles: {len(programs):,} | Reference: {old_score:,} | Instructions: {new_score:,}"
    )


if __name__ == "__main__":
    main()
