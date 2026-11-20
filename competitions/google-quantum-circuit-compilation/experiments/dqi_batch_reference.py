"""Compare classical DQI symbol recovery by batches and polynomial precomputation."""
import argparse
import json
from pathlib import Path
import random

ORDER = 4095
RADIUS = 35
MODULUS = 0x1053  # x^12 + x^6 + x^4 + x + 1


def field_tables():
    powers, logs = [], [-1]*(ORDER+1)
    value = 1
    for i in range(ORDER):
        if logs[value] >= 0:
            raise ValueError('The field generator is not primitive')
        powers.append(value)
        logs[value] = i
        value <<= 1
        if value > ORDER:
            value ^= MODULUS
    return powers+powers, logs


POWERS, LOGS = field_tables()


def mul(a, b):
    return POWERS[LOGS[a]+LOGS[b]] if a and b else 0


def inverse(a):
    if not a:
        raise ZeroDivisionError('No inverse of zero in GF(4096)')
    return POWERS[ORDER-LOGS[a]]


def syndromes(errors):
    result = [0]*(2*RADIUS)
    for location, value in errors.items():
        for i in range(len(result)):
            result[i] ^= mul(value, POWERS[((i+1)*location) % ORDER])
    return result


def key_equation(s):
    """Berlekamp–Massey with syndrome convention starting at power one."""
    locator, previous = [1]+[0]*len(s), [1]+[0]*len(s)
    degree, shift, old_discrepancy = 0, 1, 1
    for i, symbol in enumerate(s):
        discrepancy = symbol
        for j in range(1, degree+1):
            discrepancy ^= mul(locator[j], s[i-j])
        if not discrepancy:
            shift += 1
            continue
        old_locator = locator.copy()
        factor = mul(discrepancy, inverse(old_discrepancy))
        for j in range(len(s)+1-shift):
            locator[j+shift] ^= mul(factor, previous[j])
        if 2*degree <= i:
            degree = i+1-degree
            previous, shift, old_discrepancy = old_locator, 1, discrepancy
        else:
            shift += 1
    if degree > RADIUS:
        raise ValueError('Outside supported decoding radius')
    locator = locator[:degree+1]
    evaluator = []
    for i in range(degree):
        coefficient = 0
        for j in range(i+1):
            coefficient ^= mul(locator[j], s[i-j])
        evaluator.append(coefficient)
    return locator, evaluator


def evaluate(poly, x):
    value = 0
    for coefficient in reversed(poly):
        value = mul(value, x) ^ coefficient
    return value


def batch_inverse(nonzero):
    prefix = [nonzero[0]]
    for value in nonzero[1:]:
        prefix.append(mul(prefix[-1], value))
    product_inverse = inverse(prefix[-1])
    result = [0]*len(nonzero)
    for j in range(len(nonzero)-1, 0, -1):
        result[j] = mul(product_inverse, prefix[j-1])
        product_inverse = mul(product_inverse, nonzero[j])
    result[0] = product_inverse
    return result


def decode_windows(locator, evaluator, widths):
    derivative = [locator[j] if j % 2 else 0 for j in range(1,len(locator))]
    # Save every position, including nonroots, to model fixed circuit windows.
    # The derivative may vanish at a nonroot. A neutral one takes its place.
    roots, numerators, denominators = [], [], []
    for position in range(ORDER):
        x = POWERS[ORDER-position]
        hit = evaluate(locator, x) == 0
        roots.append(hit)
        numerators.append(evaluate(evaluator, x) if hit else 0)
        denominators.append(evaluate(derivative, x) if hit else 1)
    decoded = {}
    for width in widths:
        errors = {}
        for first in range(0, ORDER, width):
            values = batch_inverse(denominators[first:first+width])
            for i, reciprocal in enumerate(values, first):
                if roots[i]:
                    errors[i] = mul(numerators[i], reciprocal)
        decoded[width] = errors
    return decoded


def trim(poly):
    while poly and poly[-1] == 0:
        poly.pop()
    return poly


def polynomial_product(left, right):
    if not left or not right:
        return []
    result = [0]*(len(left)+len(right)-1)
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            result[i+j] ^= mul(a,b)
    return trim(result)


def polynomial_xor(left, right):
    result = [0]*max(len(left),len(right))
    for values in (left,right):
        for i,value in enumerate(values):
            result[i] ^= value
    return trim(result)


def polynomial_division(dividend, divisor):
    remainder = trim(dividend.copy())
    quotient = [0]*max(0,len(remainder)-len(divisor)+1)
    lead_inverse = inverse(divisor[-1])
    while len(remainder) >= len(divisor):
        offset = len(remainder)-len(divisor)
        factor = mul(remainder[-1],lead_inverse)
        quotient[offset] = factor
        for i,value in enumerate(divisor,offset):
            remainder[i] ^= mul(factor,value)
        trim(remainder)
    return trim(quotient), remainder


def symbol_polynomial(locator, evaluator):
    """Solve locator'(z)*result(z) = evaluator(z) mod locator(z)."""
    if locator == [1]:
        return []
    derivative = trim([locator[j] if j % 2 else 0 for j in range(1,len(locator))])
    a,b = locator,derivative
    u,v = [],[1]
    while b:
        q,r = polynomial_division(a,b)
        a,b = b,r
        u,v = v,polynomial_xor(u,polynomial_product(q,v))
    if len(a) != 1:
        raise ValueError('Locator and derivative are not coprime')
    scale = inverse(a[0])
    scaled_inverse = [mul(scale,coefficient) for coefficient in u]
    _, symbol = polynomial_division(polynomial_product(evaluator,scaled_inverse),locator)
    return symbol


def precomputed_symbols(locator, evaluator):
    symbol = symbol_polynomial(locator, evaluator)
    # The fixed Chien scan needs only fixed-scalar field multiplications and
    # additions to evaluate these two polynomials. There is no division here.
    errors = {}
    for position in range(ORDER):
        x = POWERS[ORDER-position]
        if evaluate(locator,x) == 0:
            errors[position] = evaluate(symbol,x)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    seed = 20261120
    rng = random.Random(seed)
    weights = [0, 1, 2, 16] + [30, 31, 32, 33, 34, 35]*8
    widths = (1, 4, 8, 16)
    for weight in weights:
        errors = {pos: rng.randint(1, ORDER) for pos in rng.sample(range(ORDER), weight)}
        masks = [rng.randrange(ORDER+1) for _ in range(ORDER)]
        phase = sum((masks[i] & value).bit_count() for i,value in errors.items()) % 2
        polynomials = key_equation(syndromes(errors))
        if precomputed_symbols(*polynomials) != errors:
            raise ValueError(f'Polynomial recovery mismatch for weight {weight}')
        for width, decoded in decode_windows(*polynomials, widths).items():
            actual = sum((masks[i] & value).bit_count() for i,value in decoded.items()) % 2
            if decoded != errors or actual != phase:
                raise ValueError(f'Decode or phase mismatch for weight {weight}, window {width}')
    windows = []
    for width in widths:
        batches = (ORDER+width-1)//width
        windows.append({'window':width, 'inversions':batches,
                        'extra_field_multiplications':3*(ORDER-batches)})
    report = {'mode':'classical synthetic errors with official field and syndrome parameters',
              'seed':seed, 'cases':len(weights), 'weights':weights,
              'decode_and_phase_mismatches':0, 'polynomial_recovery_mismatches':0,
              'polynomial_recovery_inversions_inside_chien_scan':0,
              'arithmetic_per_fixed_position_scan':windows}
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(weights)} inputs passed at each window width')


if __name__ == '__main__':
    main()
