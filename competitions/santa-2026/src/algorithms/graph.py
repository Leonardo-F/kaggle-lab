"""Compile an arithmetic dependency DAG into register instructions."""
import json
import random
from collections import defaultdict
from .common import arithmetic, replay

def compile_graph(row, graph, tries=8):
    s = json.loads(row['starting_values'])
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    L = int(row['value_limit'])
    R = int(row['registers'])
    start = set(s)
    cl = {v: set() for v in s}

    def closure(v, stack=frozenset()):
        if v in cl:
            return cl[v]
        if v in stack:
            raise ValueError('cycle')
        op, a, b = graph[v]
        if not 1 <= v <= L or arithmetic(op, a, b) != v:
            raise ValueError('invalid graph')
        cl[v] = closure(a, stack | {v}) | closure(b, stack | {v}) | {v}
        return cl[v]
    for v in ts:
        closure(v)
    rng = random.Random(919)
    best = None
    for turn in range(tries):
        roots = ts.copy()
        if turn % 4 == 1:
            roots.reverse()
        elif turn % 4 == 2:
            roots.sort(key=lambda v: len(cl[v]), reverse=turn % 8 == 6)
        elif turn % 4 == 3:
            rng.shuffle(roots)
        done = set(s)
        order = []

        def visit(v):
            if v in done:
                return
            _, a, b = graph[v]
            if (len(cl[a]) < len(cl[b])) == (turn % 2 == 0):
                a, b = (b, a)
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
        live = {x: i for i, x in enumerate(s)}
        p = []
        index = 0

        def ensure(v, protect):
            if v in live:
                return
            op, a, b = graph[v]
            ensure(a, protect)
            ensure(b, protect | {a})
            i, j = (live[a], live[b])
            free = set(range(R)) - set(live.values())
            if free:
                d = min(free)
            else:
                options = [x for x in live if x not in start and x not in protect]
                if not options:
                    raise ValueError('register pressure')

                def rank(x):
                    nxt = next((k for k in future[x] if k > index), len(order) + 10000)
                    return ((nxt - index) / (1 + len(cl[x]) if turn % 2 else 1), nxt, -len(cl[x]), x)
                x = max(options, key=rank)
                d = live.pop(x)
            p.append([op, i, j, d])
            live[v] = d
        try:
            for index, v in enumerate(order):
                ensure(v, set())
                for x in list(live):
                    if x not in start and (not any((k > index for k in future[x]))):
                        live.pop(x)
            replay(row, p)
        except (ValueError, KeyError, RecursionError):
            continue
        if best is None or len(p) < len(best):
            best = p
        if best is not None and len(best) == len(order):
            break
    if best is None:
        raise ValueError('no valid schedule')
    return (best, len(order))
