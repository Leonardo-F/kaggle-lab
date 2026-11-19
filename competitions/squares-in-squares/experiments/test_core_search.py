import math
from pathlib import Path
import sys
import unittest

ALGORITHMS = Path(__file__).resolve().parents[1] / 'algorithms'
sys.path.insert(0, str(ALGORITHMS))

from certify import _evaluate
from core_search import read_witnesses
from packing import extent


class RectangularCoreTests(unittest.TestCase):
    def test_rectangular_witnesses_reconstruct_and_certify(self):
        witnesses = dict((n, core) for n, core in read_witnesses(ALGORITHMS / 'core_witnesses.tsv')
                         if core.p != core.q)
        for n, bound in ((18, 2 + 2*math.sqrt(2)), (41, 2 + 7/math.sqrt(2))):
            with self.subTest(n=n):
                core = witnesses[n]
                self.assertAlmostEqual(core.side, bound)
                tiles = core.layout()[:n]
                self.assertEqual(len(tiles), n)
                self.assertLess(extent(tiles), math.ceil(math.sqrt(n)))
                rows = [dict(id=str(i), n=str(n), square_id=str(i),
                             x=repr(tile.x), y=repr(tile.y), angle=repr(tile.angle))
                        for i, tile in enumerate(tiles)]
                self.assertEqual(_evaluate((n, rows))['reason'], 'ok')
