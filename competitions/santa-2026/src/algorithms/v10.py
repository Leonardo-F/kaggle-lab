"""V10 Full: seven native constructors, joint scheduling and exact repair.

This module is the production port of the frozen V10 research pipeline.  It
keeps the research route order, candidate order, seeds, tie handling, native
timeouts and search budgets unchanged.  Every candidate is built from the
official puzzle row in the current call; no archived program, submission CSV
or research checkpoint is read as a solver input.

The pipeline has three observable stages:

``v10_stage1``
    The best value DAG compiled from the four frozen Stage 1 routes
    (``constructor_wide`` / ``constructor_mitm`` at widths 6:3 and 6:4, each
    raw and after two polish sweeps), before register scheduling.  This is the
    V10 ablation's "Stage 1" number.

``v10_stage3``
    The V10.1 joint portfolio re-schedules every distinct route DAG instead of
    discarding the losing routes, adds the pressure-guided constructor at 6:3
    and 6:4, then runs the exact pressure-guided DAG repair and the two joint
    routes (``constructor_joint`` and ``constructor_cf``).  The shortest
    replayed candidate is retained.

``v10final``
    The selected policy adds the target-order routes.  The default policy,
    ``full``, tries both ``constructor_order_fast`` and
    ``constructor_order_cf`` and keeps the shortest legal candidate.
"""

import json
import statistics
from collections import Counter, defaultdict

from .common import arithmetic, replay
from .construct import construct
from .graph import extract
from .rewrite import inverses, polish
from .schedule import compile_graph, schedule

SOLVER_VERSION = "v10"

# Four frozen Stage 1 routes, in the exact research order.
STAGE1_ROUTES = (
    ("constructor_wide_polish", 6, 3),
    ("constructor_wide_polish", 6, 4),
    ("constructor_mitm_polish", 6, 3),
    ("constructor_mitm_polish", 6, 4),
)

# The two routes that turn Stage 3 into the full policy.
ORDER_ROUTES = ("constructor_order_fast", "constructor_order_cf")

# The two joint routes already used by Stage 3.
JOINT_ROUTES = ("constructor_joint", "constructor_cf")

POLICIES = ("stage3", "order", "hybrid", "full", "adaptive")

DEFAULT_CONFIG = {
    "stage1_routes": STAGE1_ROUTES,
    "compile_tries": 8,
    "compile_seed": 919,
    "polish_rounds": 2,
    "schedule_seed": 202609,
    "schedule_tries": 32,
    "schedule_top": 12,
    "schedule_modes": 6,
    "pressure_modes": (3, 4),
    "stage1_timeout": 45,
    "extra_timeout": 18,
    "repair_rounds": 2,
    "repair_budget": 8,
    "policy": "full",
}

STAGES = ("v10_stage1", "v10_stage3", "v10final")

_INT_KEYS = (
    "compile_tries", "compile_seed", "polish_rounds", "schedule_seed",
    "schedule_tries", "schedule_top", "schedule_modes", "stage1_timeout",
    "extra_timeout", "repair_rounds", "repair_budget",
)


def _resolve_config(config):
    """Validate and normalise the frozen V10 parameters."""
    cfg = dict(DEFAULT_CONFIG)
    if config is not None:
        unknown = set(config) - set(cfg)
        if unknown:
            raise ValueError(f"unknown V10 solver configuration: {sorted(unknown)}")
        cfg.update(config)
    routes = []
    for route in cfg["stage1_routes"]:
        if len(route) != 3:
            raise ValueError(f"invalid V10 Stage 1 route: {route!r}")
        name, width, mode = route
        if type(name) is not str or not name.endswith("_polish"):
            raise ValueError(f"invalid V10 Stage 1 route name: {name!r}")
        routes.append((name, int(width), int(mode)))
    cfg["stage1_routes"] = tuple(routes)
    for key in _INT_KEYS:
        if type(cfg[key]) is not int or cfg[key] < 0:
            raise ValueError(f"invalid V10 solver configuration {key}: {cfg[key]!r}")
    modes = cfg["pressure_modes"]
    if (not isinstance(modes, (tuple, list)) or len(modes) != 2
            or any(type(mode) is not int or mode < 0 for mode in modes)):
        raise ValueError(f"invalid V10 pressure modes: {modes!r}")
    cfg["pressure_modes"] = tuple(modes)
    if cfg["policy"] not in POLICIES:
        raise ValueError(f"invalid V10 policy: {cfg['policy']!r}")
    return cfg


