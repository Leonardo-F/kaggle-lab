"""Subgraph rewriting: two-operation, three-operation and grouped cut repair.

The search budgets are frozen at the V8 Final values.  Every candidate is
derived from a programme generated in the same invocation; no historical
answer or submission CSV is read.
"""

import json
import random
from collections import Counter

from .common import replay
from .graph import closures, extract, pairs
from .schedule import compile_graph


def inverse(t, a, L):
    """Enumerate the other operand b for expressions that evaluate to t."""
    for op, b, rev in (('+', t - a, False), ('-', a - t, False), ('-', t + a, True),
                       ('*', t // a if t % a == 0 else 0, False), ('/', t * a, True),
                       ('/', a // t if a % t == 0 else 0, False)):
        if 0 < b <= L:
            yield b, (op, b, a) if rev else (op, a, b)


def exclusive(g, start, v, refs):
    """Nodes that would become unreferenced if v's production were removed."""
    ref = refs.copy()
    removed = set()

    def drop(x):
        ref[x] -= 1
        if ref[x] == 0 and x not in start:
            removed.add(x)
            _, a, b = g[x]
            drop(a)
            drop(b)

    _, a, b = g[v]
    drop(a)
    drop(b)
    return removed


def rewrite(row, program, sweeps=2):
    """Two-operation subgraph rewriting on a fresh V7-derived graph."""
    s = json.loads(row['starting_values'])
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    L = int(row['value_limit'])
    start = set(s)
    g = extract(row, program)
    best = program
    accepted = 0
    novel = 0
    cl, active = closures(g, s, ts)
    g = {x: g[x] for x in active}
    for sweep in range(sweeps):
        changed = 0
        values = sorted(active | start, key=lambda x: (len(cl[x]), x))
        pool = pairs(values, L)
        for v in sorted(active, key=lambda x: (-len(cl[x]), -x)):
            if v not in active:
                continue
            refs = Counter(ts)
            for x in active:
                _, a, b = g[x]
                refs[a] += 1
                refs[b] += 1
            removed = set()

            def drop(x):
                refs[x] -= 1
                if refs[x] == 0 and x not in start:
                    removed.add(x)
                    _, a, b = g[x]
                    drop(a)
                    drop(b)

            _, a, b = g[v]
            drop(a)
            drop(b)
            if not removed:
                continue
            kept = active - removed
            best_delta = 0
            chosen = None
            for a in values:
                if a not in cl or v in cl[a] or a == v:
                    continue
                opts = (('+', v - a, False), ('-', a - v, False), ('-', v + a, True),
                        ('*', v // a if v % a == 0 else 0, False), ('/', v * a, True),
                        ('/', a // v if a % v == 0 else 0, False))
                for op, b, rev in opts:
                    if b <= 0 or b > L or b == v:
                        continue
                    e = (op, b, a) if rev else (op, a, b)
                    if b in cl:
                        if v in cl[b]:
                            continue
                        delta = len((cl[a] | cl[b]) - kept) - len(removed)
                        if delta < best_delta:
                            best_delta = delta
                            chosen = (e, None)
                    elif len(removed) > 1:
                        for eb in pool.get(b, ()):
                            _, c, d = eb
                            if c not in cl or d not in cl or c == v or d == v or v in cl[c] or v in cl[d]:
                                continue
                            delta = 1 + len((cl[a] | cl[c] | cl[d]) - kept) - len(removed)
                            if delta < best_delta:
                                best_delta = delta
                                chosen = (e, (b, eb))
            if chosen is None:
                continue
            e, extra = chosen
            old = g[v]
            g[v] = e
            if extra:
                g[extra[0]] = extra[1]
            nc, na = closures(g, s, ts)
            if len(na) >= len(active):
                g[v] = old
                if extra:
                    g.pop(extra[0])
                continue
            g = {x: g[x] for x in na}
            cl, active = nc, na
            changed += 1
            accepted += 1
            novel += int(extra is not None)
        if not changed:
            break
    return compile_graph(row, g, best), accepted, novel


def three(row, program, sweeps=2, budget=10, neutral=False):
    """Three-operation subgraph rewriting, strict or equal-cost exploration."""
    s = json.loads(row['starting_values'])
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    L = int(row['value_limit'])
    start = set(s)
    g = extract(row, program)
    cl, active = closures(g, s, ts)
    g = {x: g[x] for x in active}
    best = program
    accepted = 0
    equal = 0
    rng = random.Random(832)
    for _ in range(sweeps):
        refs = Counter(ts)
        for v in active:
            _, a, b = g[v]
            refs[a] += 1
            refs[b] += 1
        targets = []
        for v in sorted(active):
            removed = exclusive(g, start, v, refs)
            if len(removed) >= (2 if neutral else 3):
                targets.append((len(removed), v, removed))
        targets.sort(key=lambda x: (-x[0], -x[1]))
        changed = False
        for _, v, removed in targets[:budget]:
            kept = active - removed
            vals = sorted((kept | start) - {v}, key=lambda x: (len(cl[x]), x))
            vals = [x for x in vals if v not in cl[x]]
            if not vals:
                continue
            pool = pairs(vals, L)
            pool = {x: es[0] for x, es in pool.items() if x not in cl and x != v}
            if not pool:
                continue
            bins = {}
            for x in pool:
                bins.setdefault(x.bit_length(), []).append(x)
            probes = []
            for bit, xs in sorted(bins.items()):
                xs.sort()
                probes.extend(rng.sample(xs, min(96, len(xs))))
            proposals = []
            for x in probes:
                for y, e in inverse(v, x, L):
                    if y in pool:
                        proposals.append({x: pool[x], y: pool[y], v: e})
                if len(proposals) >= 4:
                    break
            short = vals[:48]
            if len(vals) > 48:
                short += rng.sample(vals[48:], min(24, len(vals) - 48))
            for a in short:
                for b, e in inverse(v, a, L):
                    if b in cl or b == v:
                        continue
                    for c in short:
                        for d, eb in inverse(b, c, L):
                            if d in pool and d != b:
                                proposals.append({d: pool[d], b: eb, v: e})
                            if len(proposals) >= 8:
                                break
                        if len(proposals) >= 8:
                            break
                    if len(proposals) >= 8:
                        break
                if len(proposals) >= 8:
                    break
            candidate = None
            bestsize = len(active) + int(neutral)
            for p in proposals:
                trial = g | p
                try:
                    tc, ta = closures(trial, s, ts)
                except (ValueError, KeyError, RecursionError):
                    continue
                if len(ta) < bestsize:
                    bestsize = len(ta)
                    candidate = (trial, tc, ta)
            if candidate:
                g, cl, newactive = candidate
                equal += int(len(newactive) == len(active))
                active = newactive
                g = {x: g[x] for x in active}
                accepted += 1
                changed = True
                break
        if not changed:
            break
    best = compile_graph(row, g, best)
    if neutral and accepted and len(best) == len(program):
        try:
            witness = compile_graph(row, g, program + [None] * 8)
            if None not in witness:
                alt, _, _ = rewrite(row, witness, 2)
                if len(alt) < len(best):
                    best = alt
        except (ValueError, KeyError, RecursionError, AssertionError):
            pass
    replay(row, best)
    return best, accepted, equal


def cut_repair(row, program, rounds=8, neutral=True, beam=10):
    """Bounded destroy/repair with joint beam selection of cut-node expressions."""
    s = json.loads(row['starting_values'])
    start = set(s)
    ts = list(dict.fromkeys(json.loads(row['targets'])))
    L = int(row['value_limit'])
    g = extract(row, program)
    cl, active = closures(g, s, ts)
    g = {x: g[x] for x in active}
    best = program
    initial = len(active)
    rng = random.Random(884)
    accepted = flat = trials = 0
    for turn in range(rounds):
        if len(active) < 4:
            break
        refs = Counter(ts)
        for v in active:
            _, a, b = g[v]
            refs[a] += 1
            refs[b] += 1
        ranked = sorted(active, key=lambda v: (-len(exclusive(g, start, v, refs)), -len(cl[v]), v))
        ranked = [v for v in ranked if len(cl[v]) > 1]
        if not ranked:
            break
        anchor = ranked[turn % min(len(ranked), 12)] if turn < 4 else rng.choice(ranked[:min(24, len(ranked))])
        cuts = [anchor]
        size = 2 + turn % 3
        eligible = [v for v in ranked if v != anchor and anchor not in cl[v] and v not in cl[anchor]]
        eligible.sort(key=lambda v: (-len(cl[v] & cl[anchor]), abs(v.bit_length() - anchor.bit_length()),
                                      -len(cl[v]), v))
        if turn % 3 == 2:
            rng.shuffle(eligible)
        for v in eligible:
            if all(v not in cl[w] and w not in cl[v] for w in cuts):
                cuts.append(v)
            if len(cuts) == size:
                break
        if len(cuts) < 2:
            continue
        cs = set(cuts)
        _, fixed = closures(g, start | cs, ts)
        safe = [v for v in sorted(start | active) if not (cl[v] & cs)]
        safe.sort(key=lambda v: (len(cl[v] - fixed), len(cl[v]), v))
        vals = safe[:180]
        if len(safe) > 180:
            vals += rng.sample(safe[180:], min(32, len(safe) - 180))
        vs = set(vals)
        pool = pairs(vals, L)
        fresh = {x: min(es, key=lambda e: (len((cl[e[1]] | cl[e[2]]) - fixed), e))
                 for x, es in pool.items() if x not in cl and x not in cs}
        alternatives = {}
        for v in cuts:
            old = g[v]
            opts = [(old, None, cl[v] - {v})]
            seen = {(old, None)}
            for a in vals:
                for b, e in inverse(v, a, L):
                    if b in vs:
                        aux = None
                        dep = cl[a] | cl[b]
                    elif b in fresh:
                        aux = (b, fresh[b])
                        _, c, d = aux[1]
                        dep = cl[a] | cl[c] | cl[d] | {b}
                    else:
                        continue
                    key = (e, aux)
                    if key not in seen:
                        seen.add(key)
                        opts.append((e, aux, dep))
            opts.sort(key=lambda o: (len(o[2] - fixed), len(o[2]), o[0]))
            alternatives[v] = opts
        share = Counter(x for opts in alternatives.values() for x in {o[1][0] for o in opts if o[1]})
        for v, opts in alternatives.items():
            orig = next(o for o in opts if o[0] == g[v] and o[1] is None)
            shared = sorted((o for o in opts if o[1] and share[o[1][0]] > 1),
                            key=lambda o: (len(o[2] - fixed) - share[o[1][0]] * .8, len(o[2]), o[0]))
            alternatives[v] = list(dict.fromkeys([orig] + opts[:14] + shared[:10]))
        frontier = [(frozenset(fixed), {})]
        cuts.sort(key=lambda v: (len(alternatives[v]), v))
        for v in cuts:
            expanded = []
            for used, patch in frontier:
                for e, aux, dep in alternatives[v]:
                    new = patch | {v: e}
                    if aux:
                        new[aux[0]] = aux[1]
                    u = used | dep | {v}
                    expanded.append((u, new))
            expanded.sort(key=lambda z: (len(z[0]), len(z[1]), tuple(sorted(z[1].items()))))
            frontier = []
            seen = set()
            for u, p in expanded:
                sig = tuple(sorted(p.items()))
                if sig in seen:
                    continue
                seen.add(sig)
                frontier.append((u, p))
                if len(frontier) >= beam:
                    break
        choices = []
        for _, patch in frontier:
            if all(g.get(v) == e for v, e in patch.items()):
                continue
            trial = g | patch
            try:
                tc, ta = closures(trial, s, ts)
            except (ValueError, KeyError, RecursionError):
                continue
            trials += 1
            if len(ta) > len(active) + (1 if neutral and turn % 3 == 2 else 0):
                continue
            if len(ta) > initial + 1:
                continue
            choices.append((len(ta), trial, tc, ta))
        if not choices:
            continue
        choices.sort(key=lambda x: x[0])
        cost, trial, tc, ta = choices[0]
        for _, candidate, _, _ in choices[:3]:
            new = compile_graph(row, candidate, best)
            if len(new) < len(best):
                best = new
        if cost < len(active) or (neutral and turn % 3 == 2 and cost <= len(active) + 1):
            flat += int(cost >= len(active))
            accepted += 1
            g = {v: trial[v] for v in ta}
            cl, active = tc, ta
    replay(row, best)
    return best, {'group_moves': accepted, 'group_nonimproving': flat, 'group_trials': trials}
