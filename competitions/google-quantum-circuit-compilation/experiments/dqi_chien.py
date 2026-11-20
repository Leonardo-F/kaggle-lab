"""A reversible Chien phase scan from precomputed locator and symbol polynomials."""
from contextlib import contextmanager

import kickmix as km

from dqi_batch_reference import MODULUS, ORDER, POWERS, RADIUS


@contextmanager
def zero_flag(builder, word):
    # The AND of complemented bits detects zero. Measurement erases its carries.
    builder.x(word)
    flags = builder.alloc_qubits(len(word) - 1)
    controls = [word[0], *flags[:-1]]
    for lhs, rhs, out in zip(controls, word[1:], flags):
        builder.init_and(lhs, rhs, out)
    builder.x(word)
    yield flags[-1]
    builder.x(word)
    for lhs, rhs, out in reversed(list(zip(controls, word[1:], flags))):
        builder.del_and(lhs, rhs, out)
    builder.free(flags)
    builder.x(word)


def build_step():
    """Input word j holds coefficient[j] * z^j. Advance z by alpha^-1."""
    width = 12
    field = km.GF2Field(width, modulus=MODULUS, primitive_element=2)
    builder = km.CircuitBuilder()
    def words(count, name):
        reg = builder.create_quantum_register(count*width, name)
        return [reg[i:i+width] for i in range(0, len(reg), width)]

    locator = words(RADIUS+1, 'locator')
    symbol = words(RADIUS, 'symbol')
    mask = builder.create_classical_register(width, 'mask')

    # Each zeroth word doubles as the accumulator. Its coefficient is restored
    # before the constant field multiplications advance the two polynomials.
    for term in locator[1:]:
        builder.cx(term, locator[0])
    for term in symbol[1:]:
        builder.cx(term, symbol[0])
    with zero_flag(builder, locator[0]) as root:
        builder.ccz(root, symbol[0], mask)
    for term in symbol[1:]:
        builder.cx(term, symbol[0])
    for term in locator[1:]:
        builder.cx(term, locator[0])
    for poly in (locator, symbol):
        for j, term in enumerate(poly[1:], 1):
            builder.gf2_imul(POWERS[ORDER-j], target=term, field=field)
    return builder.finish_circuit()
