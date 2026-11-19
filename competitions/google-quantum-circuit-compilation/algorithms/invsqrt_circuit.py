"""Compile an inverse-square-root phase oracle using dyadic linear interpolation."""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
from functools import lru_cache
from pathlib import Path

from invsqrt_model import MAX_X

WIDTH = MAX_X.bit_length()
TOP = WIDTH - 1
DEFAULT_FRACTION = 27
DEFAULT_PHASE = 39


@lru_cache
def coefficients(bits: int, centered: bool, fraction_bits: int) -> tuple[list[int], list[int]]:
    if bits not in (10, 11):
        raise ValueError('Supported address widths are 10 and 11')
    if not 26 <= fraction_bits <= 30:
        raise ValueError('Coefficient precision must be in 26..30')
    count = 1 << bits
    intercept, drop = [], []
    with localcontext() as ctx:
        ctx.prec = 70
        for parity in (1, 0):  # Address high bit is the leading-zero count modulo 2.
            for index in range(count):
                start = Decimal(count + index) / count
                end = Decimal(count + index + 1) / count
                def value(m):
                    return Decimal(1) / (m * (1 << parity)).sqrt()
                a, b = value(start), value(end)
                # Convex f lies below its secant. Split the midpoint gap between
                # endpoints and interior before independently quantizing A and D.
                shift = ((a + b)/2 - value((start + end)/2))/2 if centered else 0
                intercept.append(round((a-shift) * (1 << fraction_bits)))
                drop.append(round((a-b) * (1 << fraction_bits)))
    return intercept, drop


def phase_fraction(x: int, bits: int, centered: bool, fraction_bits: int, phase_bits: int) -> tuple[int, int]:
    """Unwrapped phase as an exact integer divided by 2**exponent."""
    if not 1 <= x <= MAX_X:
        raise ValueError('x outside benchmark domain')
    a, d = coefficients(bits, centered, fraction_bits)
    zeros = WIDTH - x.bit_length()
    rbits = TOP-bits
    normalized = x << zeros
    address = (zeros % 2 << bits) | ((normalized >> rbits) % (1 << bits))
    residual = normalized % (1 << rbits)
    exponent = fraction_bits + rbits + (TOP-zeros)//2
    clipped = max(0, exponent-phase_bits)
    return ((a[address] << rbits) - d[address]*residual) >> clipped, exponent-clipped


def build(bits: int = 10, centered: bool = True, fraction_bits: int = DEFAULT_FRACTION,
          phase_bits: int = DEFAULT_PHASE, paired_lookup: bool = True):
    import kickmix as km

    if not 32 <= phase_bits <= 64:
        raise ValueError('Phase precision must be in 32..64')
    intercept, drop = coefficients(bits, centered, fraction_bits)
    rbits = TOP-bits
    builder = km.CircuitBuilder()
    x = builder.create_quantum_register(WIDTH, 'x')
    zero_flags = builder.alloc_qubits(TOP.bit_length())
    stages = [(1 << i, zero_flags[i]) for i in reversed(range(len(zero_flags)))]

    # Save binary leading-zero count, in place normalize x to [2**TOP, 2**WIDTH).
    for shift, flag in stages:
        builder.flip_if_equal(x[WIDTH-shift:], 0, target=flag)
        builder.left_rotate(x, shift, control=flag)

    addr = x[rbits:TOP] + zero_flags[:1]
    a_width = max(intercept).bit_length()
    d_width = max(drop).bit_length()
    if not paired_lookup:
        low = builder.alloc_qubits(rbits)
    a = builder.alloc_qubits(a_width)
    d = builder.alloc_qubits(d_width)
    # One QROM address traversal loads both coefficients into disjoint bit fields.
    words = [v | (w << a_width) for v,w in zip(intercept, drop)]
    if paired_lookup:
        # Load adjacent entries during the same address traversal. Preserve the
        # selected word and erase its neighbor before allocating the multiplier.
        word = a + d
        neighbor = builder.alloc_qubits(len(word))
        pairs = [even | (odd << len(word)) for even, odd in zip(words[::2], words[1::2])]
        builder.init_lookup(table=pairs, address=addr[1:], target=word+neighbor)
        builder.cswap(addr[0], word, neighbor)
        # After the controlled swap, the unused entry is a function of the
        # original address. Measurement-based QROM erasure restores clean wires.
        other_words = [words[j ^ 1] for j in range(len(words))]
        half = len(addr)//2
        pad = builder.alloc_qubits(max(0, (1 << half) - half - len(word)))
        builder.del_lookup(table=other_words, address=addr, target=neighbor+pad)
        builder.free(neighbor+pad)
        low = builder.alloc_qubits(rbits)
    else:
        builder.init_lookup(table=words, address=addr, target=a+d)

    product = low + a
    for i in range(rbits):
        builder.isub(d, target=product[i:], control=x[i])

    # The phase in turns is product * 2**(zeros//2) / 2**(F+rbits+TOP//2).
    # Extra zero bits make these rotations logical shifts on every valid input.
    extra = builder.alloc_qubits(TOP//2)
    scaled = product + extra
    builder.left_rotate(scaled, zero_flags[1:])
    denom_bits = fraction_bits + rbits + TOP//2
    for i in range(max(0, denom_bits-phase_bits), min(len(scaled), denom_bits)):
        builder.z_pow(scaled[i], 2.0 ** (1+i-denom_bits))
    builder.right_rotate(scaled, zero_flags[1:])
    builder.free(extra)
    for i in reversed(range(rbits)):
        builder.iadd(d, target=product[i:], control=x[i])
    # Kickmix 1.0.0 unfolds the low half of the address during QROM erasure.
    # The restored low product bits can serve as extra all-zero output planes.
    half_address = len(addr)//2
    pad = max(0, (1 << half_address) - half_address - len(a) - len(d))
    padding = low[:pad] + builder.alloc_qubits(max(0, pad - len(low)))
    builder.del_lookup(table=words, address=addr, target=a+d+padding)
    for shift, flag in reversed(stages):
        builder.right_rotate(x, shift, control=flag)
        builder.flip_if_equal(x[WIDTH-shift:], 0, target=flag)
    return builder.finish_circuit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bits', type=int, choices=(10,11), default=10)
    parser.add_argument('--fraction-bits', type=int, choices=range(26,31), default=DEFAULT_FRACTION)
    parser.add_argument('--phase-bits', type=int, choices=range(32,65), default=DEFAULT_PHASE)
    parser.add_argument('--single-lookup', action='store_true', help='use the one-word QROM baseline')
    parser.add_argument('--secant', action='store_true', help='omit the midpoint correction')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.suffix != '.kmb':
        parser.error('Specify a .kmb output file')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    circuit = build(args.bits, not args.secant, args.fraction_bits, args.phase_bits, not args.single_lookup)
    circuit.to_file(args.output, format='kmb')
    print(f'{circuit.num_qubits} qubits; {circuit.operation_statistics().num_toffoli_like} Toffoli-like gates')


if __name__ == '__main__':
    main()
