"""Compile two radius-two DQI phase decoders over GF(16) for a resource comparison."""
from contextlib import contextmanager

import kickmix as km

from dqi_chien import zero_flag


FIELD = km.GF2Field(4, modulus=0x13, primitive_element=2)
WIDTH = FIELD.degree
ORDER = (1 << WIDTH) - 1


def xor_linear(builder, source, target, images):
    """XOR a GF(2)-linear map into target, given the images of its basis bits."""
    for wire, image in zip(source, images):
        for bit, out in enumerate(target):
            if image & (1 << bit):
                builder.cx(wire, out)


@contextmanager
def add_terms(builder, target, *terms):
    """Temporarily add fixed linear images of disjoint registers to target."""
    for source, images in terms:
        xor_linear(builder, source, target, images)
    yield target
    for source, images in reversed(terms):
        xor_linear(builder, source, target, images)


@contextmanager
def product(builder, left, right):
    out = builder.init_gf2_mul(left, right, field=FIELD)
    yield out
    builder.del_gf2_mul(left, right, target=out, field=FIELD)
    builder.free(out)


def scan(builder, s1, s2, determinant, linear, quadratic, gain, masks, coefficients):
    basis = [1 << bit for bit in range(WIDTH)]
    for position in range(ORDER):
        z = FIELD.pow(2, (-position) % ORDER)
        z_map = [FIELD.mul(z, v) for v in basis]
        z2_map = [FIELD.mul(FIELD.square(z), v) for v in basis]
        mask = masks[position*WIDTH:(position+1)*WIDTH]
        # Test the projective locator D + L*z + M*z^2 in place.
        with add_terms(builder, determinant, (linear, z_map), (quadratic, z2_map)):
            with zero_flag(builder, determinant) as root:
                if coefficients is not None:
                    a, b = coefficients
                    with add_terms(builder, a, (b, z_map)) as symbol:
                        builder.ccz(root, symbol, mask)
                else:
                    # Same gain as the optimized circuit. Multiply after evaluation.
                    with add_terms(builder, s1, (s2, z_map)) as value:
                        with product(builder, gain, value) as symbol:
                            # S1*z = value*z + S2*z^2 in characteristic two.
                            with add_terms(builder, symbol, (value, z_map), (s2, z2_map)):
                                builder.ccz(root, symbol, mask)


def build(precompute=True):
    builder = km.CircuitBuilder()
    syndrome = builder.create_quantum_register(4*WIDTH, 's')
    masks = builder.create_classical_register(ORDER*WIDTH, 'c')
    s1, s2, s3, s4 = (syndrome[i:i+WIDTH] for i in range(0, len(syndrome), WIDTH))
    squares = [FIELD.square(1 << bit) for bit in range(WIDTH)]
    identity = [1 << bit for bit in range(WIDTH)]

    # Two-error locator coefficients from the two syndrome recurrences.
    with (product(builder, s1, s3) as d, product(builder, s2, s3) as l,
          product(builder, s2, s4) as m):
        builder.ixor_gf2_mul(s1, s4, target=l, field=FIELD)
        with add_terms(builder, d, (s2, squares)), add_terms(builder, m, (s3, squares)):
            with zero_flag(builder, d) as degenerate:
                # One error has locator S1 + S2*z. Zero errors yield zero symbols.
                builder.ccx(degenerate, s1, d)
                builder.ccx(degenerate, s2, l)
                reciprocal = builder.init_gf2_inverse(l, field=FIELD)  # 0 maps to 0
                with product(builder, d, reciprocal) as gain:
                    if precompute:
                        with product(builder, gain, s1) as a, product(builder, gain, s2) as b:
                            with add_terms(builder, b, (s1, identity)):
                                scan(builder, s1, s2, d, l, m, gain, masks, (a, b))
                    else:
                        scan(builder, s1, s2, d, l, m, gain, masks, None)
                builder.del_gf2_inverse(l, target=reciprocal, field=FIELD)
                builder.free(reciprocal)
                builder.ccx(degenerate, s2, l)
                builder.ccx(degenerate, s1, d)
        builder.ixor_gf2_mul(s1, s4, target=l, field=FIELD)
    return builder.finish_circuit()
