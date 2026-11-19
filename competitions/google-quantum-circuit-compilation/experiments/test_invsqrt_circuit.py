import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'algorithms'))
from invsqrt_circuit import MAX_X, build, phase_fraction


class LinearPhaseTests(unittest.TestCase):
    def within_tolerance(self, x, bits, centered, precision, phase_bits, integer_fit=False):
        y, e = phase_fraction(x, bits, centered, precision, phase_bits, integer_fit)
        v = (x*y*y) << 48
        return (2**24-1)**2 << (2*e) <= v <= (2**24+1)**2 << (2*e)

    def test_midpoint_and_quantization_regressions(self):
        self.assertFalse(self.within_tolerance(4102, 10, False, 30, 64))
        self.assertFalse(self.within_tolerance(2107391, 10, True, 26, 39))
        self.assertTrue(self.within_tolerance(2107391, 10, True, 26, 39, integer_fit=True))
        for x in (1, 2, 3, 4102, 2107391, 2170879, MAX_X):
            self.assertTrue(self.within_tolerance(x, 10, True, 27, 39))

    @unittest.skipUnless(importlib.util.find_spec('kickmix'), 'requires kickmix==1.0.0')
    def test_registers_wraparound_and_clean_workspace(self):
        from fractions import Fraction
        import kickmix as km
        points = (1, 2, 3, 1023, 1024, 1025, 2097152, MAX_X)
        for args, paired in (((10, True, 27, 39), True), ((10, True, 27, 39), False),
                             ((11, False, 26, 64), True)):
            circuit = build(*args, paired_lookup=paired)
            sim = km.Simulator(batch_size=len(points), seed=29)
            sim.use_same_registers_as(circuit)
            for shot,x in enumerate(points):
                sim.write_within_shot('x',shot,x)
            sim.do(circuit)
            wires = [km.q(i) for i in range(circuit.num_qubits)]
            for shot,x in enumerate(points):
                self.assertEqual(sim.read_within_shot(wires,shot,out=int), x)
                y,e = phase_fraction(x,*args)
                self.assertEqual(Fraction(sim.read_shot_phase(shot),2) % 1, Fraction(y,2**e) % 1)