def _compile(row, graph, cfg):
    return compile_graph(row, graph, tries=cfg["compile_tries"], seed=cfg["compile_seed"])


def _schedule(row, program, cfg, tries=None):
    return schedule(
        row, extract(row, program), program,
        tries=cfg["schedule_tries"] if tries is None else tries,
        top=cfg["schedule_top"], modes=cfg["schedule_modes"],
        seed=cfg["schedule_seed"],
    )


def _route(row, kernel, cfg, timeout):
    """Native candidate -> Stage 1 compiler -> register scheduler."""
    graph = construct(row, 6, 3, kernel, timeout=timeout)
    program, nodes = _compile(row, graph, cfg)
    program, info = _schedule(row, program, cfg)
    return {
        "score": replay(row, program),
        "nodes": nodes,
        "schedule_attempts": info["attempts"],
        "program": program,
    }


def _joint_portfolio(row, cfg):
    """V10.1: compare every route DAG after register scheduling."""
    starting = json.loads(row["starting_values"])
    targets = json.loads(row["targets"])
    limit = int(row["value_limit"])
    candidates = []
    routes = []
    base = None
    for name, width, mode in cfg["stage1_routes"]:
        label = f"{name}:{width}:{mode}"
        graph = construct(row, width, mode, name.removesuffix("_polish"),
                          timeout=cfg["stage1_timeout"])
        raw_program, raw_nodes = _compile(row, graph, cfg)
        raw = (label + ":raw", raw_program, raw_nodes)
        polished, _ = polish(graph, starting, targets, limit,
                             rounds=cfg["polish_rounds"])
        polish_program, polish_nodes = _compile(row, polished, cfg)
        polished_entry = (label + ":polish", polish_program, polish_nodes)
        candidates.extend((raw, polished_entry))
        route = polished_entry if len(polish_program) < len(raw_program) else raw
        routes.append({
            "label": label,
            "raw": len(raw_program),
            "polish": len(polish_program),
            "raw_nodes": raw_nodes,
            "polish_nodes": polish_nodes,
        })
        if base is None or len(route[1]) < len(base[1]):
            base = route

    base_label, base_program, base_nodes = base
    v9_program, v9_info = _schedule(row, base_program, cfg)
    replay(row, v9_program)
    best = v9_program
    winner = base_label
    scheduled = []
    seen = {tuple(sorted(extract(row, base_program).items()))}
    for label, program, nodes in sorted(candidates, key=lambda item: (item[2], len(item[1]))):
        if label == base_label:
            continue
        # A fixed candidate's node count is a lower bound only for that candidate.
        if nodes >= len(best):
            continue
        graph = extract(row, program)
        key = tuple(sorted(graph.items()))
        if key in seen:
            continue
        seen.add(key)
        candidate, info = schedule(row, graph, program, tries=cfg["schedule_tries"])
        replay(row, candidate)
        scheduled.append({
            "label": label,
            "initial": len(program),
            "nodes": info["nodes"],
            "score": len(candidate),
            "attempts": info["attempts"],
        })
        if len(candidate) < len(best):
            best = candidate
            winner = label
    return {
        "stage1": len(base_program),
        "base_nodes": base_nodes,
        "v9": len(v9_program),
        "v9_attempts": v9_info["attempts"],
        "program": best,
        "score": replay(row, best),
        "winner": winner,
        "routes": routes,
        "scheduled": scheduled,
    }


def _pressure_portfolio(row, cfg):
    """V10's pressure-guided constructor over the joint portfolio."""
    result = _joint_portfolio(row, cfg)
    best = result["program"]
    extra = []
    starting = json.loads(row["starting_values"])
    targets = json.loads(row["targets"])
    limit = int(row["value_limit"])
    for mode in cfg["pressure_modes"]:
        try:
            graph = construct(row, 6, mode, "constructor_pressure",
                              timeout=cfg["stage1_timeout"])
            polished, _ = polish(graph, starting, targets, limit,
                                 rounds=cfg["polish_rounds"])
            for kind, candidate_graph in (("raw", graph), ("polish", polished)):
                program, _ = _compile(row, candidate_graph, cfg)
                program, info = _schedule(row, program, cfg)
                replay(row, program)
                extra.append({
                    "mode": mode,
                    "kind": kind,
                    "score": len(program),
                    "nodes": info["nodes"],
                })
                if len(program) < len(best):
                    best = program
                    result["winner"] = f"pressure:{mode}:{kind}"
        except (ValueError, KeyError, RuntimeError, RecursionError) as exc:
            extra.append({"mode": mode, "error": str(exc)})
    result.update(pressure=extra, program=best, score=replay(row, best))
    return result


