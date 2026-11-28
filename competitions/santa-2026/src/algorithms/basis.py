"""Independent candidate generation and evaluation."""
import time
from .construct import native, puzzle_data, synthesis_data
from .schedule import compile_candidate

def search_basis(row):
    st = time.monotonic()
    data = puzzle_data(row)
    g, _ = native('order', [6, 3], data)
    ps = {}
    nodes = {}
    stats = {}

    def evaluate(k, g):
        p, n = compile_candidate(row, g, local_search=True)
        ps[k] = p
        nodes[k] = n
    evaluate('order', g)
    h, info = native('variants/basis12free/basis', [6, 3], data)
    evaluate('basis', h)
    stats['basis'] = info
    inp = synthesis_data(row, h)
    for k, exe, m in [('basis3', 'synth', 3), ('basis4', 'variants/synth9/synth9', 4)]:
        hh, info = native(exe, [m], inp)
        evaluate(k, hh)
        stats[k] = info
    scores = {k: len(v) for k, v in ps.items()}
    return dict(id=row['id'], scores=scores, programs=ps, nodes=nodes, stats=stats, seconds=round(time.monotonic() - st, 3))
