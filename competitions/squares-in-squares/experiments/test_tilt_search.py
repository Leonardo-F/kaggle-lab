import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'algorithms'))
from certify import certify_csv
from constructions import build_portfolio, write_portfolio
from strip_search import search_portfolio
from tilt_search import StripWitness, add_rectangular_cores, critical_sides, improve, make_layout


class TiltSearchTests(unittest.TestCase):
    def test_threshold_and_export_match_at_eighteen(self):
        w = StripWitness(4, 28.0, .7913622812165997, 2, 3)
        threshold = critical_sides(w)[17]
        self.assertEqual(len(make_layout(w, threshold + 1e-8)), 18)
        self.assertLess(len(make_layout(w, threshold - 1e-6)), 18)
        with tempfile.TemporaryDirectory() as directory:
            witness = Path(directory) / 'witness.tsv'
            witness.write_text('4 4.890625 18 28 .7913622812165997 2 3\n')
            base = search_portfolio(build_portfolio(18))
            new = improve(base, witness)
            self.assertLess(new[18].side, base[18].side - .029)
            csv = Path(directory) / 'tilt.csv'
            write_portfolio(csv, new)
            self.assertTrue(certify_csv(csv)['valid'])

    def test_off_centre_block_beats_grid_and_survives_transport(self):
        previous = search_portfolio(build_portfolio(26))
        new = add_rectangular_cores(previous)
        self.assertAlmostEqual(new[26].side, 3.5 + 3/math.sqrt(2), places=5)
        self.assertEqual(sum(t.angle != 0 for t in new[26].tiles), 9)
        self.assertLess(new[26].side, previous[26].side - .06)
        self.assertEqual(new[25].side, 5)
        with tempfile.TemporaryDirectory() as directory:
            csv = Path(directory) / 'core.csv'
            write_portfolio(csv, new)
            self.assertTrue(certify_csv(csv)['valid'])


if __name__ == '__main__':
    unittest.main()
