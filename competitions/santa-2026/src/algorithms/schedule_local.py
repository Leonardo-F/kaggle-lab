"""Local search over scheduling orders."""
import json
import random
import math
from .common import replay

def schedule_local(row, g, best, steps=180):
    s = json.loads(row['starting_values'])
    targets = list(dict.fromkeys(json.loads(row['targets'])))
    R = int(row['registers'])
    S = set(s)
    seen = set(S)
    top = []

    def visit(v):
        if v in seen:
            return
        _, a, b = g[v]
        visit(a)
        visit(b)
        seen.add(v)
        top.append(v)
    for t in targets:
        visit(t)
    N = len(top)
    if len(best) == N:
        return (best, {'nodes': N, 'tries': 0, 'peak': None})
    vals = list(dict.fromkeys(s)) + top
    idx = {v: i for i, v in enumerate(vals)}
    K = len(S)
    n = len(vals)
    deps = [None] * K + [(idx[g[v][1]], idx[g[v][2]]) for v in top]
    counts = [0] * n
    cl = [0] * n
    for i in range(K, n):
        a, b = deps[i]
        counts[a] += 1
        counts[b] += a != b
        cl[i] = cl[a] | cl[b] | 1 << i
    roots = [idx[t] for t in targets if t not in S]
    rng = random.Random(8821)

    def order(roots, mode):
        made = (1 << K) - 1
        out = []

        def walk(i):
            nonlocal made
            if made >> i & 1:
                return
            a, b = deps[i]
            if mode == 0:
                flip = (cl[b] & ~made).bit_count() > (cl[a] & ~made).bit_count()
            elif mode == 1:
                flip = (cl[b] & ~made).bit_count() < (cl[a] & ~made).bit_count()
            elif mode == 2:
                flip = b < a
            else:
                flip = b > a
            if flip:
                a, b = (b, a)
            walk(a)
            walk(b)
            made |= 1 << i
            out.append(i)
        for i in roots:
            walk(i)
        return out

    def assess(o):
        rem = counts[:]
        live = sum((x > 0 for x in rem[:K]))
        peak = live
        excess = area = 0
        for i in o:
            a, b = deps[i]
            rem[a] -= 1
            live -= rem[a] == 0
            if b != a:
                rem[b] -= 1
                live -= rem[b] == 0
            p = live + 1
            peak = max(peak, p)
            excess += max(0, p - R)
            area += p
            live += rem[i] > 0
        return (excess, peak, area)

    def emit(o):
        rem = counts[:]
        live = {idx[v]: i for i, v in enumerate(s) if counts[idx[v]]}
        p = []
        for i in o:
            a, b = deps[i]
            ai, bi = (live[a], live[b])
            rem[a] -= 1
            if a != b:
                rem[b] -= 1
            for x in {a, b}:
                if rem[x] == 0:
                    live.pop(x)
            free = set(range(R)) - set(live.values())
            if not free:
                return None
            d = min(free)
            p.append([g[vals[i]][0], ai, bi, d])
            if rem[i]:
                live[i] = d
        replay(row, p)
        return p
    candidates = [roots, roots[::-1], sorted(roots, key=lambda i: cl[i].bit_count()), sorted(roots, key=lambda i: -cl[i].bit_count())]
    bestkey = None
    bestroots = None
    bestmode = 0
    attempt = 0
    for rr in candidates:
        for m in range(4):
            o = order(rr, m)
            key = assess(o)
            attempt += 1
            if key[0] == 0:
                return (emit(o), {'nodes': N, 'tries': attempt, 'peak': key[1]})
            if bestkey is None or key < bestkey:
                bestkey = key
                bestroots = rr[:]
                bestmode = m
    if len(roots) < 2:
        return (best, {'nodes': N, 'tries': attempt, 'peak': bestkey[1]})
    cur = bestkey
    rr = bestroots[:]
    m = bestmode
    for k in range(steps):
        if k % 45 == 0:
            rr = bestroots[:]
            m = bestmode
            cur = bestkey
        trial = rr[:]
        a, b = rng.sample(range(len(rr)), 2)
        if k % 3:
            trial[a], trial[b] = (trial[b], trial[a])
        else:
            trial.insert(b, trial.pop(a))
        mm = rng.randrange(4) if k % 7 == 0 else m
        o = order(trial, mm)
        key = assess(o)
        attempt += 1
        if key[0] == 0:
            return (emit(o), {'nodes': N, 'tries': attempt, 'peak': key[1]})
        if key < bestkey:
            bestkey = key
            bestroots = trial[:]
            bestmode = mm
        delta = key[0] - cur[0] + 0.1 * (key[1] - cur[1]) + 0.0005 * (key[2] - cur[2])
        temp = 2 * (1 - k % 45 / 45) + 0.05
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            rr = trial
            m = mm
            cur = key
    return (best, {'nodes': N, 'tries': attempt, 'peak': bestkey[1]})
