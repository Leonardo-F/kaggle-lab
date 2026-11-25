"""The single public Santa 2026 solver: V8 Final equivalent pipeline.

The pipeline is orchestrated here in the exact order of the frozen V8 code.
Construction, graph fusion, graph compilation and rewriting remain interleaved:
the V7 baseline is regenerated in-process, then compiled, rewritten, repaired
and finally rescheduled.  No stage reads a historical answer or submission.

Stage metric keys (``v7`` ... ``v8final``) are kept for compatibility with the
existing reports and checkpoint consumers.
"""

import json

from .common import replay
from .construct import adaptive_base, adaptive_v4, adaptive_v5, plans
from .graph import extract, global_select, joint_polish, path_union
from .rewrite import cut_repair, rewrite, three
from .schedule import compile_graph, schedule_v7, schedule_v8
from .common import sparse

SOLVER_VERSION = "v8"

DEFAULT_CONFIG = {
    # V6 baseline search
    "v6_rounds": 180,
    "v6_extra": True,
    # V7 portfolio and fusion
    "v7_portfolio": 3,
    "v7_path_rounds": 400,
    "v7_schedule": True,
    "v7_retain_v6_graphs": False,
    # V8 rewriting
    "rewrite_sweeps": 2,
    "three_sweeps": 2,
    "three_budget": 10,
    # V8 grouped repair and final scheduling
    "group_strict_rounds": 6,
    "group_neutral_rounds": 8,
    "group_beam": 10,
    "schedule_tries": 32,
}

STAGES = ("v7", "list_schedule", "v8", "v81", "v82",
          "v8group_strict", "v8group_neutral", "v8final")


def _resolve_config(config):
    cfg = dict(DEFAULT_CONFIG)
    if config is not None:
        unknown = set(config) - set(cfg)
        if unknown:
            raise ValueError(f"unknown solver configuration: {sorted(unknown)}")
        cfg.update(config)
    return cfg


def _solve_v3_base(row, thorough=True):
    """Radix portfolio plus the early adaptive and joint-polish stages."""
    s = json.loads(row['starting_values'])
    ts = json.loads(row['targets'])
    L = int(row['value_limit'])
    best = None
    method = None

    def consider(result, name):
        nonlocal best, method
        if result is not None:
            p = result[2]
            if best is None or len(p) < len(best):
                replay(row, p)
                best = p
                method = name

    for b, d in [(2, 2), (16, 8), (64, 8), (128, 16), (256, 16), (512, 16),
                 (1024, 32), (2048, 32), (4096, 32), (4096, 64), (8192, 64),
                 (16384, 64), (32768, 128), (65536, 256), (1000, 10), (10000, 100)]:
        for rev in (False, True):
            try:
                consider(sparse(s, ts, L, b, d, rev), f'radix-{b}-{d}-{int(rev)}')
            except (ValueError, AssertionError, KeyError, RecursionError):
                pass
    if best is None:
        raise RuntimeError('no valid candidate: ' + row['id'])
    if thorough and len(best) > len(set(ts) - set(s)):
        try:
            consider(adaptive_base(s, ts, L, 0), 'adaptive-0')
        except (ValueError, AssertionError, KeyError, RecursionError):
            pass
    baseline = len(best)
    if thorough and len(best) > len(set(ts) - set(s)):
        try:
            consider(adaptive_base(s, list(reversed(ts)), L, 1, 3, True), 'adaptive-wide-reverse')
        except (ValueError, AssertionError, KeyError, RecursionError):
            pass
    before_joint = len(best)
    if thorough and len(best) > len(set(ts) - set(s)):
        try:
            new = joint_polish(row, best)
            if len(new) < len(best):
                replay(row, new)
                best = new
                method += ' + joint'
        except (ValueError, AssertionError, KeyError, RecursionError):
            pass
    return row['id'], best, method, baseline, before_joint


