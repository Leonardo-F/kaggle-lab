"""Replay both small DQI decoders and the full-field Chien scan from saved KMBs."""
import argparse
import hashlib
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest

import kickmix as km
import numpy as np

from dqi_batch_reference import ORDER, POWERS, RADIUS, key_equation, mul, symbol_polynomial, syndromes
from dqi_chien import build_step
from dqi_radius_two import ORDER as SMALL_ORDER, WIDTH, build


def mul16(a, b):
    """Independent shift/XOR multiplication modulo x^4+x+1."""
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & 16:
            a ^= 0x13
    return result


def patterns():
    singles = []
    point = 1
    for position in range(SMALL_ORDER):
        row = []
        for value in range(1, SMALL_ORDER+1):
            term = value
            syndrome = 0
            for j in range(4):
                term = mul16(term, point)
                syndrome |= term << (WIDTH*j)
            row.append((syndrome, value << (WIDTH*position)))
        singles.append(row)
        point = mul16(point, 2)
    yield 0, 0
    for row in singles:
        yield from row
    for left, right in combinations(singles, 2):
        for s1, e1 in left:
            for s2, e2 in right:
                yield s1 ^ s2, e1 ^ e2


def bit_planes(values, width):
    shifts = np.arange(width, dtype=np.uint64)[:, None]
    return ((values >> shifts) & 1).astype(np.bool_)


def audit_radius_two(path, seed):
    circuit = km.Circuit.from_file(path, format='kmb')
    items = list(patterns())
    cases = len(items)
    assert cases == 23851 and len({s for s, _ in items}) == cases
    syndrome, errors = np.array(items, dtype=np.uint64).T
    mask_width = SMALL_ORDER*WIDTH
    rng = np.random.default_rng(seed)
    scratch = [km.q(i) for i in range(4*WIDTH, circuit.num_qubits)]
    expected_registers = {'s': [km.q(i) for i in range(4*WIDTH)],
                          'c': [km.b(i) for i in range(mask_width)]}
    if {k:list(v) for k,v in circuit.register_data.items()} != expected_registers:
        raise ValueError('Unexpected syndrome or mask register layout')
    phase_errors = syndrome_errors = scratch_errors = mask_errors = 0
    shots = 0
    for start in range(0, cases, 1024):
        batch = slice(start, start+1024)
        input_bits = bit_planes(syndrome[batch], 4*WIDTH)
        error_bits = bit_planes(errors[batch], mask_width)
        batch_size = error_bits.shape[1]
        # Check every component of e separately, a zero mask and a dense random
        # mask per syndrome. The expected signs use only the planted errors.
        masks = np.zeros_like(error_bits)
        for probe in range(mask_width+2):
            masks.fill(False)
            if probe < mask_width:
                masks[probe] = True
            elif probe == mask_width+1:
                masks = rng.integers(0, 2, size=masks.shape, dtype=np.uint8).astype(bool)
            expected = np.logical_xor.reduce(masks & error_bits, axis=0)
            sim = km.Simulator(batch_size=batch_size, seed=int(rng.integers(2**63-1)))
            sim.use_same_registers_as(circuit)
            sim.write_across_shots('s', input_bits)
            sim.write_across_shots('c', masks)
            sim.do(circuit)
            # The two candidate circuits use only phases in {+1, -1}.
            phase_errors += np.count_nonzero(sim.read_phase_flipped_across_shots() != expected)
            syndrome_errors += np.count_nonzero(np.any(sim.read_across_shots('s') != input_bits, axis=0))
            scratch_errors += np.count_nonzero(np.any(sim.read_across_shots(scratch), axis=0))
            mask_errors += np.count_nonzero(np.any(sim.read_across_shots('c') != masks, axis=0))
            shots += batch_size
    toffoli = circuit.operation_statistics().num_toffoli_like
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                qubits=circuit.num_qubits, toffoli_like=toffoli,
                qubits_squared_times_toffoli=circuit.num_qubits**2*toffoli,
                shots=shots, phase_errors=int(phase_errors), syndrome_errors=int(syndrome_errors),
                scratch_errors=int(scratch_errors), mask_errors=int(mask_errors))


def prepare_cases(seed):
    rng = random.Random(seed)
    weights = [0, 1, 2, 3, 8, 16, 25, 30, 31, 32, 33, 34, 35, 35, 35, 35]
    errors, locators, symbols = [], [], []
    for weight in weights:
        e = {p:rng.randint(1, ORDER) for p in rng.sample(range(ORDER), weight)}
        locator, evaluator = key_equation(syndromes(e))
        symbol = symbol_polynomial(locator, evaluator)
        errors.append(e)
        locators.append(locator + [0]*(RADIUS+1-len(locator)))
        symbols.append(symbol + [0]*(RADIUS-len(symbol)))
    return weights, errors, locators, symbols


