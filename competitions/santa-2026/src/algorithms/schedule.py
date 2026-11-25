"""Register scheduling and legal compilation.

Three schedulers remain distinct because they make different ordering,
pressure and rematerialisation decisions:

* ``schedule_v7``: shared-closure root clustering with last-use overwrite;
* ``compile_graph``: eight topological/DFS orders for a graph candidate;
* ``schedule_v8``: pressure-ranked root orders with up to 32 candidates.
"""

import json
import random
from collections import Counter, defaultdict

from .common import replay
from .graph import closures, extract


def schedule_v7(row, program):
    """Cluster roots by shared dependencies and try last-use register overwrite."""
    s = json.loads(row['starting_values'])
    start = set(s)
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    n = int(row['registers'])
    g = extract(row, program)
    closure = {v: frozenset() for v in s}
    depth = {v: 0 for v in s}
    for v, (o, a, b) in g.items():
        closure[v] = closure[a] | closure[b] | {v}
        depth[v] = 1 + max(depth[a], depth[b])
    nodes = set().union(*(closure[t] for t in ts))
    if len(nodes) >= len(program):
        return program

    def cluster(reverse=False):
        todo = set(ts)
        out = []
        prev = None
        used = set()
        while todo:
            if prev is None:
                t = max(todo, key=lambda x: (len(closure[x]), x)) if reverse else min(todo, key=lambda x: (len(closure[x]), x))
            else:
                t = max(todo, key=lambda x: (len(closure[x] & closure[prev]), len(closure[x] & used),
                                             -len(closure[x] - used), -x))
            todo.remove(t)
            out.append(t)
            used |= closure[t]
            prev = t
        return out

    best = program
    for roots in [ts, ts[::-1], sorted(ts), sorted(ts, reverse=True), cluster(), cluster(True)]:
        for deep_first in (False, True):
            order = []
            seen = set(s)

            def visit(v):
                if v in seen:
                    return
                _, a, b = g[v]
                if deep_first and (depth[b], len(closure[b])) > (depth[a], len(closure[a])):
                    a, b = b, a
                visit(a)
                visit(b)
                seen.add(v)
                order.append(v)

            for t in roots:
                visit(t)
            uses = defaultdict(list)
            for i, v in enumerate(order):
                _, a, b = g[v]
                uses[a].append(i)
                uses[b].append(i)
            for policy in ('distance', 'cost'):
                if len(order) >= len(best):
                    return best
                live = {v: i for i, v in enumerate(s)}
                out = []
                at = 0
                ptr = defaultdict(int)

                def nextuse(v):
                    return uses[v][ptr[v]] if ptr[v] < len(uses[v]) else 10 ** 9

                def ensure(v, protect):
                    if v in live:
                        return
                    o, a, b = g[v]
                    if deep_first and depth[b] > depth[a]:
                        ensure(b, protect)
                        ensure(a, protect | {b})
                    else:
                        ensure(a, protect)
                        ensure(b, protect | {a})
                    ai, bi = live[a], live[b]
                    disposable = [k for k in {a, b} if k not in start and k not in protect
                                  and v == order[at] and ptr[k] + (1 if a != b else 2) == len(uses[k])]
                    if disposable:
                        d = live.pop(min(disposable))
                    else:
                        free = set(range(n)) - set(live.values())
                        if free:
                            d = min(free)
                        else:
                            ev = [k for k in live if k not in start and k not in protect]
                            if not ev:
                                raise ValueError('register pressure')
                            if policy == 'distance':
                                k = max(ev, key=lambda k: (nextuse(k), -len(closure[k]), k))
                            else:
                                k = max(ev, key=lambda k: ((nextuse(k) - at) / (1 + len(closure[k])), nextuse(k), k))
                            d = live.pop(k)
                    out.append([o, ai, bi, d])
                    live[v] = d
                    if len(out) >= len(best):
                        raise ValueError('not shorter')

                try:
                    for at, v in enumerate(order):
                        _, a, b = g[v]
                        ensure(v, set())
                        ptr[a] += 1
                        ptr[b] += 1
                        for k in list(live):
                            if k not in start and nextuse(k) == 10 ** 9:
                                live.pop(k)
                    replay(row, out)
                    best = out
                except (ValueError, RecursionError):
                    pass
    return best


