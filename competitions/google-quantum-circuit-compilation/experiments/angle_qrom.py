"""Benchmark a lossless ANGLE lookup that shares constant subtrees."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import random

import kickmix as km


def build(table, precision, *, prune):
    """Rows are tuples of already-quantized angle words in verifier order."""
    if len(table) < 2:
        raise ValueError('At least two addresses are required')
    addresses = (len(table)-1).bit_length()
    words = len(table[0])
    if not (words and precision >= 1 and addresses + words*precision <= 128):
        raise ValueError('Invalid ANGLE register widths')
    if any(len(row) != words or any(not 0 <= word < 1 << precision for word in row)
           for row in table):
        raise ValueError('Invalid fixed-point words')
    rows = [sum(word << (w*precision) for w,word in enumerate(row)) for row in table]
    rows += [0]*((1 << addresses)-len(rows))
    builder = km.CircuitBuilder()
    selection = builder.create_quantum_register(addresses, 'selection')
    outputs = [q for j in range(words) for q in
               builder.create_quantum_register(precision, f'word_{j}')]
    flags = builder.alloc_qubits(addresses)

    def apply(start, depth, enabled):
        span = 1 << depth
        word = rows[start]
        if depth == 0 or (prune and rows[start:start+span].count(word) == span):
            for bit, wire in enumerate(outputs):
                if word >> bit & 1:
                    builder.cx(enabled, wire)
            return
        select = selection[depth-1]
        flag = flags[depth-1]
        builder.x(select)
        builder.init_and(enabled, select, flag)
        builder.x(select)
        apply(start, depth-1, flag)
        builder.cx(enabled, flag)
        apply(start + span//2, depth-1, flag)
        builder.del_and(enabled, select, flag)

    apply(0, addresses, True)
    circuit = builder.finish_circuit()
    if circuit.num_qubits > 128:
        raise ValueError('Constructed ANGLE circuit exceeds 128 qubits')
    return circuit


def audit(circuit, table, precision, seed):
    """Replay the XOR oracle from zero and nonzero outputs."""
    rng = random.Random(seed)
    width = len(table[0])*precision
    selection_bits = (len(table)-1).bit_length()
    covered = len(table)
    payload = circuit.register_data
    out = [q for i in range(len(table[0])) for q in payload[f'word_{i}']]
    wires = [km.q(i) for i in range(circuit.num_qubits)]
    rng_values = [rng.randrange(1 << width) for _ in table]
    for initial in ([0]*covered, rng_values):
        for first in range(0, covered, 128):
            batch = table[first:first+128]
            simulator = km.Simulator(batch_size=len(batch), seed=rng.getrandbits(63))
            simulator.use_same_registers_as(circuit)
            for shot in range(len(batch)):
                address = first+shot
                simulator.write_within_shot('selection', shot, address)
                simulator.write_within_shot(out, shot, initial[address])
            simulator.do(circuit)
            for shot, row in enumerate(batch):
                address = first+shot
                word = sum(v << (i*precision) for i,v in enumerate(row))
                expected = address | ((word ^ initial[address]) << selection_bits)
                if simulator.read_within_shot(wires, shot, out=int) != expected:
                    raise ValueError(f'Incorrect ANGLE bits or dirty workspace at address {address}')
                if Fraction(simulator.read_shot_phase(shot)) % 2:
                    raise ValueError(f'Nonzero ANGLE phase at address {address}')
    return 2*covered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    seed = 20261120
    precision = 12
    rng = random.Random(seed)
    def sample():
        return tuple(rng.randrange(1 << precision) for _ in range(4))
    tables = {
        'synthetic_piecewise_constant': [sample() for _ in range(256)],
        'synthetic_random': [sample() for _ in range(1024)],
    }
    tables['synthetic_piecewise_constant'] = [
        row for row in tables['synthetic_piecewise_constant'] for _ in range(4)]
    reports = {}
    for name, table in tables.items():
        rows = {}
        for prune in (False, True):
            circuit = build(table, precision, prune=prune)
            shots = audit(circuit, table, precision, seed)
            rows['pruned' if prune else 'direct'] = {
                'qubits':circuit.num_qubits,
                'toffoli_like':circuit.operation_statistics().num_toffoli_like,
                'kickmix_shots':shots,
                'mismatches':0,
            }
        reports[name] = rows
    args.output.write_text(json.dumps({'kickmix':'1.0.0', 'seed':seed, 'addresses':1024,
                                       'words':4, 'word_bits':precision, 'results':reports},
                                      indent=2)+'\n')
    print(json.dumps(reports))


if __name__ == '__main__':
    main()
