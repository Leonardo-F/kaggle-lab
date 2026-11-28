"""Current independent solver: graph portfolio and shared-basis portfolio."""
from .basis import search_basis
from .portfolio import search_graphs
from .common import replay

SOLVER_VERSION = "v11"
ROUTES = {"r8": search_graphs, "basis": search_basis}


def solve_group(group, row):
    result = ROUTES[group](row)
    if not result["programs"] or any(replay(row, p) != result["scores"][k]
                                    for k, p in result["programs"].items()):
        raise ValueError(f"invalid candidate group: {group}")
    return result


def choose(row, results):
    candidates = {f"{group}/{name}": program for group in ROUTES
                  for name, program in results[group]["programs"].items()}
    scores = {name: replay(row, program) for name, program in candidates.items()}
    winner = min(scores, key=scores.get)
    return row["id"], candidates[winner], {"winner": winner, "scores": scores}


def solve(row, config=None, version=None):
    if config or version not in (None, SOLVER_VERSION):
        raise ValueError("Only the current frozen search configuration is supported")
    return choose(row, {group: solve_group(group, row) for group in ROUTES})