def _solve_v3(row, thorough=True):
    """Bidirectional construction and fusion-LNS on top of the V3 baseline."""
    pid, best, method, _, _ = _solve_v3_base(row, thorough)
    v2 = len(best)
    s = json.loads(row['starting_values'])
    ts = json.loads(row['targets'])
    L = int(row['value_limit'])
    alt = None
    if thorough and len(best) > len(set(ts) - set(s)):
        try:
            alt = adaptive_base(s, sorted(ts, reverse=True), L, 2, 3, True, True)[2]
            replay(row, alt)
        except (ValueError, AssertionError, KeyError, RecursionError):
            alt = None
    previous = best
    if alt is not None and len(alt) < len(best):
        best = alt
        method = 'bidirectional'
    bidir = len(best)
    if thorough and len(best) > len(set(ts) - set(s)):
        try:
            other = previous if best is alt else alt
            new = joint_polish(row, best, other, rounds=100)
            if len(new) < len(best):
                replay(row, new)
                best = new
                method += ' + fusion-LNS'
        except (ValueError, AssertionError, KeyError, RecursionError):
            pass
    return pid, best, method, v2, bidir


def _solve_v4(row, full=True):
    """Quotient-neighbour construction on top of the V3 baseline."""
    s = json.loads(row['starting_values'])
    ts = json.loads(row['targets'])
    L = int(row['value_limit'])
    if full:
        pid, best, method, _, _ = _solve_v3(row)
    else:
        pid, best, method, _, _ = _solve_v3_base(row, True)
    baseline = len(best)
    if baseline == len(set(ts) - set(s)):
        return pid, best, method, baseline, baseline, False
    try:
        alt = adaptive_v4(s, sorted(ts, reverse=True), L)[2]
        replay(row, alt)
    except (ValueError, AssertionError, KeyError, RecursionError):
        return pid, best, method, baseline, baseline, False
    raw = len(alt)
    if raw < len(best):
        best, alt = alt, best
        method = 'v4-mitm'
    try:
        new = joint_polish(row, best, alt, rounds=100)
        if len(new) < len(best):
            replay(row, new)
            best = new
            method += ' + v4-fusion'
    except (ValueError, AssertionError, KeyError, RecursionError):
        pass
    return pid, best, method, baseline, raw, True


def _solve_v5(row, full=True, modular=True):
    """Product pool and modular-residue construction on top of V4."""
    s = json.loads(row['starting_values'])
    ts = json.loads(row['targets'])
    L = int(row['value_limit'])
    pid, best, method, _, _, _ = _solve_v4(row, full)
    baseline = len(best)
    raw = None
    selected = baseline
    if baseline == len(set(ts) - set(s)):
        return pid, best, method, baseline, raw, selected, len(best)
    try:
        alt = adaptive_v5(s, sorted(ts, reverse=True), L, products=True, modular=modular)[2]
        replay(row, alt)
        raw = len(alt)
        if raw < len(best):
            best, alt = alt, best
            method = 'v5-product-residue'
        selected = len(best)
        new = joint_polish(row, best, alt, rounds=100)
        if len(new) < len(best):
            replay(row, new)
            best = new
            method += ' + v5-fusion'
    except (ValueError, AssertionError, KeyError, RecursionError):
        pass
    return pid, best, method, baseline, raw, selected, len(best)


def _solve_v6(row, cfg, trace=False):
    """Dynamic acyclic selection, an extra constructor and path union."""
    rounds = cfg["v6_rounds"]
    extra = cfg["v6_extra"]
    pid, baseline, *_ = _solve_v5(row, True, True)
    s = json.loads(row['starting_values'])
    ts = json.loads(row['targets'])
    L = int(row['value_limit'])
    if len(baseline) == len(set(ts) - set(s)):
        metrics = {'v5': len(baseline), 'single': len(baseline), 'alternate': None,
                   'pre_path': len(baseline), 'v6': len(baseline)}
        return (pid, baseline, metrics, [baseline]) if trace else (pid, baseline, metrics)
    best = global_select(row, baseline, rounds=rounds)
    single = len(best)
    candidates = [baseline, best]
    alt = None
    raw = None
    if extra:
        try:
            alt = adaptive_v5(s, sorted(ts), L, seed=4)[2]
            replay(row, alt)
            raw = len(alt)
        except (ValueError, AssertionError, KeyError, RecursionError):
            alt = None
        if alt is not None:
            candidates.append(alt)
            if len(alt) < len(best):
                best, alt = alt, best
            new = global_select(row, best, alt, rounds=rounds)
            if len(new) < len(best):
                best = new
    pre_path = len(best)
    candidates.append(best)
    new = path_union(row, candidates, rounds=300)
    if len(new) < len(best):
        best = new
    replay(row, best)
    metrics = {'v5': len(baseline), 'single': single, 'alternate': raw,
               'pre_path': pre_path, 'v6': len(best)}
    return (pid, best, metrics, candidates) if trace else (pid, best, metrics)