def compile_graph(row, g, best):
    """Compile a graph candidate under eight deterministic orders, keep shortest."""
    s = json.loads(row['starting_values'])
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    n = int(row['registers'])
    start = set(s)
    cl, active = closures(g, s, ts)
    if len(active) >= len(best):
        return best
    children = defaultdict(list)
    deps = {}
    original = Counter()
    rng = random.Random(808)
    for v in active:
        _, a, b = g[v]
        deps[v] = len({a, b} - start)
        for x in {a, b}:
            children[x].append(v)
            original[x] += 1
    for mode in range(8):
        order = []
        if mode >= 4:
            roots = ts.copy()
            if mode == 5:
                roots.reverse()
            elif mode == 6:
                roots.sort(key=lambda t: (len(cl[t]), t))
            elif mode == 7:
                roots.sort(key=lambda t: (-len(cl[t]), t))
            seen = set(start)

            def visit(v):
                if v in seen:
                    return
                _, a, b = g[v]
                if mode % 2 and len(cl[b]) > len(cl[a]):
                    a, b = b, a
                visit(a)
                visit(b)
                seen.add(v)
                order.append(v)

            for t in roots:
                visit(t)
        else:
            remaining = original.copy()
            indeg = deps.copy()
            ready = {v for v, d in indeg.items() if d == 0}
            priority = {v: rng.random() for v in sorted(active)}
            while ready:
                def score(v):
                    _, a, b = g[v]
                    release = sum(x not in start and remaining[x] == 1 for x in {a, b})
                    birth = bool(remaining[v])
                    reuse = sum(x not in start for x in {a, b})
                    return (release - birth, release, (-len(cl[v]), len(cl[v]), priority[v], -remaining[v])[mode], reuse, -v)

                v = max(ready, key=score)
                ready.remove(v)
                order.append(v)
                _, a, b = g[v]
                for x in {a, b}:
                    remaining[x] -= 1
                for w in children[v]:
                    indeg[w] -= 1
                    if indeg[w] == 0:
                        ready.add(w)
        if len(order) != len(active):
            raise ValueError('bad order')
        uses = defaultdict(list)
        ptr = defaultdict(int)
        for j, v in enumerate(order):
            _, a, b = g[v]
            for x in {a, b}:
                uses[x].append(j)
        live = {v: i for i, v in enumerate(s)}
        out = []

        def nextuse(v):
            return uses[v][ptr[v]] if ptr[v] < len(uses[v]) else 10 ** 9

        def ensure(v, protect):
            if v in live:
                return
            op, a, b = g[v]
            if len(cl[b]) > len(cl[a]):
                ensure(b, protect)
                ensure(a, protect | {b})
            else:
                ensure(a, protect)
                ensure(b, protect | {a})
            ai, bi = live[a], live[b]
            disposable = [x for x in {a, b} if x not in start and x not in protect
                          and nextuse(x) == at and ptr[x] + 1 == len(uses[x]) and order[at] == v]
            if disposable:
                d = live.pop(min(disposable))
            else:
                free = set(range(n)) - set(live.values())
                if free:
                    d = min(free)
                else:
                    ev = [x for x in live if x not in start and x not in protect]
                    if not ev:
                        raise ValueError('register pressure')
                    d = live.pop(max(ev, key=lambda x: (nextuse(x), -len(cl[x]), x)))
            out.append([op, ai, bi, d])
            live[v] = d
            if len(out) >= len(best):
                raise ValueError('not shorter')

        try:
            for at, v in enumerate(order):
                ensure(v, set())
                _, a, b = g[v]
                for x in {a, b}:
                    ptr[x] += 1
                for x in list(live):
                    if x not in start and nextuse(x) == 10 ** 9:
                        live.pop(x)
            replay(row, out)
            best = out
            if len(best) == len(active):
                break
        except (ValueError, RecursionError, AssertionError):
            pass
    return best


