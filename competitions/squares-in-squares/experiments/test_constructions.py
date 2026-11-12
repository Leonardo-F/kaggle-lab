"""Independent construction invariants and the written CSV certification."""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

ALGORITHMS = Path(__file__).resolve().parents[1] / 'algorithms'
sys.path.insert(0, str(ALGORITHMS))
import packing


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        source = ALGORITHMS / 'constructions.py'
        self.assertTrue(source.is_file(), 'structured constructions are not implemented')
        spec = importlib.util.spec_from_file_location('packing_constructions', source)
        self.c = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.c
        spec.loader.exec_module(self.c)

    def test_tilted_five_is_feasible_and_smaller_than_three(self):
        tiles = self.c.four_corners(1)
        self.assertEqual(len(tiles), 5)
        self.assertFalse(packing.validate_layout(tiles))
        self.assertAlmostEqual(packing.extent(tiles), 2 + math.sqrt(2)/2, places=6)

    def test_staircases_do_not_overlap(self):
        for m, b in [(2, 1), (4, 4), (5, 5), (8, 10), (15, 19)]:
            tiles = self.c.diamond_staircase(m, b)
            self.assertEqual(len(tiles), 2*m*(m-1) + b*b)
            self.assertFalse(packing.validate_layout(tiles), (m, b))
        with self.assertRaises(ValueError):
            self.c.diamond_staircase(5, 1)

    def test_all_counts_fall_back_to_grid_and_square_counts_stay_optimal(self):
        portfolio = self.c.build_portfolio()
        self.assertEqual(set(portfolio), set(range(1, 1001)))
        for n, candidate in portfolio.items():
            self.assertEqual(len(candidate.tiles), n)
            self.assertLessEqual(candidate.side, math.ceil(math.sqrt(n)))
            if math.isqrt(n)**2 == n:
                self.assertEqual(candidate.method, 'grid')
                self.assertEqual(candidate.side, math.isqrt(n))
        self.assertLess(portfolio[5].side, 2.708)
        self.assertLess(portfolio[65].side, 8.54)

    def test_final_csv_and_neighbor_transfer_pass_official_metric(self):
        from certify import certify_csv
        portfolio = self.c.build_portfolio(80)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'candidate.csv'
            manifest = self.c.write_portfolio(path, portfolio)
            self.assertEqual(manifest['rows'], 80*81//2)
            result = certify_csv(path)
            self.assertTrue(result['valid'], [x for x in result['details'] if x['literal']['reason'] != 'ok' or x['transport']['reason'] != 'ok'])
            self.assertEqual(result['accepted_literal'], 80)
            self.assertLess(result['score_transport'], sum(math.ceil(math.sqrt(n))/math.sqrt(n)-1 for n in range(1,81)))


if __name__ == '__main__':
    unittest.main()
