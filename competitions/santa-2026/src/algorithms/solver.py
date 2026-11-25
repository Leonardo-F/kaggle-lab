"""The single public Santa 2026 solver: frozen V9 pipeline.

The pipeline is orchestrated here in the exact order of the frozen V9 Stage 2
candidate.  Every candidate is freshly constructed from the puzzle row:

1. four native-constructor routes (two kernels x widths/modes 6:3 and 6:4),
   each compiled with the eight-order Stage 1 compiler, optionally after two
   polish sweeps; the shortest legal route becomes the Stage 1 program;
2. a first-occurrence DAG is extracted from that program and the frozen
   register-pressure scheduler searches alternative schedules with actual
   replay, keeping only strictly shorter programs.

Stage metric keys are ``v9_stage1`` and ``v9final``; per-route scores and node
counts are retained for reproducibility checks.  No stage reads a historical
answer, submission CSV or research checkpoint.
"""

import json

from .common import replay
from .construct import construct
from .graph import extract
from .rewrite import polish
from .schedule import compile_graph, schedule

SOLVER_VERSION = "v9"

DEFAULT_CONFIG = {
    "stage1_routes": (
        ("constructor_wide_polish", 6, 3),
        ("constructor_wide_polish", 6, 4),
        ("constructor_mitm_polish", 6, 3),
        ("constructor_mitm_polish", 6, 4),
    ),
    "compile_tries": 8,
    "compile_seed": 919,
    "polish_rounds": 2,
    "schedule_seed": 202609,
    "schedule_tries": 32,
    "schedule_top": 12,
    "schedule_modes": 6,
}

STAGES = ("v9_stage1", "v9final")


def _resolve_config(config):
    cfg = dict(DEFAULT_CONFIG)
    if config is not None:
        unknown = set(config) - set(cfg)
        if unknown:
            raise ValueError(f"unknown solver configuration: {sorted(unknown)}")
        cfg.update(config)
    routes = []
    for route in cfg["stage1_routes"]:
        if len(route) != 3:
            raise ValueError(f"invalid stage 1 route: {route!r}")
        name, width, mode = route
        if type(name) is not str or not name.endswith("_polish"):
            raise ValueError(f"invalid stage 1 route name: {name!r}")
        routes.append((name, int(width), int(mode)))
    cfg["stage1_routes"] = tuple(routes)
    for key in ("compile_tries", "polish_rounds", "schedule_tries", "schedule_top", "schedule_modes"):
        if type(cfg[key]) is not int or cfg[key] < 0:
            raise ValueError(f"invalid solver configuration {key}: {cfg[key]!r}")
    for key in ("compile_seed", "schedule_seed"):
        if type(cfg[key]) is not int:
            raise ValueError(f"invalid solver configuration {key}: {cfg[key]!r}")
    return cfg


def _stage1(row, cfg):
    """Run the four frozen construction routes; return the shortest and metrics."""
    best = None
    routes = []
    starting = json.loads(row['starting_values'])
    targets = json.loads(row['targets'])
    limit = int(row['value_limit'])
    for route in cfg["stage1_routes"]:
        name, width, mode = route
        entry = {"config": [name, width, mode], "nodes": None, "score": None, "error": None}
        try:
            kernel = name.removesuffix("_polish")
            graph = construct(row, width, mode, kernel)
            program, nodes = compile_graph(row, graph, tries=cfg["compile_tries"],
                                           seed=cfg["compile_seed"])
            if name.endswith("_polish"):
                polished, _ = polish(graph, starting, targets, limit,
                                     rounds=cfg["polish_rounds"])
                polished_program, polished_nodes = compile_graph(
                    row, polished, tries=cfg["compile_tries"], seed=cfg["compile_seed"])
                if len(polished_program) < len(program):
                    program, nodes = polished_program, polished_nodes
            score = replay(row, program)
            entry["nodes"] = nodes
            entry["score"] = score
            if best is None or len(program) < len(best):
                best = program
        except Exception as exc:  # the frozen runner records failing routes and continues
            entry["error"] = f"{type(exc).__name__}: {exc}"
        routes.append(entry)
    if best is None:
        detail = '; '.join(entry["error"] or 'invalid candidate' for entry in routes)
        raise RuntimeError(f"{row['id']}: no legal candidate from any frozen route ({detail})")
    return best, routes


def solve(row, config=None):
    """Solve one puzzle from the official row and return ``(id, program, metrics)``."""
    cfg = _resolve_config(config)
    stage1_program, routes = _stage1(row, cfg)
    stage1_score = len(stage1_program)
    graph = extract(row, stage1_program)
    program, info = schedule(
        row, graph, stage1_program,
        tries=cfg["schedule_tries"], top=cfg["schedule_top"],
        modes=cfg["schedule_modes"], seed=cfg["schedule_seed"],
    )
    final_score = replay(row, program)
    metrics = {
        "v9_stage1": stage1_score,
        "v9final": final_score,
        "routes": routes,
        "nodes": info["nodes"],
        "schedule_attempts": info["attempts"],
    }
    return row["id"], program, metrics
