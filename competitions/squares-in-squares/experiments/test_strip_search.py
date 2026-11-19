import math
from pathlib import Path
import sys
import tempfile
import unittest

ALGORITHMS = Path(__file__).resolve().parents[1] / 'algorithms'
sys.path.insert(0, str(ALGORITHMS))
from certify import certify_csv
from constructions import build_portfolio, write_portfolio
from packing import extent, validate_layout


class StripSearchTests(unittest.TestCase):
    def test_offset_diagonal_rows_improve_eighteen_after_csv_round_trip(self):
        from strip_search import search_portfolio

        baseline = build_portfolio(18)
        candidate = search_portfolio(baseline, method='diagonal')
        self.assertEqual(baseline[18].side, 5)
        self.assertAlmostEqual(candidate[18].side, 3.5 + math.sqrt(2), places=5)
        # Two tilted rows of lengths 4 and 5, plus opposite corners of 3 and 6.
        self.assertEqual(sum(t.angle != 0 for t in candidate[18].tiles), 9)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'packing.csv'
            write_portfolio(path, candidate)
            result = certify_csv(path)
        self.assertTrue(result['valid'])
        self.assertEqual(result['accepted_transport'], 18)

    def test_outer_border_transfers_the_sixty_five_square_layout(self):
        from strip_search import search_portfolio

        baseline = build_portfolio(82)
        winner = search_portfolio(baseline, method='border')[82]
        self.assertEqual(winner.parameters['seed_n'], 65)
        self.assertEqual(len(winner.tiles), 82)
        self.assertFalse(validate_layout(winner.tiles))
        self.assertAlmostEqual(extent(winner.tiles), 6 + 5/math.sqrt(2), places=5)
        self.assertLess(winner.side, baseline[82].side - 0.4)

    def test_combining_methods_retains_the_base_and_both_improvements(self):
        from strip_search import search_portfolio

        baseline = build_portfolio(120)
        diagonal = search_portfolio(baseline, method='diagonal')
        border = search_portfolio(baseline, method='border')
        combined = search_portfolio(baseline)
        self.assertEqual(combined.keys(), baseline.keys())
        self.assertLess(combined[18].side, border[18].side)
        self.assertLess(combined[82].side, diagonal[82].side)
        for n, candidate in combined.items():
            self.assertEqual(len(candidate.tiles), n)
            self.assertLessEqual(candidate.side, min(diagonal[n].side, border[n].side) + 1e-6)
            if math.isqrt(n)**2 == n:
                self.assertEqual(candidate.side, math.isqrt(n))


if __name__ == '__main__':
    unittest.main()