def _solve_v7(row, cfg):
    """Feature-adaptive portfolio, multi-graph path union and scheduling."""
    pid, base, _, extra_graphs = _solve_v6(row, cfg, trace=True)
    s = json.loads(row['starting_values'])
    ts = json.loads(row['targets'])
    L = int(row['value_limit'])
    best = base
    graphs = [base]
    raw = {}
    failed = []
    if len(base) > len(set(ts) - set(s)):
        for name, order, seed, width in list(plans(s, ts))[:cfg["v7_portfolio"]]:
            try:
                alt = adaptive_v5(s, order, L, seed=seed, width=width)[2]
                replay(row, alt)
                raw[name] = len(alt)
                graphs.append(alt)
                if len(alt) < len(best):
                    best = alt
            except (ValueError, AssertionError, KeyError, RecursionError):
                failed.append(name)
    selected = len(best)
    fused = selected
    if len(graphs) > 1:
        new = path_union(row, graphs, rounds=cfg["v7_path_rounds"])
        if len(new) < len(best):
            best = new
        fused = len(best)
        for alt in sorted(graphs, key=len)[:2]:
            if alt == best:
                continue
            new = global_select(row, best, alt, rounds=120)
            if len(new) < len(best):
                best = new
    polished = len(best)
    if cfg["v7_retain_v6_graphs"] and len(base) > len(set(ts) - set(s)):
        extended = [best] + graphs + extra_graphs
        # Only unique in-memory current-run witnesses, retaining the existing best.
        unique = []
        signatures = set()
        for program in extended:
            signature = tuple(map(tuple, program))
            if signature not in signatures:
                signatures.add(signature)
                unique.append(program)
        if len(unique) > len(graphs):
            new = path_union(row, unique, rounds=cfg["v7_path_rounds"])
            if len(new) < len(best):
                best = new
    retained = len(best)
    if cfg["v7_schedule"]:
        best = schedule_v7(row, best)
    replay(row, best)
    return pid, best, dict(v6=len(base), portfolio=selected, path_union=fused,
                           polished=polished, retained=retained, v7=len(best),
                           candidates=raw, failed=failed)


def _solve_v8_rewrite(row, cfg):
    """V8.0 two-operation rewriting on the V7 programme."""
    pid, base, _ = _solve_v7(row, cfg)
    best = compile_graph(row, extract(row, base), base)
    list_schedule = len(best)
    best, rewrites, novel = rewrite(row, best, cfg["rewrite_sweeps"])
    replay(row, best)
    return pid, best, {'v7': len(base), 'list_schedule': list_schedule,
                       'v8': len(best), 'rewrites': rewrites, 'novel': novel}


def _solve_v8_three(row, cfg):
    """V8.1 three-operation rewriting and equal-cost exploration."""
    pid, base, metrics = _solve_v8_rewrite(row, cfg)
    strict, a, _ = three(row, base, sweeps=cfg["three_sweeps"],
                         budget=cfg["three_budget"], neutral=False)
    neutral, b, c = three(row, strict, sweeps=cfg["three_sweeps"],
                          budget=cfg["three_budget"], neutral=True)
    replay(row, neutral)
    metrics.update(v81=len(strict), v82=len(neutral), three_moves=a,
                   neutral_moves=b, neutral_equal=c)
    return pid, neutral, metrics


def solve(row, config=None):
    """Solve one puzzle from the official row and return (id, program, metrics)."""
    cfg = _resolve_config(config)
    pid, base, metrics = _solve_v8_three(row, cfg)
    strict, a = cut_repair(row, base, rounds=cfg["group_strict_rounds"],
                           neutral=False, beam=cfg["group_beam"])
    mixed, b = cut_repair(row, strict, rounds=cfg["group_neutral_rounds"],
                          neutral=True, beam=cfg["group_beam"])
    best, attempts, gap = schedule_v8(row, mixed, tries=cfg["schedule_tries"])
    replay(row, best)
    metrics.update(v8group_strict=len(strict), v8group_neutral=len(mixed),
                   v8final=len(best),
                   group_moves=a['group_moves'] + b['group_moves'],
                   group_nonimproving=b['group_nonimproving'],
                   group_trials=a['group_trials'] + b['group_trials'],
                   schedule_attempts=attempts, remat_gap=gap)
    return pid, best, metrics
