"""Adaptive expression construction strategies.

Three construction policies remain distinguishable because they search
different candidate spaces: the early legacy beam, the quotient-neighbour beam,
and the product/residue-augmented beam.  The latter two are one parameterised
implementation: with the product and residue switches off it executes exactly
the historical V4 policy, and with them on it executes the historical V5
policy.  Only the search space differs; candidate ordering and random-number
consumption are unchanged.
"""

import json
import random
from bisect import bisect_left
from functools import lru_cache

from .common import compile_dag, ops


def adaptive_base(s, ts, L, seed=0, width=2, wide=False, bidir=False):
    """Early adaptive beam (V3) without quotient neighbours or product pool."""
    rng = random.Random(seed)
    expr = {v: None for v in s}
    anc = {v: frozenset() for v in s}

    def add(v, e):
        a, b = e[1:]
        deps = anc[a] | anc[b] | {v}
        if v not in anc or len(deps) < len(anc[v]):
            # first create only: changing ancestors of existing expressions invalidates cache
            if v not in anc:
                expr[v] = e
                anc[v] = deps

    for _ in range(2):
        old = list(expr)
        for i, a in enumerate(old):
            for b in old[:i + 1]:
                for v, e in ops(a, b, L):
                    add(v, e)
    if len(s) == 1:
        for v in range(2, min(L, 48) + 1):
            add(v, ('+', v // 2, v - v // 2))
        for v in (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
            if v <= L:
                add(v, ('+', v // 2, v // 2))
    l2 = list(expr)
    l1 = [v for v in l2 if len(anc[v]) <= 1]

    # broad cheap pool, one operation over L2 and L1
    # Limit expansion to stratified low-cost values (deterministic budget).
    def stratified(values, count):
        buckets = {}
        for v in values:
            buckets.setdefault(v.bit_length(), []).append(v)
        for vv in buckets.values():
            vv.sort(key=lambda v: (len(anc[v]), rng.random()))
        return [v for vv in buckets.values() for v in vv[:count]]

    limited_l1 = stratified(l1, 8)
    for a in stratified(l2, 18):
        for b in limited_l1:
            for v, e in ops(a, b, L):
                add(v, e)
    # supplement small dense dictionary with additions of L2 values
    small = stratified([v for v in l2 if v < 4096], 12)
    for i, a in enumerate(small):
        for b in small[:i + 1]:
            for v, e in ops(a, b, min(L, 65536)):
                add(v, e)
    # get a set of varied divisors: prioritize 1-3 step bases
    maxbit = max(ts).bit_length()
    bins = {}
    for v in l2:
        if v > 1 and v.bit_length() <= min(22, maxbit // 2 + 3):
            bins.setdefault(v.bit_length(), []).append(v)
    l2set = set(l2)
    extra = {}
    for v in expr:
        if v > 1 and v not in l2set and len(anc[v]) <= 3 and v.bit_length() <= min(24, maxbit // 2 + 3):
            extra.setdefault(v.bit_length(), []).append(v)
    bases = []
    for k, vs in extra.items():
        vs.sort(key=lambda v: (len(anc[v]), rng.random()))
        bases.extend(vs[:5 if wide else 3])
    for k, vs in bins.items():
        vs.sort(key=lambda v: (len(anc[v]), rng.random()))
        bases.extend(vs[:10 if wide else 7])
    # powers and other bases chosen by coverage; use L2 cheaply
    bases = sorted(set(bases), reverse=True)
    used = set()
    probe = stratified(list(expr), 6) if bidir else []

    # per target beam recursion, expressions are immutable (tuple trees), cost union
    def leaf(v):
        return (anc[v], ())

    def build_fallback(v):
        if v in expr:
            return
        if v <= 1:
            raise ValueError("missing unit")
        # Guaranteed recursive construction from 1; use existing inexpensive nodes.
        b = 16 if v < 4096 else 256
        if v <= b:
            a = v // 2
            c = v - a
            build_fallback(a)
            build_fallback(c)
            add(v, ('+', a, c))
            return
        q, r = divmod(v, b)
        build_fallback(b)
        build_fallback(q)
        p = q * b
        add(p, ('*', q, b))
        if r:
            build_fallback(r)
            add(v, ('+', p, r))

    for t in ts:
        @lru_cache(None)
        def rec(v, depth):
            if v in expr:
                return leaf(v)
            if depth <= 0 or v <= 1:
                return None
            cand = []
            direct = None
            direct_cost = 10 ** 9
            if bidir:
                # Reverse operation with a known operand; hash lookup of its complement.
                for a in dict.fromkeys(probe + sorted(used)):
                    for o, b, rev in (('+', v - a, False), ('-', a - v, False), ('-', v + a, True),
                                      ('*', v // a if v % a == 0 else 0, False), ('/', v * a, True),
                                      ('/', a // v if a % v == 0 else 0, False)):
                        if b not in expr or not 0 < b <= L:
                            continue
                        ds = anc[a] | anc[b] | {v}
                        c = len(ds - used)
                        if c < direct_cost:
                            direct = (ds, ((v, (o, b, a) if rev else (o, a, b)),))
                            direct_cost = c
                    if direct_cost == 1:
                        return direct
            for a in bases:
                if a >= v:
                    continue
                q, r = divmod(v, a)
                for qq, rr, sign in ((q, r, '+'), (q + 1, a - r, '-')):
                    if qq >= v or a * qq > L:
                        continue
                    if rr and rr not in expr:
                        continue
                    # rank split by residual + base cost + estimated remaining magnitude
                    c = len((anc[a] | (anc[rr] if rr else set())) - used) + (1 if not rr else 2)
                    est = c + (len(anc[qq] - used) if qq in expr else max(2, (qq.bit_length() - 9) * .30))
                    cand.append((est, a, qq, rr, sign))
            cand.sort()
            best = direct
            bc = direct_cost
            for _, a, q, r, sign in cand[:width]:
                sub = rec(q, depth - 1)
                if sub is None:
                    continue
                p = a * q
                ds = sub[0] | anc[a] | {p}
                es = sub[1] + ((p, ('*', a, q)),)
                if r:
                    ds = ds | anc[r] | {v}
                    es = es + ((v, (sign, p, r)),)
                cost = len(ds - used)
                if cost < bc:
                    best = (ds, es)
                    bc = cost
            return best

        out = rec(t, 4)
        if out is None:
            build_fallback(t)
            used |= anc[t]
            continue
        for v, e in out[1]:
            if v not in expr:
                expr[v] = e
                anc[v] = anc[e[1]] | anc[e[2]] | {v}
        used |= anc[t]
    return compile_dag(s, ts, expr, anc, L)


def adaptive_quotient(s, ts, L, seed=3, width=3, wide=True, bidir=True,
                      products=True, modular=True, direct_products=True,
                      factor_count=4):
    """Quotient-neighbour beam, optionally augmented with products and residues.

    ``products=False, modular=False, direct_products=False`` is the V4 policy;
    the defaults are the V5 policy.  The flag checks are placed exactly where
    the historical implementations diverge, so both variants consume the same
    random numbers and return the same candidates as before.
    """
    rng = random.Random(seed)
    expr = {v: None for v in s}
    anc = {v: frozenset() for v in s}

    def add(v, e):
        a, b = e[1:]
        deps = anc[a] | anc[b] | {v}
        if v not in anc or len(deps) < len(anc[v]):
            # first create only: changing ancestors of existing expressions invalidates cache
            if v not in anc:
                expr[v] = e
                anc[v] = deps

    for _ in range(2):
        old = list(expr)
        for i, a in enumerate(old):
            for b in old[:i + 1]:
                for v, e in ops(a, b, L):
                    add(v, e)
    if len(s) == 1:
        for v in range(2, min(L, 48) + 1):
            add(v, ('+', v // 2, v - v // 2))
        for v in (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
            if v <= L:
                add(v, ('+', v // 2, v // 2))
    l2 = list(expr)
    l1 = [v for v in l2 if len(anc[v]) <= 1]

    # broad cheap pool, one operation over L2 and L1
    # Limit expansion to stratified low-cost values (deterministic budget).
    def stratified(values, count):
        buckets = {}
        for v in values:
            buckets.setdefault(v.bit_length(), []).append(v)
        for vv in buckets.values():
            vv.sort(key=lambda v: (len(anc[v]), rng.random()))
        return [v for vv in buckets.values() for v in vv[:count]]

    limited_l1 = stratified(l1, 8)
    for a in stratified(l2, 18):
        for b in limited_l1:
            for v, e in ops(a, b, L):
                add(v, e)
    # supplement small dense dictionary with additions of L2 values
    small = stratified([v for v in l2 if v < 4096], 12)
    for i, a in enumerate(small):
        for b in small[:i + 1]:
            for v, e in ops(a, b, min(L, 65536)):
                add(v, e)
    # Expand a stratified subset of cheap values into products and differences.
    mid = stratified([v for v in l2 if len(anc[v]) <= 3], 4)
    for i, a in enumerate(mid):
        for b in mid[:i + 1]:
            for v, e in ops(a, b, L):
                add(v, e)
    # get a set of varied divisors: prioritize 1-3 step bases
    maxbit = max(ts).bit_length()
    bins = {}
    for v in l2:
        if v > 1 and v.bit_length() <= min(22, maxbit // 2 + 3):
            bins.setdefault(v.bit_length(), []).append(v)
    l2set = set(l2)
    extra = {}
    for v in expr:
        if v > 1 and v not in l2set and len(anc[v]) <= 3 and v.bit_length() <= min(24, maxbit // 2 + 3):
            extra.setdefault(v.bit_length(), []).append(v)
    bases = []
    for k, vs in extra.items():
        vs.sort(key=lambda v: (len(anc[v]), rng.random()))
        bases.extend(vs[:5 if wide else 3])
    for k, vs in bins.items():
        vs.sort(key=lambda v: (len(anc[v]), rng.random()))
        bases.extend(vs[:10 if wide else 7])
    # powers and other bases chosen by coverage; use L2 cheaply
    bases = sorted(set(bases), reverse=True)
    # Products of cheap factors, derived exclusively from initial values.
    product_values = set()
    if products:
        factors = stratified([v for v in expr if v > 1 and len(anc[v]) <= 3
                              and v.bit_length() <= min(32, maxbit // 2 + 5)], factor_count)
        for i, a in enumerate(factors):
            for b in factors[:i + 1]:
                v = a * b
                if v <= L:
                    add(v, ('*', a, b))
                    product_values.add(v)
    products_sorted = sorted(product_values, key=lambda v: (len(anc[v]), v))
    residue_index = {}
    if products_sorted:
        mod_bases = stratified([a for a in bases if 6 <= a.bit_length() <= 22], 3)
        max_target = max(ts)
        for a in mod_bases:
            table = {}
            for r in products_sorted:
                if r > max_target:
                    continue
                bucket = table.setdefault(r % a, [])
                if len(bucket) < 2:
                    bucket.append(r)
            residue_index[a] = table
    if not modular:
        residue_index.clear()
    used = set()
    probe = stratified(list(expr), 6) if bidir else []
    # per target beam recursion, expressions are immutable (tuple trees), cost union
    def leaf(v):
        return (anc[v], ())

    def build_fallback(v):
        if v in expr:
            return
        if v <= 1:
            raise ValueError("missing unit")
        # Guaranteed recursive construction from 1; use existing inexpensive nodes.
        b = 16 if v < 4096 else 256
        if v <= b:
            a = v // 2
            c = v - a
            build_fallback(a)
            build_fallback(c)
            add(v, ('+', a, c))
            return
        q, r = divmod(v, b)
        build_fallback(b)
        build_fallback(q)
        p = q * b
        add(p, ('*', q, b))
        if r:
            build_fallback(r)
            add(v, ('+', p, r))

    for t in ts:
        current_bases = sorted(set(bases) | set(stratified([v for v in used if v > 1], 3)), reverse=True)
        known = sorted(expr)
        probes = list(dict.fromkeys(probe + sorted(used)))

        @lru_cache(None)
        def rec(v, depth):
            if v in expr:
                return leaf(v)
            if depth <= 0 or v <= 1:
                return None
            cand = []
            direct = None
            direct_cost = 10 ** 9
            if bidir:
                # Reverse operation with a known operand; hash lookup of its complement.
                for a in probes:
                    for o, b, rev in (('+', v - a, False), ('-', a - v, False), ('-', v + a, True),
                                      ('*', v // a if v % a == 0 else 0, False), ('/', v * a, True),
                                      ('/', a // v if a % v == 0 else 0, False)):
                        if b not in expr or not 0 < b <= L:
                            continue
                        ds = anc[a] | anc[b] | {v}
                        c = len(ds - used)
                        if c < direct_cost:
                            direct = (ds, ((v, (o, b, a) if rev else (o, a, b)),))
                            direct_cost = c
                if direct_cost == 1:
                    return direct
            # Match two products or one product and another known value.
            if products and direct_products and depth == 4:
                for a in products_sorted:
                    for b, o, rev in ((v - a, '+', False), (a - v, '-', False), (a + v, '-', True)):
                        if b not in expr or b == v:
                            continue
                        ds = anc[a] | anc[b] | {v}
                        c = len(ds - used)
                        if c < direct_cost:
                            direct = (ds, ((v, (o, b, a) if rev else (o, a, b)),))
                            direct_cost = c
                    if direct_cost == 1:
                        return direct
            for a in current_bases:
                if a >= v:
                    continue
                q, r = divmod(v, a)
                splits = [(q, r, '+'), (q + 1, a - r, '-')]
                # Match a nearby already constructible quotient; the residue
                # need not be the conventional remainder modulo a.
                pos = bisect_left(known, q)
                for qq in known[max(0, pos - 1):pos + 2]:
                    p = a * qq
                    if p <= L and p != v:
                        splits.append((qq, abs(v - p), '+' if p < v else '-'))
                table = residue_index.get(a)
                if table is not None:
                    for rr in table.get(v % a, ()):
                        qq = (v - rr) // a
                        if qq > 0:
                            splits.append((qq, rr, '+'))
                    for rr in table.get((-v) % a, ()):
                        qq = (v + rr) // a
                        if qq > 0:
                            splits.append((qq, rr, '-'))
                for qq, rr, sign in dict.fromkeys(splits):
                    if qq < 1 or qq >= v or a * qq > L:
                        continue
                    if rr and rr not in expr:
                        continue
                    # rank split by residual + base cost + estimated remaining magnitude
                    c = len((anc[a] | (anc[rr] if rr else set())) - used) + (1 if not rr else 2)
                    if qq in expr:
                        p = a * qq
                        ds = anc[a] | anc[qq] | (anc[rr] if rr else set()) | {p, v}
                        if p in expr:
                            ds = anc[p] | (anc[rr] if rr else set()) | {v}
                        est = len(ds - used)
                    else:
                        est = c + max(2, (qq.bit_length() - 9) * .30)
                    cand.append((est, a, qq, rr, sign))
            cand.sort()
            best = direct
            bc = direct_cost
            for _, a, q, r, sign in cand[:width]:
                sub = rec(q, depth - 1)
                if sub is None:
                    continue
                p = a * q
                if p in expr:
                    ds = anc[p]
                    es = ()
                else:
                    ds = sub[0] | anc[a] | {p}
                    es = sub[1] + ((p, ('*', a, q)),)
                if r:
                    ds = ds | anc[r] | {v}
                    es = es + ((v, (sign, p, r)),)
                cost = len(ds - used)
                if cost < bc:
                    best = (ds, es)
                    bc = cost
            return best

        out = rec(t, 4)
        if out is None:
            build_fallback(t)
            used |= anc[t]
            continue
        for v, e in out[1]:
            if v not in expr:
                expr[v] = e
                anc[v] = anc[e[1]] | anc[e[2]] | {v}
        used |= anc[t]
    return compile_dag(s, ts, expr, anc, L)


def adaptive_v4(s, ts, L, seed=3, width=3, wide=True, bidir=True):
    """V4 quotient-neighbour policy: no product pool, no residue index."""
    return adaptive_quotient(s, ts, L, seed=seed, width=width, wide=wide, bidir=bidir,
                             products=False, modular=False, direct_products=False)


def adaptive_v5(s, ts, L, seed=3, width=3, wide=True, bidir=True, products=True,
                modular=True, direct_products=True, factor_count=4):
    """V5 product/residue policy."""
    return adaptive_quotient(s, ts, L, seed=seed, width=width, wide=wide, bidir=bidir,
                             products=products, modular=modular,
                             direct_products=direct_products, factor_count=factor_count)


def plans(s, ts):
    """Feature-adaptive plan order used by the V7 portfolio stage."""
    maxbit = max(ts).bit_length()
    spread = maxbit - min(ts).bit_length()
    asc = sorted(ts)
    yield 'asc-seed5', asc, 5, 3
    if len(ts) >= 20:
        if spread >= 6:
            order = sorted(ts, key=lambda t: (-t.bit_length(), t))
        else:
            order = sorted(ts, key=lambda t: (t % 256, t))
        yield 'feature-order', order, 6, 3
        if maxbit >= 40:
            yield 'wide-asc', asc, 7, 4
    elif len(s) <= 2 and maxbit >= 25:
        yield 'small-start-wide', asc, 7, 4