def planes(words):
    """Convert case-major field words to little-endian bit planes for Kickmix."""
    words = np.asarray(words, dtype=np.uint16)
    bits = (words[:, :, None] >> np.arange(12)) & 1
    return bits.astype(bool).reshape(len(words), -1).T.copy()


def audit_step(path, seed):
    step = km.Circuit.from_file(path, format='kmb')
    weights, errors, locators, symbols = prepare_cases(seed)
    rng = np.random.default_rng(seed)
    # One lane for each one-hot symbol bit, one zero mask, one varying dense mask.
    probes = 14
    shots = probes*len(errors)
    sim = km.Simulator(batch_size=shots, seed=seed)
    sim.use_same_registers_as(step)
    initial = {'locator': locators, 'symbol': symbols}
    for name, values in initial.items():
        sim.write_across_shots(name, np.repeat(planes(values), probes, axis=1))
    scratch = [km.q(i) for i in range((2*RADIUS+1)*12, step.num_qubits)]
    masks = np.tile([1 << j for j in range(12)] + [0, 0], len(errors)).astype(np.uint16)
    expected_phase = np.zeros(shots, dtype=bool)
    phase_errors = scratch_errors = mask_errors = coefficient_errors = 0
    # A whole multiplicative cycle restores all coefficients. The input
    # syndrome -> polynomial preparation is classical in this component audit.
    checkpoints = {1, 97, ORDER//2, ORDER}
    for position in range(ORDER):
        masks[probes-1::probes] = rng.integers(0, ORDER+1, size=len(errors))
        mask_bits = planes(masks[:, None])
        sim.write_across_shots('mask', mask_bits)
        sim.do(step)
        planted = np.repeat([e.get(position, 0) for e in errors], probes)
        parity = np.logical_xor.reduce(planes((planted & masks)[:, None]), axis=0)
        expected_phase ^= parity
        phase_errors += np.count_nonzero(sim.read_phase_flipped_across_shots() != expected_phase)
        scratch_errors += np.count_nonzero(np.any(sim.read_across_shots(scratch), axis=0))
        mask_errors += np.count_nonzero(np.any(sim.read_across_shots('mask') != mask_bits, axis=0))
        if position+1 in checkpoints:
            for name, values in initial.items():
                expected = [[mul(c, POWERS[(-(position+1)*j) % ORDER])
                             for j,c in enumerate(poly)] for poly in values]
                mismatch = sim.read_across_shots(name) != np.repeat(planes(expected), probes, axis=1)
                coefficient_errors += np.count_nonzero(np.any(mismatch, axis=0))
    toffoli = step.operation_statistics().num_toffoli_like
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), kickmix=version('kickmix'),
                field='GF(4096), modulus 0x1053', radius=RADIUS, positions=ORDER,
                scope='Chien phase scan only, with classically precomputed locator and symbol inputs',
                weights=weights, seed=seed, lanes=shots, position_lane_checks=ORDER*shots,
                coefficient_checkpoints=sorted(checkpoints), qubits=step.num_qubits,
                toffoli_like_per_step=toffoli, toffoli_like_full_scan=toffoli*ORDER,
                phase_errors=int(phase_errors), scratch_errors=int(scratch_errors),
                mask_errors=int(mask_errors), coefficient_errors=int(coefficient_errors),
                official_verifier_run=False)


def run_experiment(directory):
    directory.mkdir(parents=True, exist_ok=True)
    seed = 20261120
    runs = {}
    for name in ('pointwise', 'precomputed'):
        path = directory/f'radius-two-{name}.kmb'
        build(precompute=(name == 'precomputed')).to_file(path, format='kmb')
        runs[name] = audit_radius_two(path, seed)
    step = directory/'chien-step.kmb'
    build_step().to_file(step, format='kmb')
    toy = dict(field='GF(16), modulus 0x13', radius=2, weight_counts=[1, 225, 23625],
               masks_per_pattern='60 one-hot + zero + seeded random', seed=seed,
               kickmix=version('kickmix'), official_verifier_run=False, runs=runs)
    return {'radius_two': toy, 'full_field_scan': audit_step(step, seed)}


def mismatches(report):
    runs = [*report['radius_two']['runs'].values(), report['full_field_scan']]
    return sum(v for run in runs for k,v in run.items() if k.endswith('_errors'))


class DqiCircuitTests(unittest.TestCase):
    def test_saved_circuits(self):
        with TemporaryDirectory() as directory:
            report = run_experiment(Path(directory))
        self.assertEqual(mismatches(report), 0, report)
        runs = report['radius_two']['runs']
        self.assertLess(runs['precomputed']['qubits_squared_times_toffoli'],
                        runs['pointwise']['qubits_squared_times_toffoli'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = run_experiment(args.output_dir)
    result = json.dumps(report, indent=2)
    (args.output_dir/'dqi-reversible-results.json').write_text(result+'\n')
    print(result)
    raise SystemExit(bool(mismatches(report)))