def _repair_stats(graph, start, targets, registers):
    """Closure, live pressure triple and active node count of a fixed DAG."""
    closure = {v: frozenset() for v in start}
    visiting = set()
    order = []

    def walk(value):
        if value not in closure:
            if value in visiting:
                raise ValueError("cycle")
            visiting.add(value)
            _, a, b = graph[value]
            closure[value] = walk(a) | walk(b) | {value}
            visiting.remove(value)
            order.append(value)
        return closure[value]

    for target in targets:
        walk(target)
    active = set(order)
    graph = {v: graph[v] for v in order}
    deps = {v: set(graph[v][1:]) for v in order}
    last = {x: i for i, v in enumerate(order) for x in deps[v]}
    live = set(start)
    excess = area = peak = 0
    for i, value in enumerate(order):
        for x in deps[value]:
            if x not in start and last[x] == i:
                live.discard(x)
        if last.get(value, -1) > i:
            live.add(value)
        size = len(live)
        excess += max(0, size - registers)
        area += size
        peak = max(peak, size)
    return graph, len(active), excess, peak, area


def _repair(row, program, cfg):
    """V10.2 pressure-guided exact DAG repair (two rounds, budget eight)."""
    best = program
    history = []
    limit = int(row["value_limit"])
    registers = int(row["registers"])
    start = set(json.loads(row["starting_values"]))
    targets = list(dict.fromkeys(json.loads(row["targets"])))
    attempts = 0
    for round_index in range(cfg["repair_rounds"]):
        graph = extract(row, best)
        # Active closure, repeated-value counts and target set.
        closure = {v: frozenset() for v in start}

        def visit(value):
            if value not in closure:
                _, a, b = graph[value]
                closure[value] = visit(a) | visit(b) | {value}
            return closure[value]

        active = set().union(*(visit(target) for target in targets))
        graph = {v: graph[v] for v in active}
        registers_state = dict(enumerate(json.loads(row["starting_values"])))
        count = Counter()
        for op, left, right, destination in best:
            value = arithmetic(op, registers_state[left], registers_state[right])
            registers_state[destination] = value
            count[value] += 1
        _, _, old_excess, old_peak, _ = _repair_stats(graph, start, targets, registers)
        values = sorted(set(graph) | start)
        users = defaultdict(set)
        for value, (_, a, b) in graph.items():
            users[a].add(value)
            users[b].add(value)
        rank = sorted(graph, key=lambda value: (
            -(max(0, count[value] - 1) * (1 + len(closure[value]))
              + sum(max(0, count[a] - 1) * (1 + len(closure[a]))
                    for a in set(graph[value][1:]))),
            -len(closure[value]), value))
        selected = rank[:16]
        patches = []
        seen = set()
        for value in selected:
            for a in values:
                if value == a or value in closure[a]:
                    continue
                for b, expression in inverses(value, a, limit):
                    if b not in closure or b == value or value in closure[b] or expression == graph[value]:
                        continue
                    if expression[0] in "+*" and expression[1] > expression[2]:
                        expression = (expression[0], expression[2], expression[1])
                    key = (value, expression)
                    if key in seen:
                        continue
                    seen.add(key)
                    if len(closure[a] | closure[b]) > len(closure[value]) + 16:
                        continue
                    patch = graph.copy()
                    patch[value] = expression
                    try:
                        _, nodes, excess, peak, area = _repair_stats(
                            patch, start, targets, registers)
                    except (ValueError, KeyError, RecursionError):
                        continue
                    if nodes >= len(best):
                        continue
                    # The proxy only ranks patches; acceptance is an exact replay.
                    proxy = nodes + 0.08 * excess + 0.004 * area
                    patches.append((proxy, nodes, excess, peak, area,
                                    value, expression, patch))
        if not patches:
            break
        trials = Counter()
        before = len(best)
        accepted = None
        for proxy, nodes, excess, peak, area, value, expression, patch in sorted(
                patches, key=lambda item: item[:7]):
            if trials[value] >= 2 or nodes >= len(best):
                continue
            trials[value] += 1
            attempts += 1
            try:
                candidate, _ = compile_graph(row, patch, tries=4)
                if len(candidate) < len(best):
                    replay(row, candidate)
                    best = candidate
                    accepted = (value, expression, nodes, excess)
                candidate, _ = schedule(row, patch, candidate, tries=16)
                replay(row, candidate)
                if len(candidate) < len(best):
                    best = candidate
                    accepted = (value, expression, nodes, excess)
            except (ValueError, KeyError, RecursionError):
                pass
            if sum(trials.values()) >= cfg["repair_budget"]:
                break
        history.append({
            "round": round_index,
            "patches": len(patches),
            "before": before,
            "after": len(best),
            "unlimited_peak_before": old_peak,
            "unlimited_excess_before": old_excess,
            "accepted": accepted,
        })
        if len(best) == before:
            break
    return best, history, attempts


