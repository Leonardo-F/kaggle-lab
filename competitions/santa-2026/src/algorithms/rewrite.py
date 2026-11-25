"""Frozen V9 graph rewriting (polish).

A single round of the frozen polish policy looks for values whose entire
exclusive dependency subtree can be rebuilt from a smaller suffix expression,
then patches the graph in place.  Two rounds are used by the frozen portfolio.
The search is a bounded local rewrite; it does not prove optimality and never
reads historical programs.
"""

from collections import Counter


def inverses(value, a, limit):
    """One-step ways to produce ``value`` while reusing the known operand ``a``."""
    if value > a:
        yield value - a, ('+', a, value - a)
    if a > value:
        yield a - value, ('-', a, a - value)
    if value + a <= limit:
        yield value + a, ('-', value + a, a)
    if value % a == 0:
        yield value // a, ('*', a, value // a)
    if value * a <= limit:
        yield value * a, ('/', value * a, a)
    if a % value == 0:
        yield a // value, ('/', a, a // value)


def polish(graph, starting, targets, limit, rounds=2):
    """Rewrite ``graph`` in place for ``rounds`` sweeps; return (graph, moves)."""
    graph = graph.copy()
    start = set(starting)
    targets = set(targets)
    moves = 0

    def state():
        closure = {v: frozenset() for v in start}

        def deps(v):
            if v not in closure:
                _, a, b = graph[v]
                closure[v] = deps(a) | deps(b) | {v}
            return closure[v]

        active = set().union(*(deps(t) for t in targets))
        refs = Counter(targets)
        for v in active:
            refs.update(set(graph[v][1:]))
        return closure, deps, active, refs

    def exclusive(v, refs):
        deleted = set()
        counts = refs.copy()
        stack = list(set(graph[v][1:]))
        while stack:
            x = stack.pop()
            counts[x] -= 1
            if x not in start and counts[x] == 0 and x not in deleted:
                deleted.add(x)
                stack.extend(set(graph[x][1:]))
        return deleted

    for _ in range(rounds):
        closure, deps, active, refs = state()
        pool = {}
        values = sorted(start | active)
        for i, a in enumerate(values):
            for b in values[:i + 1]:
                for z, e in ((a + b, ('+', a, b)), (a * b, ('*', a, b)),
                             (a - b, ('-', a, b)), (a // b if a % b == 0 else 0, ('/', a, b))):
                    if 1 <= z <= limit and z not in start and z not in graph:
                        pool.setdefault(z, e)
        ranked = sorted(active, key=lambda v: (-len(exclusive(v, refs)), v))[:20]
        for v in ranked:
            closure, deps, active, refs = state()
            if v not in active:
                continue
            dead = exclusive(v, refs)
            if not dead:
                continue
            fixed = active - dead
            best = 0
            patch = None
            for a in sorted(start | active):
                ca = deps(a)
                if v in ca:
                    continue
                for b, e in inverses(v, a, limit):
                    if b == v:
                        continue
                    if b in start or b in graph:
                        cb = deps(b)
                        if v in cb:
                            continue
                        new = ca | cb
                        aux = None
                    elif b in pool:
                        _, c, d = pool[b]
                        cb = deps(c) | deps(d)
                        if v in cb:
                            continue
                        new = ca | cb | {b}
                        aux = (b, pool[b])
                    else:
                        continue
                    gain = len(dead) - len(new - fixed)
                    if gain > best:
                        best = gain
                        patch = (e, aux)
            if patch:
                e, aux = patch
                if aux:
                    graph[aux[0]] = aux[1]
                graph[v] = e
                moves += 1
        closure, deps, active, refs = state()
        graph = {v: graph[v] for v in active}
    return graph, moves
