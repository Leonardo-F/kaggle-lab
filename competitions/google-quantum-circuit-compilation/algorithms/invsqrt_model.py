"""Reproducible integer fixed-point model for a candidate invsqrt phase.

This is a numerical experiment, not a reversible circuit or official verifier.
Every arithmetic stage uses nearest-even rounding. The binary exponent is kept
separately, so denormalization does NOT throw away k more fractional bits.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib
import json
from pathlib import Path
import platform

MAX_X = 3133452


def round_shift(value: int, bits: int) -> int:
    q, r = divmod(value, 1 << bits)
    half = 1 << (bits-1)
    return q + int(r > half or (r == half and q % 2))


class FixedInvSqrt:
    def __init__(self, segments: int = 64, fraction_bits: int = 28):
        if (type(segments) is not int or not 1 <= segments <= 1024 or segments & (segments-1)
                or type(fraction_bits) is not int or not 20 <= fraction_bits <= 30):
            raise ValueError('segments must be a power of 2 in 1..1024; fraction_bits must be 20..30')
        self.segments, self.bits = segments, fraction_bits
        self.scale = 1 << self.bits
        self.intercepts, self.slopes = [], []
        with localcontext() as ctx:
            ctx.prec = 80
            width = Decimal(3)/segments
            for j in range(segments):
                left = 1 + j*width
                a, c = 1/left.sqrt(), 1/(left+width).sqrt()
                self.intercepts.append(int((a*self.scale).to_integral_value(rounding=ROUND_HALF_EVEN)))
                self.slopes.append(int(((c-a)/width*self.scale).to_integral_value(rounding=ROUND_HALF_EVEN)))

    def evaluate(self, x: int) -> tuple[int, int]:
        """Return (numerator, binary denominator exponent) for the phase turns."""
        if type(x) is not int or not 1 <= x <= MAX_X:
            raise ValueError(f'x must be an integer in 1..{MAX_X}')
        k = (x.bit_length()-1)//2
        m = x << (self.bits-2*k)  # exact for the supported input/width range
        j = (m-self.scale)*self.segments//(3*self.scale)
        left = self.scale + j*3*self.scale//self.segments
        y0 = self.intercepts[j] + round_shift(self.slopes[j]*(m-left), self.bits)
        y_sq = round_shift(y0*y0, self.bits)
        my_sq = round_shift(m*y_sq, self.bits)
        y1 = round_shift(y0*(3*self.scale-my_sq), self.bits+1)
        return y1, self.bits+k

    def scan(self, max_x: int = MAX_X, chunk_size: int = 65536) -> dict:
        import numpy as np

        if type(max_x) is not int or not 1 <= max_x <= MAX_X or type(chunk_size) is not int or chunk_size < 1:
            raise ValueError('Invalid input range or chunk size')
        def rounded(values, bits):
            q, r = np.divmod(values, 1 << bits)
            half = 1 << (bits-1)
            return q + ((r > half) | ((r == half) & ((q & 1) != 0)))

        intercepts = np.asarray(self.intercepts, dtype=np.int64)
        slopes = np.asarray(self.slopes, dtype=np.int64)
        failures, worst_x, worst_error = 0, 1, 0.0
        min_margin, margin_x = float('inf'), 1
        # Exact integer version of (1-tol)^2 <= y1^2*m/S^3 <= (1+tol)^2.
        lower = (2**24-1)**2 * self.scale**3
        upper = (2**24+1)**2 * self.scale**3
        for start in range(1, max_x+1, chunk_size):
            x = np.arange(start, min(start+chunk_size, max_x+1), dtype=np.int64)
            k = np.zeros(len(x), dtype=np.int64)
            for e in range(1, 11):
                k[x >= 4**e] = e
            m = np.left_shift(x, self.bits) >> (2*k)
            j = (m-self.scale)*self.segments//(3*self.scale)
            left = self.scale + j*3*self.scale//self.segments
            y0 = intercepts[j] + rounded(slopes[j]*(m-left), self.bits)
            y_sq = rounded(y0*y0, self.bits)
            my_sq = rounded(m*y_sq, self.bits)
            y1 = rounded(y0*(3*self.scale-my_sq), self.bits+1)
            # Python arbitrary-precision integers prevent overflow in the proof
            # check. The vectorized arithmetic above fits signed int64 at <=30 bits.
            exact = y1.astype(object)**2 * m.astype(object) * 2**48
            failures += int(np.count_nonzero((exact < lower) | (exact > upper)))
            relative = np.abs(y1.astype(float)/self.scale*np.sqrt(m.astype(float)/self.scale)-1)
            i = int(np.argmax(relative))
            if float(relative[i]) > worst_error:
                worst_error, worst_x = float(relative[i]), int(x[i])
            margin = (2**-24-relative)/np.sqrt(x.astype(float))
            i = int(np.argmin(margin))
            if float(margin[i]) < min_margin:
                min_margin, margin_x = float(margin[i]), int(x[i])
        tables = {'intercepts': self.intercepts, 'slopes': self.slopes}
        return {
            'stage': 'integer-numerical-model', 'official_circuit_verified': False,
            'segments': self.segments, 'fraction_bits': self.bits,
            'rounding': 'nearest-even at each multiplication and Newton division',
            'denormalization': 'separate binary exponent; no extra right-shift rounding',
            'inputs_checked': max_x, 'failures_exact': failures,
            'max_relative_error_float': worst_error, 'worst_x_float': worst_x,
            'min_phase_margin_turns_float': min_margin, 'margin_x_float': margin_x,
            'tolerance_relative': 2**-24,
            'coefficients_sha256': hashlib.sha256(json.dumps(tables, sort_keys=True).encode()).hexdigest(),
            'tables': tables,
        }


def main():
    import numpy as np
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--segments', type=int, nargs='+', default=[32,64,128])
    parser.add_argument('--bits', type=int, nargs='+', default=[26,28,30])
    parser.add_argument('--max-x', type=int, default=MAX_X)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runs = []
    for segments in args.segments:
        for bits in args.bits:
            result = FixedInvSqrt(segments,bits).scan(args.max_x)
            runs.append(result)
            print(json.dumps({k:v for k,v in result.items() if k != 'tables'}),flush=True)
    report = {'python': platform.python_version(), 'numpy': np.__version__,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'runs': runs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
