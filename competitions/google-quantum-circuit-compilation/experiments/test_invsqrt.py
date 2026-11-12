"""Integer-model error checks; these are not official circuit certification."""
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'algorithms' / 'invsqrt_model.py'


class InverseSquareRootTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'reproducible integer model is missing')
        spec = importlib.util.spec_from_file_location('invsqrt_model', SOURCE)
        self.model = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.model
        spec.loader.exec_module(self.model)

    def test_powers_of_four_are_exact_and_input_is_bounded(self):
        model = self.model.FixedInvSqrt(64, 28)
        for k in range(11):
            numerator, exponent = model.evaluate(4**k)
            self.assertEqual(numerator * 2**k, 2**exponent)
        for x in [0, -1, 3133453, 1.2]:
            with self.assertRaises(ValueError):
                model.evaluate(x)

    def test_rounding_and_large_inputs_agree_with_independent_decimal_reference(self):
        model = self.model.FixedInvSqrt(128, 30)
        for x in [2, 3, 15, 16, 17, 65535, 65536, 65537, 1048575, 1048576, 1048577, 3133452]:
            numerator, exponent = model.evaluate(x)
            with localcontext() as ctx:
                ctx.prec = 70
                value = Decimal(numerator) / Decimal(2)**exponent
                relative = abs(value * Decimal(x).sqrt()-1)
            self.assertLess(relative, Decimal(2)**-24, x)

    def test_vector_scan_matches_scalar_including_exact_failure_count(self):
        model = self.model.FixedInvSqrt(32, 24)
        result = model.scan(max_x=1000, chunk_size=97)
        failures = 0
        for x in range(1, 1001):
            y, e = model.evaluate(x)
            # |y/2**e - 1/sqrt(x)| <= 2**-24/sqrt(x)
            scaled = y*y*x*2**48
            failures += not ((2**24-1)**2*2**(2*e) <= scaled <= (2**24+1)**2*2**(2*e))
        self.assertEqual(result['inputs_checked'], 1000)
        self.assertEqual(result['failures_exact'], failures)
        self.assertEqual(result['stage'], 'integer-numerical-model')
        self.assertFalse(result['official_circuit_verified'])

    def test_configuration_is_explicit_and_invalid_widths_fail(self):
        for segments, bits in [(3,28), (0,28), (64,19), (64,31)]:
            with self.assertRaises(ValueError):
                self.model.FixedInvSqrt(segments,bits)


if __name__ == '__main__':
    unittest.main()
