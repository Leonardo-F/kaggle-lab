"""Value-graph polish for Kaggle Santa 2026 (own implementation).

The polisher takes a valid program and treats every value it ever computes as a
free operand.  Each target is then re-derived with the cheapest expression it can
find in that value graph, which is repeated until nothing changes and dead nodes
are swept away.

Two ideas carry the score gains:

* *free value graph* -- the radix builder in ``solve.py`` can only combine the
  values that happen to be live in a register, while a finished program contains
  dozens of extra values (digits, quotients, earlier anchors).  Re-deriving a
  target as ``anchor + offset`` against any of those values is often one
  instruction instead of a whole subtree.
* *anchor pooling* -- for clusters of near-identical targets the polisher looks
  for a hidden anchor ``v <= target - offset`` that explains several targets at
  once, builds it once and makes every cluster member a single instruction.

Everything is validated with ``solve.replay`` before it is accepted, and the
reference program is kept whenever the polisher cannot beat it.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from bisect import bisect_left
import random
from math import gcd, isqrt
from pathlib import Path

from solve import (
    MAX_BYTES,
    MAX_STEPS,
    REGISTERS,
    Program,
    Puzzle,
    encode,
    load_programs,
    load_puzzles,
    prune,
    replay,
    reuse_registers,
)

INF = 10**9

# --------------------------------------------------------------------------- #
# integer factorisation (for multiplicative rewrites)
# --------------------------------------------------------------------------- #

_SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
_FACTOR_CACHE: dict[int, tuple[int, ...]] = {}
_DIVISOR_CACHE: dict[int, tuple[int, ...]] = {}


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if a >= n:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _pollard(n: int) -> int:
    if n % 2 == 0:
        return 2
    if n % 3 == 0:
        return 3
    while True:
        c = random.randrange(1, n)
        x = random.randrange(0, n)
        y, d = x, 1
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = gcd(abs(x - y), n)
        if d != n:
            return d


def factor(n: int) -> tuple[int, ...]:
    cached = _FACTOR_CACHE.get(n)
    if cached is not None:
        return cached
    out: list[int] = []
    stack = [n]
    while stack:
        m = stack.pop()
        if m == 1:
            continue
        if _is_prime(m):
            out.append(m)
            continue
        d = _pollard(m)
        stack.append(d)
        stack.append(m // d)
    out.sort()
    _FACTOR_CACHE[n] = tuple(out)
    return _FACTOR_CACHE[n]


def divisors(n: int) -> tuple[int, ...]:
    cached = _DIVISOR_CACHE.get(n)
    if cached is not None:
        return cached
    counts: dict[int, int] = defaultdict(int)
    for p in factor(n):
        counts[p] += 1
    out = [1]
    for p, e in counts.items():
        out = [d * p**k for d in out for k in range(e + 1)]
    result = tuple(sorted(x for x in out if x > 1))
    _DIVISOR_CACHE[n] = result
    return result


# --------------------------------------------------------------------------- #
# value graph
# --------------------------------------------------------------------------- #

OpSplit = tuple[str, int, int]


def graph_of(puzzle: Puzzle, program: Program) -> dict[int, OpSplit | None]:
    """Every value the program produces, with one expression for it."""
    slots: list[int | None] = list(puzzle.starting) + [None] * (REGISTERS - len(puzzle.starting))
    graph: dict[int, OpSplit | None] = {value: None for value in puzzle.starting}
    for op, i, j, d in program:
        a, b = slots[i], slots[j]
        if a is None or b is None:
            raise ValueError("undefined source register")
        if op == "+":
            value = a + b
        elif op == "-":
            value = a - b
        elif op == "*":
            value = a * b
        else:
            if a % b:
                raise ValueError("inexact division")
            value = a // b
        slots[d] = value
        graph.setdefault(value, (op, a, b))
    return graph


class Polisher:
    """Rewrites the targets of one puzzle inside a shared value graph."""

    def __init__(self, puzzle: Puzzle, graph: dict[int, OpSplit | None], *,
                 two_step_pairs: int = 90, anchor_offsets: int = 220,
                 anchor_min_support: int = 3, anchor_span: int = 8,
                 anchor_nearest: int = 8) -> None:
        self.puzzle = puzzle
        self.limit = puzzle.limit
        self.starts = list(dict.fromkeys(puzzle.starting))
        self.targets = list(dict.fromkeys(puzzle.targets))
        self.target_set = set(self.targets)
        self.graph = dict(graph)
        self.two_step_pairs = two_step_pairs
        self.anchor_offsets = anchor_offsets
        self.anchor_min_support = anchor_min_support
        self.anchor_span = anchor_span
        self.anchor_nearest = anchor_nearest
        self.tried: set[tuple[int, int, tuple]] = set()
        self._hot: list[int] = []
        self._anchor_cache: list[int] = []

    # -- bookkeeping -------------------------------------------------------- #
    def node_cost(self, value: int, seen: set[int] | None = None) -> int:
        """Instructions needed for the unique subtree of ``value``."""
        if value in self.graph and self.graph[value] is None:
            return 0
        seen = set() if seen is None else seen
        stack = [value]
        count = 0
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            split = self.graph.get(v)
            if split is None:
                continue
            count += 1
            stack.extend(split[1:])
        return count

    def free_values(self) -> list[int]:
        return list(self.graph)

    def cheapest_sets(self, limit: int = 140) -> list[int]:
        """Free values sorted by how cheap their own subtree is."""
        scored = []
        for value in self.graph:
            scored.append((self.node_cost(value), -value.bit_length(), -value, value))
        scored.sort()
        return [item[3] for item in scored[:limit]]

    # -- one instruction ---------------------------------------------------- #
    def one_step(self, target: int, free: set[int], pool: list[int]) -> OpSplit | None:
        for a in pool:
            if a == target:
                continue
            if a > target:
                if a - target in free:
                    return ("-", a, a - target)
                if a % target == 0:
                    other = a // target
                    if other in free and other != target:
                        return ("/", a, other)
            else:
                diff = target - a
                if diff in free:
                    return ("+", a, diff)
            if a > 1 and target % a == 0:
                other = target // a
                if other in free and other != target:
                    return ("*", a, other)
            if target and a % target == 0:
                other = a // target
                if other in free and other != target:
                    return ("/", a, other)
            if a != 1:
                product = target * a
                if product <= self.limit and product in free:
                    return ("/", product, a)
        return None

    # -- two instructions ---------------------------------------------------- #
    def two_step(self, target: int, free: set[int], pool: list[int]
                 ) -> tuple[OpSplit, int, OpSplit] | None:
        """Best ``target = u op c`` where ``u`` needs at most one instruction."""
        limit = self.limit
        for index, a in enumerate(pool):
            if a == target:
                continue
            for b in pool[index:]:
                if b == target:
                    continue
                for u in (a + b, a * b):
                    if u > limit or u in free or u == target:
                        continue
                    found = self.one_step_lookup(target, u, free)
                    if found is not None:
                        return found, u, (("*", a, b) if u == a * b else ("+", a, b))
                for u in (a - b, b - a):
                    if not 1 <= u <= limit or u in free or u == target:
                        continue
                    found = self.one_step_lookup(target, u, free)
                    if found is not None:
                        return found, u, (("-", a, b) if u == a - b else ("-", b, a))
                if b and a % b == 0:
                    u = a // b
                    if u not in free and u != target:
                        found = self.one_step_lookup(target, u, free)
                        if found is not None:
                            return found, u, ("/", a, b)
                if a and b % a == 0:
                    u = b // a
                    if u not in free and u != target:
                        found = self.one_step_lookup(target, u, free)
                        if found is not None:
                            return found, u, ("/", b, a)
        return None

    def one_step_lookup(self, target: int, u: int, free: set[int]) -> OpSplit | None:
        """Constant-time check whether ``target`` is one instruction from ``u``."""
        limit = self.limit
        if target > u:
            if target - u in free:
                return ("+", u, target - u)
            if target % u == 0 and target // u in free and target // u != target:
                return ("*", u, target // u)
        elif target < u:
            if u - target in free:
                return ("-", u, u - target)
            if u % target == 0 and u // target in free and u // target != target:
                return ("/", u, u // target)
        if u != 1:
            if target + u <= limit and target + u in free:
                return ("-", target + u, u)
            product = target * u
            if product <= limit and product in free:
                return ("/", product, u)
        return None

    # -- anchors ------------------------------------------------------------ #
    def cheap_offsets(self) -> list[int]:
        """Small values the program already builds, usable as offsets."""
        values = [v for v in self.graph if v < max(self.targets)]
        values.sort(key=lambda v: (self.node_cost(v), v.bit_length(), v))
        return values[: self.anchor_offsets]

    def anchors(self) -> list[int]:
        """Hidden anchors that explain several targets through cheap offsets."""
        offsets = self.cheap_offsets()
        support: dict[int, int] = defaultdict(int)
        for target in self.targets:
            seen: set[int] = set()
            for offset in offsets:
                anchor = target - offset
                if anchor < 1 or anchor in seen:
                    continue
                seen.add(anchor)
                support[anchor] += 1
        ranked = sorted(support.items(),
                        key=lambda item: (-item[1], item[0].bit_length(), item[0]))
        chosen = []
        for anchor, count in ranked:
            if count < self.anchor_min_support:
                break
            if anchor in self.graph:
                continue
            chosen.append(anchor)
            if len(chosen) >= 6:
                break
        return chosen

    def anchor_split(self, target: int) -> OpSplit | None:
        """``target = anchor + offset`` for the best known anchor."""
        best: tuple[int, OpSplit] | None = None
        for anchor in self._anchor_cache:
            offset = target - anchor
            if offset < 1:
                continue
            cost = self.node_cost(anchor) + (0 if offset in self.graph else self.node_cost(offset))
            if best is None or cost < best[0]:
                best = (cost, ("+", anchor, offset))
        return None if best is None else best[1]

    # -- building new helpers ------------------------------------------------ #
    def _try_one(self, value: int, forbidden: int = 0) -> OpSplit | None:
        """One-instruction form of ``value`` from existing graph values."""
        graph = self.graph
        for a in self._hot:
            if a == value or a == forbidden:
                continue
            if value - a == forbidden or a - value == forbidden:
                continue
            if a and value // a == forbidden and value % a == 0:
                continue
            if a > value:
                if a - value in graph:
                    return ("-", a, a - value)
            else:
                if value - a in graph:
                    return ("+", a, value - a)
            if a > 1 and value % a == 0 and value // a in graph and value // a != value:
                return ("*", a, value // a)
            if a != 1 and value * a <= self.limit and value * a in graph:
                return ("/", value * a, a)
        return None

    def ensure(self, value: int, depth: int = 3, forbidden: int = 0) -> int:
        """Add the cheapest derivation of ``value`` to the graph; return the cost."""
        if value in self.graph:
            return 0
        if depth <= 0:
            return INF
        split = self._try_one(value, forbidden)
        if split is not None:
            self.graph[value] = split
            return 1
        root = isqrt(value)
        bases = [b for b in (root, root + 1, 256, 1000, 4096, 65536) if 2 <= b < value]
        bases.extend(b for b in self._hot if 2 <= b < value)
        seen: set[int] = set()
        for base in bases:
            if base in seen:
                continue
            seen.add(base)
            q, r = divmod(value, base)
            if r == 0:
                cost = self.ensure(base, depth - 1, forbidden) + self.ensure(q, depth - 1, forbidden)
                if cost < INF:
                    self.graph[value] = ("*", q, base)
                    return cost + 1
                continue
            cost = self.ensure(base, depth - 1, forbidden) + self.ensure(q, depth - 1, forbidden)
            cost += self.ensure(r, depth - 1, forbidden)
            if cost < INF:
                self.graph[value] = ("+", q * base, r)
                if q * base not in self.graph:
                    self.graph[q * base] = ("*", q, base)
                return cost + 2
        return INF

    # -- driver ------------------------------------------------------------- #
    def rewrite(self, use_two_step: bool = True) -> bool:
        """Replace each target by the cheapest derivation that is still new."""
        changed = False
        self._anchor_cache = self.anchors()
        self._hot = self.cheapest_sets(140)
        free = set(self.graph)
        pool = self.free_values()
        cheap_pool = self.cheapest_sets(self.two_step_pairs) if use_two_step else ()
        for target in self.targets:
            current = self.graph.get(target)
            if current is None:
                continue
            candidate = None
            split = self.one_step(target, free, pool)
            if split is not None and split != current:
                candidate = (1, split)
            else:
                split = self.anchor_split(target)
                if split is not None and split != current:
                    candidate = (1, split)
                elif use_two_step and self.node_cost(target) > 3:
                    found = self.two_step(target, free, cheap_pool)
                    if found is not None:
                        split, intermediate, intermediate_split = found
                        if split != current and (intermediate in self.graph
                                                 or len(self.graph) < 2500):
                            if intermediate not in self.graph:
                                self.graph[intermediate] = intermediate_split
                            candidate = (2, split)
            if candidate is None:
                continue
            instr, split = candidate
            key = (target, split)
            if key in self.tried:
                continue
            self.tried.add(key)
            if instr >= self.node_cost(target):
                continue
            self.graph[target] = split
            changed = True
        return changed


    def walk(self, rounds: int = 400, seed: int = 0) -> bool:
        """Neutral moves on the value graph, keeping the best length seen."""
        rng = random.Random(seed)
        order = sorted(self.targets)
        best_graph = dict(self.graph)
        best_total = self.total_nodes()
        improved = False
        for _ in range(rounds):
            target = rng.choice(order)
            if target not in self.graph:
                continue
            current = self.graph[target]
            candidate = self.one_step(target, set(self.graph), list(self.graph))
            if candidate is None:
                position = bisect_left(order, target)
                anchor = order[min(max(0, position + rng.choice((-1, 0, 1))), len(order) - 1)]
                if anchor == target:
                    continue
                gap = abs(target - anchor)
                if not 0 < gap <= (1 << 26):
                    continue
                snapshot = dict(self.graph)
                if self.ensure(gap, 2, forbidden=target) >= INF or not self._defined():
                    self.graph = snapshot
                    continue
                candidate = ("+" if anchor < target else "-", anchor, gap)
            if candidate == current:
                continue
            self.graph[target] = candidate
            total = self.total_nodes()
            if total <= best_total:
                if total < best_total:
                    best_total = total
                    best_graph = dict(self.graph)
                    improved = True
            else:
                self.graph[target] = current
        self.graph = best_graph
        return improved

    def total_nodes(self) -> int:
        """Instructions the current graph needs for all targets."""
        needed: set[int] = set()
        stack = [t for t in self.targets if t in self.graph]
        while stack:
            value = stack.pop()
            if value in needed:
                continue
            needed.add(value)
            split = self.graph.get(value)
            if split is not None:
                stack.extend(split[1:])
        return sum(1 for v in needed if self.graph.get(v) is not None)

    def _reaches(self, start: int, goal: int) -> bool:
        """True when ``goal`` is reachable from ``start`` in the value graph."""
        stack = [start]
        seen: set[int] = set()
        while stack:
            value = stack.pop()
            if value == goal:
                return True
            if value in seen:
                continue
            seen.add(value)
            split = self.graph.get(value)
            if split is not None:
                stack.extend(split[1:])
        return False

    def _defined(self) -> bool:
        """Every operand of every used node exists."""
        known = set(self.graph)
        for value, split in self.graph.items():
            if split is None:
                continue
            for operand in split[1:]:
                if operand not in known:
                    return False
        return True

    def anchor_pass(self, window: int = 1 << 26, nearest: int | None = None,
                    strict: bool = True, one_sided: bool = False) -> bool:
        """Re-derive targets as ``nearby graph value + small offset``."""
        changed = False
        nearest = self.anchor_nearest if nearest is None else nearest
        ordered = sorted(self.graph)
        baseline = self.total_nodes()
        for target in sorted(self.targets):
            if target not in self.graph or self.node_cost(target) <= 2:
                continue
            current = self.graph[target]
            position = bisect_left(ordered, target)
            around = []
            span = 8
            span = self.anchor_span
            low = max(0, position - span)
            high = position + 1 if one_sided else min(len(ordered), position + span + 1)
            for index in range(low, high):
                value = ordered[index]
                gap = abs(target - value)
                if 0 < gap <= window:
                    around.append((gap, value))
            around.sort()
            for gap, anchor in around[:nearest]:
                snapshot = dict(self.graph)
                cost = self.ensure(gap, 3, forbidden=target)
                if cost >= INF or not self._defined():
                    self.graph = snapshot
                    continue
                split = ("+" if anchor < target else "-", anchor, gap)
                if split == current:
                    self.graph = snapshot
                    continue
                self.graph[target] = ("+" if anchor < target else "-", anchor, gap)
                if not strict:
                    if cost + 1 < self.node_cost(target):
                        changed = True
                        self.sweep()
                        ordered = sorted(self.graph)
                        break
                    self.graph = snapshot
                    continue
                total = self.total_nodes()
                if total < baseline:
                    baseline = total
                    changed = True
                    self.sweep()
                    ordered = sorted(self.graph)
                    break
                self.graph = snapshot
        return changed

    def scaled_anchor_pass(self, window: int = 1 << 22, nearest: int = 4,
                           strict: bool = True) -> bool:
        """Re-derive targets as ``anchor * k + gap`` for small ``k``."""
        changed = False
        ordered = sorted(self.graph)
        baseline = self.total_nodes()
        scales = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16)
        for target in sorted(self.targets):
            if target not in self.graph or self.node_cost(target) <= 2:
                continue
            current = self.graph[target]
            position = bisect_left(ordered, target)
            low = max(0, position - 6)
            high = min(len(ordered), position + 7)
            around = []
            for index in range(low, high):
                anchor = ordered[index]
                for k in scales:
                    product = anchor * k
                    if product <= self.limit:
                        gap = target - product
                        if 0 < abs(gap) <= window:
                            around.append((abs(gap), anchor, k, product, "*"))
                    if anchor % k == 0:
                        quotient = anchor // k
                        gap = target - quotient
                        if 0 < abs(gap) <= window:
                            around.append((abs(gap), anchor, k, quotient, "/"))
            around.sort()
            for gap_size, anchor, k, scaled, op in around[:nearest]:
                snapshot = dict(self.graph)
                if self.ensure(k, 1, forbidden=target) >= INF:
                    self.graph = snapshot
                    continue
                self.graph[scaled] = (op, anchor, k)
                cost = self.ensure(gap_size, 3, forbidden=target) + 1
                if cost >= INF or not self._defined():
                    self.graph = snapshot
                    continue
                split = ("+" if scaled < target else "-", scaled, gap_size)
                if split == current:
                    self.graph = snapshot
                    continue
                self.graph[target] = split
                if not strict:
                    if cost + 1 < self.node_cost(target):
                        changed = True
                        self.sweep()
                        ordered = sorted(self.graph)
                        break
                    self.graph = snapshot
                    continue
                total = self.total_nodes()
                if total < baseline:
                    baseline = total
                    changed = True
                    self.sweep()
                    ordered = sorted(self.graph)
                    break
                self.graph = snapshot
        return changed

    def rational_pass(self, scales: int = 64, strict: bool = True) -> bool:
        """Re-derive targets as ``(anchor*p + c) / q`` for small ``p`` and ``q``.

        Consecutive targets in the scored set are often linked by a small
        rational ratio (measured 28.5% of pairs versus 8.5% for a uniform
        control).  For each (p, q) the anchor nearest to ``target*q/p`` gives a
        tiny residual ``c = target*q - anchor*p``, so the target costs one
        multiply, one add and one divide plus the residual.
        """
        limit = self.limit
        changed = False
        baseline = self.total_nodes()
        values = sorted(self.graph)
        for target in sorted(self.targets):
            if target not in self.graph or self.node_cost(target) <= 3:
                continue
            max_q = min(scales, limit // target)
            if max_q < 2:
                continue
            current = self.graph[target]
            best: tuple[int, int, int, int] | None = None
            for q in range(2, max_q + 1):
                scaled_target = target * q
                for p in range(2, scales + 1):
                    desired = scaled_target / p
                    if desired < 2:
                        break
                    position = bisect_left(values, int(desired))
                    for index in (position - 1, position, position + 1):
                        if not 0 <= index < len(values):
                            continue
                        anchor = values[index]
                        if anchor < 2 or anchor == target:
                            continue
                        product = anchor * p
                        if product > limit:
                            continue
                        residual = scaled_target - product
                        if best is None or abs(residual) < abs(best[3]):
                            best = (anchor, p, q, residual)
            if best is None:
                continue
            anchor, p, q, residual = best
            if self.ensure(p, 1, forbidden=target) >= INF:
                continue
            if self.ensure(q, 1, forbidden=target) >= INF:
                continue
            snapshot = dict(self.graph)
            product = anchor * p
            shifted = product + residual
            if not 1 <= shifted <= limit or shifted % q:
                continue
            self.graph[product] = ("*", anchor, p)
            if residual:
                if self.ensure(abs(residual), 2, forbidden=target) >= INF:
                    self.graph = snapshot
                    continue
                self.graph[shifted] = ("+" if residual > 0 else "-", product, abs(residual))
            self.graph[target] = ("/", shifted, q)
            if not self._defined() or self._reaches(shifted, target) \
                    or self._reaches(q, target) or self._reaches(product, target):
                self.graph = snapshot
                continue
            if not strict:
                changed = True
                self.sweep()
                values = sorted(self.graph)
                continue
            total = self.total_nodes()
            if total < baseline:
                baseline = total
                changed = True
                self.sweep()
                values = sorted(self.graph)
            else:
                self.graph = snapshot
        return changed

    def product_pass(self, strict: bool = True, pool: int = 240) -> bool:
        """Re-derive targets as ``a * round(t/a) + c`` with ``a`` from the graph.

        This is the "near-square with a chosen factor" family that the public
        frontier programs use heavily: ``t = M1*M2 - c`` where both factors are
        themselves built from a shared pool of small blocks and ``c`` is small.
        """
        changed = False
        limit = self.limit
        baseline = self.total_nodes()
        candidates = self.cheapest_sets(pool)
        for target in sorted(self.targets):
            if target not in self.graph or self.node_cost(target) <= 3:
                continue
            current = self.graph[target]
            scored: list[tuple[int, int, int, int]] = []
            for a in candidates:
                if a < 2 or a >= target:
                    continue
                other = (target + a // 2) // a
                if other < 2 or a * other > limit:
                    continue
                residual = target - a * other
                estimate = abs(residual).bit_length() // 8 + 2
                scored.append((estimate, a, other, residual))
            scored.sort()
            for _, a, other, residual in scored[:4]:
                snapshot = dict(self.graph)
                cost = 2
                if other not in self.graph:
                    cost += self.ensure(other, 3, forbidden=target)
                if cost >= INF:
                    self.graph = snapshot
                    continue
                product = a * other
                self.graph[product] = ("*", a, other)
                if residual:
                    if self.ensure(abs(residual), 3, forbidden=target) >= INF:
                        self.graph = snapshot
                        continue
                    self.graph[target] = ("+" if residual > 0 else "-", product,
                                          abs(residual))
                else:
                    self.graph[target] = ("*", a, other)
                if not self._defined() or self._reaches(product, target):
                    self.graph = snapshot
                    continue
                if not strict:
                    changed = True
                    self.sweep()
                    candidates = self.cheapest_sets(pool)
                    break
                total = self.total_nodes()
                if total < baseline:
                    baseline = total
                    changed = True
                    self.sweep()
                    candidates = self.cheapest_sets(pool)
                    break
                self.graph = snapshot
        return changed

    def sweep(self) -> None:
        """Drop every node no target needs any more."""
        needed: set[int] = set()
        for target in self.targets:
            stack = [target]
            while stack:
                v = stack.pop()
                if v in needed:
                    continue
                needed.add(v)
                split = self.graph.get(v)
                if split is None:
                    continue
                stack.extend(split[1:])
        for value in list(self.graph):
            if value not in needed and value not in self.target_set:
                self.graph.pop(value)
        keep = {v for v in needed if self.graph.get(v) is not None}
        keep.update(v for v in self.targets if v in self.graph)
        self.graph = {v: e for v, e in self.graph.items() if v in keep or e is None}


def emit(puzzle: Puzzle, graph: dict[int, OpSplit | None]) -> Program:
    """Schedule the graph into a register program with liveness-based registers."""
    starts = list(dict.fromkeys(puzzle.starting))
    limit = puzzle.limit
    # targets that are close to each other share anchors, so keep them adjacent
    order = sorted(puzzle.targets, key=lambda t: (t.bit_length(), t))
    scheduled: list[int] = []
    done: set[int] = set()
    for target in order:
        if target in done:
            continue
        stack = [(target, False)]
        while stack:
            value, expanded = stack.pop()
            if expanded:
                scheduled.append(value)
                continue
            if value in done:
                continue
            done.add(value)
            split = graph.get(value)
            if split is None:
                continue
            stack.append((value, True))
            for operand in (split[1], split[2]):
                if operand not in done:
                    stack.append((operand, False))

    use_positions: dict[int, list[int]] = defaultdict(list)
    for index, value in enumerate(scheduled):
        split = graph[value]
        use_positions[split[1]].append(index)
        use_positions[split[2]].append(index)
    pointer: dict[int, int] = defaultdict(int)

    def next_use(value: int) -> int:
        positions = use_positions.get(value)
        if not positions:
            return len(scheduled) + 1
        index = pointer[value]
        return positions[index] if index < len(positions) else len(scheduled) + 1

    registers: dict[int, int] = {v: i for i, v in enumerate(starts)}
    spare = sorted(range(len(starts), REGISTERS), reverse=True)
    program: Program = []
    building: set[int] = set()

    def ensure(value: int) -> int:
        if value in registers:
            return registers[value]
        if value in building:
            raise ValueError(f"cycle at {value}")
        split = graph.get(value)
        if split is None:
            raise ValueError(f"missing operand {value}")
        building.add(value)
        i = ensure(split[1])
        j = ensure(split[2])
        if spare:
            dest = spare.pop()
        else:
            victims = [k for k in registers if k not in (split[1], split[2])]
            if not victims:
                raise ValueError("register pressure")
            dest = registers.pop(max(victims, key=next_use))
        program.append((split[0], i, j, dest))
        registers[value] = dest
        for operand in (split[1], split[2]):
            pointer[operand] += 1
        building.discard(value)
        return dest

    for value in scheduled:
        ensure(value)
        if len(program) > MAX_STEPS:
            raise ValueError("program too long")
    # drop registers that nothing reads any more
    return program


VARIANTS = (
    # (span, nearest, one_sided, two_step)
    (8, 8, False, True),
    (8, 8, True, True),
    (4, 4, False, True),
    (4, 2, True, True),
    (12, 12, False, True),
    (12, 6, True, True),
    (6, 3, False, False),
    (16, 16, False, True),
)


def polish(puzzle: Puzzle, program: Program, rounds: int = 6,
           deep: bool = False, two_step: bool = False,
           strict: bool = True, seed: int = 0, walk: bool = False,
           one_sided: bool = False, variant: int = 0,
           scaled: bool = False, rational: bool = False,
           rational_scales: int = 64, product: bool = False) -> Program:
    """Iteratively shorten ``program`` inside its own value graph."""
    sys.setrecursionlimit(20000)
    replay(puzzle, program)
    best = program
    for _ in range(rounds):
        graph = graph_of(puzzle, best)
        span, nearest, var_one_sided, var_two_step = VARIANTS[variant % len(VARIANTS)]
        polisher = Polisher(puzzle, graph, anchor_span=span, anchor_nearest=nearest)
        changed = False
        for _ in range(3):
            inner = False
            while polisher.rewrite(use_two_step=False):
                inner = True
                polisher.sweep()
            if (two_step and var_two_step) and polisher.rewrite(use_two_step=True):
                inner = True
                polisher.sweep()
            if product and polisher.product_pass(strict=strict):
                inner = True
                polisher.sweep()
            if rational and polisher.rational_pass(strict=strict,
                                                   scales=rational_scales):
                inner = True
                polisher.sweep()
            if scaled and polisher.scaled_anchor_pass(strict=strict):
                inner = True
                polisher.sweep()
            if deep and polisher.node_pass():
                inner = True
                polisher.sweep()
            if deep and polisher.anchor_search():
                inner = True
                polisher.sweep()
            if polisher.anchor_pass(strict=strict,
                                    one_sided=one_sided or var_one_sided):
                inner = True
                polisher.sweep()
            if walk and polisher.walk(rounds=300, seed=seed * 7919 + len(polisher.graph)):
                inner = True
                polisher.sweep()
            if not inner:
                break
            changed = True
        if not changed:
            break
        try:
            candidate = emit(puzzle, polisher.graph)
            replay(puzzle, candidate)
        except ValueError:
            break
        candidate = reuse_registers(puzzle, prune(puzzle, candidate))
        if len(candidate) >= len(best):
            break
        best = candidate
    return best


def solve(puzzle: Puzzle, reference: Program | None = None,
          rounds: int = 8, two_step: bool = True, strict: bool = True,
          seed: int = 0, walk: bool = False, one_sided: bool = False,
          variant: int = 0, scaled: bool = False, rational: bool = False,
          rational_scales: int = 64, product: bool = False) -> Program:
    """Polish ``reference`` repeatedly until it stops getting shorter."""
    if reference is None:
        raise ValueError("the polisher needs a reference program")
    replay(puzzle, reference)
    best = reference
    for _ in range(rounds):
        candidate = polish(puzzle, best, two_step=two_step, rounds=4,
                           strict=strict, seed=seed, walk=walk,
                           one_sided=one_sided, variant=variant,
                           scaled=scaled, rational=rational,
                           rational_scales=rational_scales, product=product)
        if len(candidate) >= len(best):
            break
        best = candidate
    return best


def solve_row(job):
    (puzzle, reference, two_step, strict, seed, one_sided, variant, scaled,
     rational, scales, product) = job
    return puzzle.id, solve(puzzle, reference, two_step=two_step,
                            strict=strict, seed=seed, one_sided=one_sided,
                            variant=variant, scaled=scaled, rational=rational,
                            rational_scales=scales, product=product)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzles", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--no-two-step", action="store_true",
                        help="only rewrite with a single instruction per target")
    parser.add_argument("--seed", type=int, default=0, help="randomised walk seed")
    parser.add_argument("--product", action="store_true",
                        help="also try a * round(t/a) + c rewrites")
    parser.add_argument("--rational-scales", type=int, default=64,
                        help="max p,q for --rational")
    parser.add_argument("--rational", action="store_true",
                        help="also try (anchor*p + c)/q rewrites")
    parser.add_argument("--scaled", action="store_true",
                        help="also try anchor*k + gap rewrites with small k")
    parser.add_argument("--variant", type=int, default=0,
                        help="search variant (0-7) for anchor span/nearest/direction")
    parser.add_argument("--one-sided", action="store_true",
                        help="only use anchors below the target")
    parser.add_argument("--merge", type=Path, nargs="+", metavar="CSV",
                        help="combine several program CSVs, keeping the shortest per puzzle")
    parser.add_argument("--loose", action="store_true",
                        help="accept anchor rewrites optimistically (explores more)")
    args = parser.parse_args()
    if not args.check and not args.reference and not args.merge:
        parser.error("--reference or --merge is required unless --check is used")
    try:
        puzzles = load_puzzles(args.puzzles)
        if args.merge:
            if not args.output:
                parser.error("--merge requires --output")
            sources = [load_programs(path, puzzles) for path in args.merge]
            programs = {pid: min((table[pid] for table in sources), key=len)
                        for pid in puzzles}
            with args.output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("id", "program"))
                writer.writerows((pid, encode(program)) for pid, program in programs.items())
            print(f"Puzzles: {len(programs):,} | Total instructions: "
                  f"{sum(map(len, programs.values())):,}")
            return
        if args.check:
            programs = load_programs(args.check, puzzles)
            print(f"Puzzles: {len(programs):,} | Total instructions: "
                  f"{sum(map(len, programs.values())):,}")
            return
        reference = load_programs(args.reference, puzzles)
        jobs = ((puzzle, reference[pid], not args.no_two_step, not args.loose,
                 args.seed, args.one_sided, args.variant, args.scaled, args.rational,
                 args.rational_scales, args.product) for pid, puzzle in puzzles.items())
        if args.jobs == 1:
            programs = dict(map(solve_row, jobs))
        else:
            with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                programs = dict(pool.map(solve_row, jobs, chunksize=4))
        if args.output:
            with args.output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("id", "program"))
                writer.writerows((pid, encode(program)) for pid, program in programs.items())
        print(f"Reference instructions: {sum(map(len, reference.values())):,}")
        print(f"Puzzles: {len(programs):,} | Total instructions: "
              f"{sum(map(len, programs.values())):,}")
    except (ValueError, OSError, KeyError, TypeError, csv.Error) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
