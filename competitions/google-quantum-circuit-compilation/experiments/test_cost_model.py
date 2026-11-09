import importlib.util
import math
import sys
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "algorithms" / "cost_model.py"
SPEC = importlib.util.spec_from_file_location("cost_model", PATH)
cost_model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cost_model
SPEC.loader.exec_module(cost_model)

class CostModelTests(unittest.TestCase):
    def test_invsqrt(self):
        self.assertAlmostEqual(cost_model.invsqrt_cost(10, 100, 40), 1100)

    def test_dqi(self):
        self.assertAlmostEqual(cost_model.dqi_repetition(0), 1)
        with self.assertRaises(ValueError):
            cost_model.dqi_cost(10, 100, 1/16)

    def test_dfthcsos(self):
        self.assertAlmostEqual(cost_model.dfthcsos_lambda(1, 1), 1)

    def test_overall(self):
        ref = {'invsqrt': 100, 'dqi': 200, 'dfthcsos': 300}
        candidate = {'invsqrt': 50, 'dqi': 100, 'dfthcsos': 150}
        self.assertAlmostEqual(cost_model.overall_score(ref, candidate), 2)

if __name__ == '__main__':
    unittest.main()
