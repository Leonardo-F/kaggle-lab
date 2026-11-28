"""Register-pressure scheduling of a candidate graph."""
import random
import bisect
import json
from collections import defaultdict, Counter
from .common import replay, arithmetic

def schedule(row, g, best, tries=32):
    s = list(json.loads(row['starting_values']))
    S = set(s)
    T = list(dict.fromkeys(json.loads(row['targets'])))
    R = int(row['registers'])
    cl = {v: frozenset() for v in S}
    depth = {v: 0 for v in S}
    top = []

    def visit(v):
        if v not in cl:
            o, a, b = g[v]
            visit(a)
            visit(b)
            cl[v] = cl[a] | cl[b] | {v}
            depth[v] = 1 + max(depth[a], depth[b])
            top.append(v)
    for v in T:
        visit(v)
    g = {v: g[v] for v in top}
    N = len(g)
    if len(best) == N:
        return (best, dict(nodes=N, attempts=0))
    users = defaultdict(list)
    deps = {v: set(g[v][1:]) for v in g}
    for v in g:
        for x in deps[v]:
            users[x].append(v)
    rng = random.Random(202609)
    orders = {}

    def dfs(roots, rev=False):
        seen = set(S)
        order = []

        def walk(v):
            if v in seen:
                return
            a, b = g[v][1:]
            a, b = sorted((a, b), key=lambda x: (len(cl[x]), x), reverse=rev)
            walk(a)
            walk(b)
            seen.add(v)
            order.append(v)
        for v in roots:
            walk(v)
        return tuple(order)

    def cluster(seed, metric):
        rem = set(T)
        roots = []
        last = seed
        made = set()
        while rem:
            if last not in rem:
                if metric == 0:
                    last = max(rem, key=lambda t: (len(cl[t] & made), -len(cl[t] - made), -t))
                elif metric == 1:
                    last = max(rem, key=lambda t: (len(cl[t] & cl[roots[-1]]), -len(cl[t] - made), -t))
                else:
                    last = max(rem, key=lambda t: (len(cl[t] & made) / (1 + len(cl[t] - made)), -t))
            roots.append(last)
            rem.remove(last)
            made.update(cl[last])
        return roots

    def pressure(order):
        last = {}
        for i, v in enumerate(order):
            for x in deps[v]:
                last[x] = i
        live = set(S)
        excess = area = peak = 0
        for i, v in enumerate(order):
            for x in deps[v]:
                if x not in S and last[x] == i:
                    live.discard(x)
            if last.get(v, -1) > i:
                live.add(v)
            k = len(live)
            excess += max(0, k - R)
            area += k
            peak = max(peak, k)
        return (excess, peak, area)

    def add(o):
        if o not in orders:
            orders[o] = pressure(o)
    for roots in (T, T[::-1], sorted(T), sorted(T, reverse=True), sorted(T, key=lambda t: (len(cl[t]), t)), sorted(T, key=lambda t: (-len(cl[t]), t))):
        for rev in (False, True):
            add(dfs(roots, rev))
    for seed in (min(T), max(T), max(T, key=lambda t: len(cl[t]))):
        for m in range(3):
            roots = cluster(seed, m)
            add(dfs(roots))
            add(dfs(roots, True))

    def list_order(mode):
        pending = {v: len(deps[v] - S) for v in g}
        ready = {v for v, n in pending.items() if not n}
        rem = {v: len(users[v]) for v in set(g) | S}
        order = []
        rank = {v: rng.random() for v in g}
        last = set(S)
        while ready:

            def priority(v):
                release = sum((x not in S and rem[x] == 1 for x in deps[v]))
                new = int(rem[v] > 0)
                unlock = sum((pending[x] == 1 for x in users[v]))
                reuse = len(deps[v] & last)
                if mode % 4 == 0:
                    return (release - new, release, unlock, reuse, -len(cl[v]), rank[v])
                if mode % 4 == 1:
                    return (release - new, unlock, reuse, depth[v], rank[v])
                if mode % 4 == 2:
                    return (release - new, reuse, release, -len(cl[v]), rank[v])
                return (release - new, release, rank[v], unlock)
            v = max(ready, key=priority)
            ready.remove(v)
            order.append(v)
            last = deps[v] | {v}
            for x in deps[v]:
                rem[x] -= 1
            for x in users[v]:
                pending[x] -= 1
                if pending[x] == 0:
                    ready.add(x)
        return tuple(order)
    for i in range(8):
        add(list_order(i))
    roots = T[:]
    rng.shuffle(roots)
    cur = pressure(dfs(roots))
    broot = roots[:]
    for k in range(tries):
        trial = broot[:]
        i, j = rng.sample(range(len(T)), 2) if len(T) > 1 else (0, 0)
        trial[i], trial[j] = (trial[j], trial[i])
        o = dfs(trial, k % 2 == 0)
        p = pressure(o)
        add(o)
        if p <= cur:
            cur = p
            broot = trial

    def emit(order, mode):
        future = defaultdict(list)
        for i, v in enumerate(order):
            for x in deps[v]:
                future[x].append(i)
        live = {v: i for i, v in enumerate(s)}
        p = []
        idx = 0

        def nxt(x):
            f = future[x]
            j = bisect.bisect_right(f, idx)
            return f[j] if j < len(f) else N + 1000

        def cost(x):
            return len(cl[x] - live.keys()) + 1

        def ensure(v, protect):
            if v in live:
                return
            op, a, b = g[v]
            if mode % 2 and len(cl[b] - live.keys()) > len(cl[a] - live.keys()):
                ensure(b, protect)
                ensure(a, protect | {b})
            else:
                ensure(a, protect)
                ensure(b, protect | {a})
            ai, bi = (live[a], live[b])
            free = set(range(R)) - set(live.values())
            dead = [x for x in (a, b) if x not in S and x not in protect and (nxt(x) > N)]
            if dead:
                d = live.pop(dead[0])
            elif free:
                d = min(free)
            else:
                opts = [x for x in live if x not in S and x not in protect]
                if not opts:
                    raise ValueError('register pressure')
                if mode // 2 == 0:
                    x = max(opts, key=lambda x: (nxt(x), -cost(x), x))
                elif mode // 2 == 1:
                    x = max(opts, key=lambda x: ((nxt(x) - idx) / cost(x), nxt(x), x))
                else:
                    x = max(opts, key=lambda x: ((nxt(x) - idx) / cost(x) ** 0.5, nxt(x), x))
                d = live.pop(x)
            p.append([op, ai, bi, d])
            live[v] = d
        for idx, v in enumerate(order):
            ensure(v, set())
            for x in list(live):
                if x not in S and nxt(x) > N:
                    live.pop(x)
            if len(p) >= len(best):
                return None
        replay(row, p)
        return p
    attempts = 0
    for order, _ in sorted(orders.items(), key=lambda z: z[1])[:12]:
        for mode in range(6):
            attempts += 1
            try:
                p = emit(order, mode)
            except (ValueError, KeyError, RecursionError):
                continue
            if p is not None and len(p) < len(best):
                best = p
            if len(best) == N:
                return (best, dict(nodes=N, attempts=attempts))
    return (best, dict(nodes=N, attempts=attempts))


def compile_candidate(row, graph, local_search=False):
    """Frozen candidate evaluation budget, shared by both portfolio branches."""
    from .graph import compile_graph
    from .schedule_local import schedule_local

    program, nodes = compile_graph(row, graph, tries=4)
    program, _ = schedule(row, graph, program, tries=16)
    if local_search:
        program, _ = schedule_local(row, graph, program)
    replay(row, program)
    return program, nodes
