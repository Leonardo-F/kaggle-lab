"""Shared arithmetic, replay, fixed-radix construction and value-DAG compilation.

These primitives are used by every functional stage.  They contain no search
policy of their own, so they can be shared without changing candidate order or
random-number consumption.
"""

import json
from collections import Counter


def ops(a, b, L):
    if a + b <= L:
        yield a + b, ('+', a, b)
    if a * b <= L:
        yield a * b, ('*', a, b)
    if a > b:
        yield a - b, ('-', a, b)
    if b > a:
        yield b - a, ('-', b, a)
    if a % b == 0:
        yield a // b, ('/', a, b)
    if b % a == 0:
        yield b // a, ('/', b, a)


def replay(row, program):
    start = json.loads(row['starting_values'])
    targets = set(json.loads(row['targets']))
    limit = int(row['value_limit'])
    n = int(row['registers'])
    if len(program) > 4096 or len(json.dumps(program, separators=(',', ':')).encode()) > 128 * 1024:
        raise ValueError('program size limit')
    regs = start + [None] * (n - len(start))
    seen = set(start)
    for op, a, b, d in program:
        if not all(type(i) is int and 0 <= i < n for i in (a, b, d)):
            raise ValueError('register index')
        x, y = regs[a], regs[b]
        if x is None or y is None:
            raise ValueError('uninitialized register')
        if op == '+':
            z = x + y
        elif op == '-':
            z = x - y
        elif op == '*':
            z = x * y
        elif op == '/' and y and x % y == 0:
            z = x // y
        else:
            raise ValueError('invalid operator or division')
        if not 0 < z <= limit:
            raise ValueError('value limit')
        regs[d] = z
        seen.add(z)
    if not targets <= seen:
        raise ValueError('missing targets')
    return len(program)


def compile_dag(s, ts, expr, anc, L, registers=48):
    """Compile a value DAG in depth-first order, evicting by remaining use.

    ``expr[v]`` is the production of a non-start value and ``anc[v]`` its
    dependency closure.  Returns ``(instruction_count, node_count, program)``.
    This is the shared compiler historically inlined in V1/V3/V4/V5.
    """
    order = []
    visited = set(s)

    def visit(v):
        if v in visited:
            return
        op, a, b = expr[v]
        visit(a)
        visit(b)
        visited.add(v)
        order.append(v)

    for t in ts:
        visit(t)
    remaining = Counter(x for v in order for x in expr[v][1:])
    live = {v: i for i, v in enumerate(s)}
    prog = []
    achieved = set(s)
    regs = list(s) + [None] * (registers - len(s))

    def ensure(v, protect):
        if v in live:
            return
        op, a, b = expr[v]
        ensure(a, protect)
        ensure(b, protect | {a})
        ai, bi = live[a], live[b]
        free = set(range(registers)) - set(live.values())
        if free:
            d = min(free)
        else:
            cand = [k for k in live if k not in protect and k not in s]
            if not cand:
                raise ValueError('pressure')
            k = min(cand, key=lambda k: (remaining[k] > 0, len(anc[k]), remaining[k]))
            d = live.pop(k)
        prog.append([op, ai, bi, d])
        live[v] = d
        x, y = regs[ai], regs[bi]
        z = x + y if op == '+' else x - y if op == '-' else x * y if op == '*' else x // y
        assert op != '/' or x % y == 0
        assert z == v and 0 < z <= L
        regs[d] = z
        achieved.add(z)

    for v in order:
        ensure(v, set())
        for x in expr[v][1:]:
            remaining[x] -= 1
        for k in list(live):
            if k not in s and remaining[k] == 0:
                live.pop(k)
    assert set(ts) <= achieved and len(prog) <= 4096
    return len(prog), len(order), prog


def sparse(s, ts, L, base=4096, digit=32, reverse=False):
    expr = {v: None for v in s}
    anc = {v: frozenset() for v in s}

    def add(v, op, a, b):
        if v not in expr:
            assert 0 < v <= L and a in expr and b in expr
            expr[v] = (op, a, b)
            anc[v] = anc[a] | anc[b] | {v}
        return v

    add(1, '/', s[0], s[0])
    # Balanced small digits; reuse all materialized values across targets.
    def make(v):
        if v in expr:
            return v
        if v <= digit:
            a = v // 2
            b = v - a
            make(a)
            make(b)
            return add(v, '+', a, b)
        q, r = divmod(v, digit)
        make(digit)
        make(q)
        p = q * digit
        add(p, '*', q, digit)
        if r:
            make(r)
            add(v, '+', p, r)
        return v

    if base > L:
        base = min(L, max(2, digit))
    make(base)

    def build(v):
        if v in expr:
            return v
        if v < base:
            return make(v)
        q, r = divmod(v, base)
        if r > base // 2 and (q + 1) * base <= L:
            q += 1
            r -= base
        build(q)
        p = q * base
        add(p, '*', q, base)
        if r:
            make(abs(r))
            add(v, '+' if r > 0 else '-', p, abs(r))
        return v

    ts = sorted(ts, reverse=reverse)
    for t in ts:
        build(t)
    return compile_dag(s, ts, expr, anc, L)
