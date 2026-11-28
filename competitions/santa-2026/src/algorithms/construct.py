"""Protocol for native graph construction and synthesis."""
import json
import subprocess
from .native.build import BUILD_DIR

KERNEL_ALIASES = {"congruence/congruence": "congruence", "variants/basis12free/basis": "basis", "variants/synth9/synth9": "synth_extended"}


def native(exe, args, data):
    binary = BUILD_DIR / KERNEL_ALIASES.get(exe, exe)
    result = subprocess.run([str(binary), *map(str, args)], input=data, text=True,
                            capture_output=True, check=True, timeout=45)
    lines = result.stdout.splitlines()
    graph = {int(v): (op, int(a), int(b)) for v, op, a, b in (line.split() for line in lines[1:])}
    if not lines or len(graph) != int(lines[0]) or len(lines) != len(graph) + 1:
        raise ValueError("invalid native graph protocol")
    return graph, result.stderr.strip()


def puzzle_data(row, graph_count=None):
    """Native header with optional graph/edge count, followed by puzzle values."""
    starts = json.loads(row["starting_values"])
    targets = json.loads(row["targets"])
    fields = [row["value_limit"], len(starts), len(targets)]
    if graph_count is not None:
        fields.append(graph_count)
    return " ".join(map(str, [*fields, *starts, *targets]))


def graph_data(graph):
    return "".join(f"{value} {op} {a} {b}\n" for value, (op, a, b) in graph.items())


def synthesis_data(row, graph):
    return puzzle_data(row, len(graph)) + "\n" + graph_data(graph)


def union_data(row, graphs):
    return puzzle_data(row, len(graphs)) + "\n" + "".join(
        f"{len(graph)}\n" + graph_data(graph) for graph in graphs)
