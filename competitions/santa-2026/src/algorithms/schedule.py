"""Register-aware compilation and scheduling for the V9 pipeline.

Two deterministic schedulers remain distinct because the frozen version treats
them as different stages:

* ``compile_graph`` compiles a freshly constructed value DAG under eight
  topological/DFS orders (Stage 1, seed 919).  The returned node count is the
  *last examined order length*, exactly as recorded by the frozen research
  runner, not always the length of the returned program;
* ``schedule`` extracts candidate orders from a first-occurrence DAG (root
  order variants, dependency-overlap clustering, list scheduling and bounded
  root-permutation search), ranks them by register pressure (overflow, peak,
  area), then emits and replays up to twelve orders with six eviction/evaluation
  strategies (Stage 2, seed 202609).

Candidate order, random-number consumption and tie handling are part of the
frozen search policy.  Neither routine reads historical programs or answers.
"""

import bisect
import json
import random
from collections import Counter, defaultdict

from .common import arithmetic, replay


def compile_graph(row, graph, tries=8, seed=919):
    """Compile a value DAG under ``tries`` deterministic orders, keep the shortest."""
    starting = json.loads(row['starting_values'])
    targets = list(dict.fromkeys(json.loads(row['targets'])))
    limit = int(row['value_limit'])
    registers = int(row['registers'])
    start = set(starting)
    closure = {v: set() for v in starting}

    def close(v, stack=frozenset()):
        if v in closure:
            return closure[v]
        if v in stack:
            raise ValueError('cycle')
        op, a, b = graph[v]
        if not 1 <= v <= limit or arithmetic(op, a, b) != v:
            raise ValueError('invalid graph')
        closure[v] = close(a, stack | {v}) | close(b, stack | {v}) | {v}
        return closure[v]

    for v in targets:
        close(v)
    rng = random.Random(seed)
    best = None
    for turn in range(tries):
        roots = targets.copy()
        if turn % 4 == 1:
            roots.reverse()
        elif turn % 4 == 2:
            roots.sort(key=lambda v: len(closure[v]), reverse=turn % 8 == 6)
        elif turn % 4 == 3:
            rng.shuffle(roots)
        done = set(starting)
        order = []

        def visit(v):
            if v in done:
                return
            _, a, b = graph[v]
            if (len(closure[a]) < len(closure[b])) == (turn % 2 == 0):
                a, b = b, a
            visit(a)
            visit(b)
            done.add(v)
            order.append(v)

        for t in roots:
            visit(t)
        future = defaultdict(list)
        for k, v in enumerate(order):
            for x in set(graph[v][1:]):
                future[x].append(k)
        live = {x: i for i, x in enumerate(starting)}
        program = []
        index = 0

        def ensure(v, protect):
            if v in live:
                return
            op, a, b = graph[v]
            ensure(a, protect)
            ensure(b, protect | {a})
            i, j = live[a], live[b]
            free = set(range(registers)) - set(live.values())
            if free:
                d = min(free)
            else:
                options = [x for x in live if x not in start and x not in protect]
                if not options:
                    raise ValueError('register pressure')

                def rank(x):
                    nxt = next((k for k in future[x] if k > index), len(order) + 10000)
                    return (nxt - index) / (1 + len(closure[x]) if turn % 2 else 1), nxt, -len(closure[x]), x

                x = max(options, key=rank)
                d = live.pop(x)
            program.append([op, i, j, d])
            live[v] = d

        try:
            for index, v in enumerate(order):
                ensure(v, set())
                for x in list(live):
                    if x not in start and not any(k > index for k in future[x]):
                        live.pop(x)
            replay(row, program)
        except (ValueError, KeyError, RecursionError):
            continue
        if best is None or len(program) < len(best):
            best = program
        if best is not None and len(best) == len(order):
            break
    if best is None:
        raise ValueError('no valid schedule')
    return best, len(order)


