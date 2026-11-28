"""Independent candidate generation and evaluation."""
import time
from .construct import native, puzzle_data, union_data, synthesis_data
from .schedule import compile_candidate
from .schedule_local import schedule_local
from .optimize import optimize

ROUTES = [("order", 6, 3), ("factor", 6, 3), ("bilayer", 6, 3), ("congruence/congruence", 6, 3)]

def search_graphs(row):
    st = time.monotonic()
    data = puzzle_data(row)
    gs = []
    programs = {}
    nodes = {}
    errors = {}
    stats = {}
    graphs = {}

    def evaluate(name, g):
        p, n = compile_candidate(row, g)
        programs[name] = p
        nodes[name] = n
        graphs[name] = g
    for exe, w, m in ROUTES:
        try:
            g, _ = native(exe, [w, m], data)
            evaluate(exe, g)
            gs.append(g)
        except Exception as e:
            errors[exe] = repr(e)
    if not gs:
        raise ValueError('no fresh graph')
    inp = union_data(row, gs)
    for name, exe, h in [('union', 'hyper', 0)]:
        try:
            g, info = native(exe, [h, 8], inp)
            evaluate(name, g)
            stats[name] = info
        except Exception as e:
            errors[name] = repr(e)
    base = min(programs, key=lambda k: len(programs[k]))
    try:
        g, info = optimize(row, list(graphs.values()), graphs[base], seconds=0.7)
        evaluate('milp', g)
        stats['milp'] = info
    except Exception as e:
        errors['milp'] = repr(e)
    baseline = min(programs, key=lambda k: len(programs[k]))
    seed = graphs[baseline]
    for mode in (2, 3):
        try:
            inp = synthesis_data(row, seed)
            g, info = native('synth', [mode], inp)
            evaluate(f'synth{mode}', g)
            stats[f'synth{mode}'] = info
        except Exception as e:
            errors[f'synth{mode}'] = repr(e)
    base8 = min(programs, key=lambda k: len(programs[k]))
    for name in list(programs):
        if len(programs[name]) <= len(programs[base8]) + 12 and len(programs[name]) > nodes[name]:
            try:
                p, info = schedule_local(row, graphs[name], programs[name])
                stats['sched8_' + name] = info
                if len(p) < len(programs[name]):
                    programs['sched8_' + name] = p
                    nodes['sched8_' + name] = nodes[name]
                    graphs['sched8_' + name] = graphs[name]
            except Exception as e:
                errors['sched8_' + name] = repr(e)
    scores = {k: len(v) for k, v in programs.items()}
    winner = min(scores, key=scores.get)
    return dict(id=row['id'], scores=scores, nodes=nodes, errors=errors, stats=stats, programs=programs, winner=winner, score=scores[winner], seconds=round(time.monotonic() - st, 3))