def schedule_v8(row, program, tries=32):
    """Liveness-ranked register scheduling with real program length selection."""
    s = json.loads(row['starting_values'])
    start = set(s)
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    n = int(row['registers'])
    g = extract(row, program)
    cl, active = closures(g, s, ts)
    if len(active) >= len(program):
        return program, 0, len(program) - len(active)
    rng = random.Random(833)
    best = program
    attempts = 0
    orders = {}

    def dfs(roots, deep):
        seen = set(start)
        order = []

        def visit(v):
            if v in seen:
                return
            _, a, b = g[v]
            if deep and len(cl[a]) < len(cl[b]):
                a, b = b, a
            visit(a)
            visit(b)
            seen.add(v)
            order.append(v)

        for t in roots:
            visit(t)
        return order

    def pressure(order):
        remaining = Counter(x for v in order for x in set(g[v][1:]))
        live = 0
        peak = 0
        overflow = 0
        area = 0
        for v in order:
            for x in set(g[v][1:]):
                remaining[x] -= 1
                if remaining[x] == 0 and x not in start:
                    live -= 1
            if remaining[v]:
                live += 1
            peak = max(peak, live)
            overflow += max(0, live + len(start) - n)
            area += live
        return overflow, peak, area

    roots = ts[:]
    for k in range(tries):
        if k % 4 == 0:
            roots = ts[:]
            rng.shuffle(roots)
        elif k % 4 == 1:
            roots = sorted(ts, key=lambda t: (len(cl[t]), t), reverse=bool(k % 8))
        elif k % 4 == 2:
            roots = []
            todo = set(ts)
            used = set()
            prev = set()
            while todo:
                t = max(todo, key=lambda x: (len(cl[x] & prev) + .5 * len(cl[x] & used) - .25 * len(cl[x] - used), -x))
                todo.remove(t)
                roots.append(t)
                prev = cl[t]
                used |= prev
        else:
            roots = roots[:]
            if len(roots) > 1:
                i, j = rng.sample(range(len(roots)), 2)
                roots[i], roots[j] = roots[j], roots[i]
        order = dfs(roots, bool(k % 2))
        orders[tuple(order)] = pressure(order)
    for order in sorted(orders, key=lambda o: orders[o])[:8]:
        if len(best) == len(active):
            break
        attempts += 1
        uses = defaultdict(list)
        ptr = defaultdict(int)
        for j, v in enumerate(order):
            for x in set(g[v][1:]):
                uses[x].append(j)
        live = {v: i for i, v in enumerate(s)}
        out = []

        def nextuse(v):
            return uses[v][ptr[v]] if ptr[v] < len(uses[v]) else 10 ** 9

        def ensure(v, protect):
            if v in live:
                return
            op, a, b = g[v]
            if (a not in live, len(cl[a])) < (b not in live, len(cl[b])):
                ensure(b, protect)
                ensure(a, protect | {b})
            else:
                ensure(a, protect)
                ensure(b, protect | {a})
            ai, bi = live[a], live[b]
            dead = [x for x in {a, b} if x not in start and x not in protect
                    and nextuse(x) == at and ptr[x] + 1 == len(uses[x]) and order[at] == v]
            if dead:
                d = live.pop(min(dead))
            else:
                free = set(range(n)) - set(live.values())
                if free:
                    d = min(free)
                else:
                    candidates = [x for x in live if x not in start and x not in protect]
                    if not candidates:
                        raise ValueError('register pressure')
                    x = max(candidates, key=lambda x: (nextuse(x) == 10 ** 9,
                                                       (nextuse(x) - at) / (1 + len(cl[x] - set(live))),
                                                       nextuse(x), x))
                    d = live.pop(x)
            out.append([op, ai, bi, d])
            live[v] = d
            if len(out) >= len(best):
                raise ValueError('not shorter')

        try:
            for at, v in enumerate(order):
                ensure(v, set())
                for x in set(g[v][1:]):
                    ptr[x] += 1
                for x in list(live):
                    if x not in start and nextuse(x) == 10 ** 9:
                        live.pop(x)
            replay(row, out)
            best = out
        except (ValueError, AssertionError, RecursionError, KeyError):
            pass
    return best, attempts, len(program) - len(active)