def schedule(row, graph, best, tries=32, top=12, modes=6, seed=202609):
    """Stage 2: search alternative register schedules for a program's DAG.

    Returns ``(program, info)`` where ``best`` is only replaced by a strictly
    shorter replayed program.  ``info`` carries the DAG node count and the
    number of emitted candidates, which are deterministic per puzzle.
    """
    starting = list(json.loads(row['starting_values']))
    start = set(starting)
    targets = list(dict.fromkeys(json.loads(row['targets'])))
    registers = int(row['registers'])
    closure = {v: frozenset() for v in start}
    depth = {v: 0 for v in start}
    topological = []

    def visit(v):
        if v not in closure:
            _, a, b = graph[v]
            visit(a)
            visit(b)
            closure[v] = closure[a] | closure[b] | {v}
            depth[v] = 1 + max(depth[a], depth[b])
            topological.append(v)

    for v in targets:
        visit(v)
    graph = {v: graph[v] for v in topological}
    nodes = len(graph)
    if len(best) == nodes:
        return best, dict(nodes=nodes, attempts=0)
    users = defaultdict(list)
    deps = {v: set(graph[v][1:]) for v in graph}
    for v in graph:
        for x in deps[v]:
            users[x].append(v)
    rng = random.Random(seed)
    orders = {}

    def dfs(roots, reverse=False):
        seen = set(start)
        order = []

        def walk(v):
            if v in seen:
                return
            a, b = graph[v][1:]
            a, b = sorted((a, b), key=lambda x: (len(closure[x]), x), reverse=reverse)
            walk(a)
            walk(b)
            seen.add(v)
            order.append(v)

        for v in roots:
            walk(v)
        return tuple(order)

    def cluster(seed_value, metric):
        remaining = set(targets)
        roots = []
        last = seed_value
        made = set()
        while remaining:
            if last not in remaining:
                if metric == 0:
                    last = max(remaining, key=lambda t: (len(closure[t] & made), -len(closure[t] - made), -t))
                elif metric == 1:
                    last = max(remaining, key=lambda t: (len(closure[t] & closure[roots[-1]]), -len(closure[t] - made), -t))
                else:
                    last = max(remaining, key=lambda t: (len(closure[t] & made) / (1 + len(closure[t] - made)), -t))
            roots.append(last)
            remaining.remove(last)
            made.update(closure[last])
        return roots

    def pressure(order):
        last = {}
        for i, v in enumerate(order):
            for x in deps[v]:
                last[x] = i
        live = set(start)
        excess = area = peak = 0
        for i, v in enumerate(order):
            for x in deps[v]:
                if x not in start and last[x] == i:
                    live.discard(x)
            if last.get(v, -1) > i:
                live.add(v)
            k = len(live)
            excess += max(0, k - registers)
            area += k
            peak = max(peak, k)
        return excess, peak, area

    def add(order):
        if order not in orders:
            orders[order] = pressure(order)

    root_variants = (
        targets, targets[::-1], sorted(targets), sorted(targets, reverse=True),
        sorted(targets, key=lambda t: (len(closure[t]), t)),
        sorted(targets, key=lambda t: (-len(closure[t]), t)),
    )
    for roots in root_variants:
        for reverse in (False, True):
            add(dfs(roots, reverse))
    for seed_value in (min(targets), max(targets), max(targets, key=lambda t: len(closure[t]))):
        for metric in range(3):
            roots = cluster(seed_value, metric)
            add(dfs(roots))
            add(dfs(roots, True))

    def list_order(mode):
        pending = {v: len(deps[v] - start) for v in graph}
        ready = {v for v, n in pending.items() if not n}
        remaining = {v: len(users[v]) for v in set(graph) | start}
        order = []
        rank = {v: rng.random() for v in graph}
        last = set(start)
        while ready:
            def priority(v):
                release = sum(x not in start and remaining[x] == 1 for x in deps[v])
                new = int(remaining[v] > 0)
                unlock = sum(pending[x] == 1 for x in users[v])
                reuse = len(deps[v] & last)
                if mode % 4 == 0:
                    return release - new, release, unlock, reuse, -len(closure[v]), rank[v]
                if mode % 4 == 1:
                    return release - new, unlock, reuse, depth[v], rank[v]
                if mode % 4 == 2:
                    return release - new, reuse, release, -len(closure[v]), rank[v]
                return release - new, release, rank[v], unlock
            v = max(ready, key=priority)
            ready.remove(v)
            order.append(v)
            last = deps[v] | {v}
            for x in deps[v]:
                remaining[x] -= 1
            for x in users[v]:
                pending[x] -= 1
                if pending[x] == 0:
                    ready.add(x)
        return tuple(order)

    for i in range(8):
        add(list_order(i))
    # Bounded root-permutation search ranked by the register-pressure proxy; it
    # does not spend a replay on every order.
    roots = targets[:]
    rng.shuffle(roots)
    current = pressure(dfs(roots))
    best_roots = roots[:]
    for k in range(tries):
        trial = best_roots[:]
        i, j = rng.sample(range(len(targets)), 2) if len(targets) > 1 else (0, 0)
        trial[i], trial[j] = trial[j], trial[i]
        order = dfs(trial, k % 2 == 0)
        p = pressure(order)
        add(order)
        if p <= current:
            current = p
            best_roots = trial

    def emit(order, mode):
        future = defaultdict(list)
        for i, v in enumerate(order):
            for x in deps[v]:
                future[x].append(i)
        live = {v: i for i, v in enumerate(starting)}
        program = []
        index = 0

        def nxt(x):
            f = future[x]
            j = bisect.bisect_right(f, index)
            return f[j] if j < len(f) else nodes + 1000

        def cost(x):
            return len(closure[x] - live.keys()) + 1

        def ensure(v, protect):
            if v in live:
                return
            op, a, b = graph[v]
            if mode % 2 and len(closure[b] - live.keys()) > len(closure[a] - live.keys()):
                ensure(b, protect)
                ensure(a, protect | {b})
            else:
                ensure(a, protect)
                ensure(b, protect | {a})
            ai, bi = live[a], live[b]
            free = set(range(registers)) - set(live.values())
            dead = [x for x in (a, b) if x not in start and x not in protect and nxt(x) > nodes]
            if dead:
                d = live.pop(dead[0])
            elif free:
                d = min(free)
            else:
                options = [x for x in live if x not in start and x not in protect]
                if not options:
                    raise ValueError('register pressure')
                if mode // 2 == 0:
                    x = max(options, key=lambda x: (nxt(x), -cost(x), x))
                elif mode // 2 == 1:
                    x = max(options, key=lambda x: ((nxt(x) - index) / cost(x), nxt(x), x))
                else:
                    x = max(options, key=lambda x: ((nxt(x) - index) / (cost(x) ** 0.5), nxt(x), x))
                d = live.pop(x)
            program.append([op, ai, bi, d])
            live[v] = d

        for index, v in enumerate(order):
            ensure(v, set())
            for x in list(live):
                if x not in start and nxt(x) > nodes:
                    live.pop(x)
            if len(program) >= len(best):
                return None
        replay(row, program)
        return program

    attempts = 0
    for order, _ in sorted(orders.items(), key=lambda z: z[1])[:top]:
        for mode in range(modes):
            attempts += 1
            try:
                program = emit(order, mode)
            except (ValueError, KeyError, RecursionError):
                continue
            if program is not None and len(program) < len(best):
                best = program
            if len(best) == nodes:
                return best, dict(nodes=nodes, attempts=attempts)
    return best, dict(nodes=nodes, attempts=attempts)