def _stage3(row, cfg):
    """Joint/pressure portfolio + exact repair + the two joint native routes."""
    result = _pressure_portfolio(row, cfg)
    route_stage1 = result["stage1"]
    result["stage3_pre_repair"] = result["score"]
    repaired, history, attempts = _repair(row, result["program"], cfg)
    result.update(
        stage1=len(repaired),
        route_stage1=route_stage1,
        program=repaired,
        score=replay(row, repaired),
        repair=history,
        repair_attempts=attempts,
    )
    best = result["program"]
    winner = "stage1"
    candidates = {}
    errors = {}
    for kernel in JOINT_ROUTES:
        try:
            route = _route(row, kernel, cfg, cfg["extra_timeout"])
            candidates[kernel] = route
            if len(route["program"]) < len(best):
                best = route["program"]
                winner = kernel
        except Exception as exc:  # the frozen runner records failing routes and continues
            errors[kernel] = f"{type(exc).__name__}: {exc}"
    result.update(
        stage3=replay(row, best),
        stage3_program=best,
        stage3_winner=winner,
        joint_candidates=candidates,
        joint_errors=errors,
    )
    return result


def _policy_selection(row, stage3, order_candidates, policy):
    """Apply one frozen policy to a finished Stage 3 and its order candidates."""
    programs = {"stage3": stage3}
    for kernel, route in order_candidates.items():
        programs[kernel] = route["program"]
    if policy == "stage3":
        extras = []
    elif policy == "order":
        extras = [ORDER_ROUTES[0]]
    elif policy == "hybrid":
        extras = [ORDER_ROUTES[1]]
    elif policy == "full":
        extras = list(ORDER_ROUTES)
    else:
        bits = statistics.median(value.bit_length()
                                 for value in json.loads(row["targets"]))
        extras = ([ORDER_ROUTES[0]] if 20 <= bits < 60 else [])
        extras += [ORDER_ROUTES[1]] if 40 <= bits < 60 else []
    eligible = ["stage3"] + [name for name in extras if name in programs]
    winner = min(eligible, key=lambda name: len(programs[name]))
    return programs[winner], winner, extras


def solve(row, config=None):
    """Solve one puzzle from its official row and return ``(id, program, metrics)``."""
    cfg = _resolve_config(config)
    result = _stage3(row, cfg)
    order_candidates = {}
    order_errors = {}
    for kernel in ORDER_ROUTES:
        try:
            order_candidates[kernel] = _route(row, kernel, cfg, cfg["extra_timeout"])
        except Exception as exc:  # the frozen runner records failing routes and continues
            order_errors[kernel] = f"{type(exc).__name__}: {exc}"

    policies = {}
    for policy in POLICIES:
        program, winner, extras = _policy_selection(
            row, result["stage3_program"], order_candidates, policy)
        policies[policy] = {
            "winner": winner,
            "score": replay(row, program),
            "extras": extras,
            "program": program,
        }
    selected = policies[cfg["policy"]]
    program = selected["program"]
    metrics = {
        "v10_stage1": result["stage1"],
        "v9": result["v9"],
        "v10_stage3": result["stage3"],
        "v10final": len(program),
        "policy": cfg["policy"],
        "winner": selected["winner"],
        "stage3_winner": result["stage3_winner"],
        "routes": result["routes"],
        "scheduled": result["scheduled"],
        "pressure": result["pressure"],
        "repair": result["repair"],
        "repair_attempts": result["repair_attempts"],
        "joint_candidates": {
            name: {key: value for key, value in route.items() if key != "program"}
            for name, route in result["joint_candidates"].items()
        },
        "joint_errors": result["joint_errors"],
        "order_candidates": {
            name: {key: value for key, value in route.items() if key != "program"}
            for name, route in order_candidates.items()
        },
        "order_errors": order_errors,
        "policies": {
            name: {"winner": entry["winner"], "score": entry["score"], "extras": entry["extras"]}
            for name, entry in policies.items()
        },
        "nodes": result["base_nodes"],
        "schedule_attempts": result["v9_attempts"],
    }
    return row["id"], program, metrics
