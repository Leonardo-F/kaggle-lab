"""Exhaustive integer model check and seeded Kickmix replay of the saved circuit."""
import argparse
from fractions import Fraction
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'algorithms'))
from invsqrt_circuit import (DEFAULT_FRACTION, DEFAULT_PHASE, MAX_X, WIDTH,
                             phase_fraction)


def scan(bits, centered, fraction_bits, phase_bits, integer_fit=False):
    failures = 0
    worst, min_margin = 0., math.inf
    for x in range(1, MAX_X+1):
        num, exp = phase_fraction(x, bits, centered, fraction_bits, phase_bits, integer_fit)
        # For a nonnegative unwrapped phase, squaring preserves both inequalities.
        value = (x*num*num) << 48
        if not ((2**24-1)**2 << (2*exp)) <= value <= ((2**24+1)**2 << (2*exp)):
            failures += 1
        root = math.sqrt(x)
        error = abs(math.ldexp(num, -exp) * root - 1)
        if error > worst:
            worst, worst_x = error, x
        margin = (2**-24-error)/root
        if margin < min_margin:
            min_margin, tight_x = margin, x
    return dict(inputs=MAX_X, failures=failures, max_relative_error=worst,
                worst_x=worst_x, min_turn_margin=min_margin, tightest_margin_x=tight_x)


def sampled_inputs(bits, rng, draws):
    xs = {1, MAX_X}
    for e in range(WIDTH):
        # Powers of two and several lookup-bin boundaries in each exponent range.
        step = 1 << max(0,e-bits)
        for offset in (0, 1, 2**bits//2, 2**bits-1):
            for delta in (-1,0,1,step//2):
                x = (1 << e) + offset*step + delta
                if 1 <= x <= MAX_X:
                    xs.add(x)
    xs.update(rng.sample(range(1,MAX_X+1),draws))
    return sorted(xs)


def replay(circuit, model, seed, draws, repetitions, all_inputs=False):
    import kickmix as km
    rng = random.Random(seed)
    xs = range(1, MAX_X+1) if all_inputs else sampled_inputs(model[0], rng, draws)
    named = circuit.register_data
    if set(named) != {'x'} or list(named['x']) != [km.q(i) for i in range(WIDTH)]:
        raise ValueError('Expected the named x register on the first 22 qubits, little endian')
    all_qubits = [km.q(i) for i in range(circuit.num_qubits)]
    # Contiguous batches also make a full-domain pass inexpensive in memory.
    phase_errors = state_errors = 0
    batches = (len(xs) + 255)//256
    for batch_id in range(batches * repetitions):
        start = (batch_id % batches) * 256
        batch = xs[start:start+256]
        sim = km.Simulator(batch_size=len(batch), seed=rng.getrandbits(63))
        sim.use_same_registers_as(circuit)
        for i,x in enumerate(batch):
            sim.write_within_shot('x',i,x)
        sim.do(circuit)
        for i,x in enumerate(batch):
            num, exp = phase_fraction(x, *model)
            phase_errors += Fraction(sim.read_shot_phase(i), 2) % 1 != Fraction(num, 1 << exp) % 1
            state_errors += sim.read_within_shot(all_qubits,i,out=int) != x
    return dict(distinct_inputs=len(xs), repetitions=repetitions, shots=len(xs)*repetitions, seed=seed,
                phase_mismatches=phase_errors, input_or_scratch_mismatches=state_errors)


def main():
    import kickmix as km
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bits', type=int, choices=(10,11), default=10)
    parser.add_argument('--fraction-bits', type=int, choices=range(26,31), default=DEFAULT_FRACTION)
    parser.add_argument('--phase-bits', type=int, choices=range(32,65), default=DEFAULT_PHASE)
    parser.add_argument('--integer-fit', action='store_true')
    parser.add_argument('--secant', action='store_true')
    parser.add_argument('--seed', type=int, default=20261119)
    parser.add_argument('--all-inputs', action='store_true', help='replay every legal x in Kickmix')
    parser.add_argument('--draws', type=int, default=4096)
    parser.add_argument('--repetitions', type=int, default=4)
    args = parser.parse_args()
    if args.output.resolve() == args.input.resolve() or not (1 <= args.draws <= MAX_X and args.repetitions > 0):
        parser.error('Use separate paths and positive sample sizes within the input domain')
    circuit = km.Circuit.from_file(args.input, format='kmb')
    model = (args.bits, not args.secant, args.fraction_bits, args.phase_bits, args.integer_fit)
    ranges = scan(*model)
    tests = replay(circuit, model, args.seed, args.draws, args.repetitions, args.all_inputs)
    stats = circuit.operation_statistics()
    fine = sum(n for level,n in stats.z_pow_clifford_hierarchy_counts.items() if level>3)
    estimate = None
    if ranges['min_turn_margin'] > 0 and not (tests['phase_mismatches'] or tests['input_or_scratch_mismatches']):
        eps = math.pi * ranges['min_turn_margin'] / fine
        t = stats.num_t_like + fine * (.56*math.log2(1/eps)+5.3)
        estimate = circuit.num_qubits * (stats.num_toffoli_like + t/4)
    report = dict(official_verifier_run=False, kaggle_scored=False, kickmix=version('kickmix'),
                  circuit_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                  prefix_bits=args.bits, centered=not args.secant, fraction_bits=args.fraction_bits,
                  phase_bits=args.phase_bits, integer_fit=args.integer_fit, qubits=circuit.num_qubits,
                  static_toffoli_like=stats.num_toffoli_like, t_like=stats.num_t_like,
                  fine_rotations=fine, model=ranges, circuit_replay=tests,
                  paper_formula_cost_estimate=estimate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return int(bool(ranges['failures'] or tests['phase_mismatches'] or tests['input_or_scratch_mismatches']))


if __name__ == '__main__':
    raise SystemExit(main())
