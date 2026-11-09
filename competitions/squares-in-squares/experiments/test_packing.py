"""Sanity checks for the original square-packing baseline and SAT verifier."""
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "algorithms" / "packing.py"
SPEC = importlib.util.spec_from_file_location("packing", SOURCE)
import sys
packing = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = packing
SPEC.loader.exec_module(packing)


class GeometryTests(unittest.TestCase):
    def test_perfect_square(self):
        tiles = packing.grid_layout(16)
        self.assertEqual(packing.extent(tiles), 4)
        self.assertEqual(packing.validate_layout(tiles), [])

    def test_rotated_overlap(self):
        a = packing.Tile(0.5, 0.5, 0)
        b = packing.Tile(0.7, 0.5, math.pi / 4)
        self.assertEqual(packing.validate_layout([a,b]), [(0,1)])

    def test_touching_allowed(self):
        self.assertFalse(packing.validate_layout([packing.Tile(0.5,0.5), packing.Tile(1.5,0.5)]))

    def test_small_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.csv"
            self.assertEqual(packing.write_baseline(path, 3), 6)
            result = packing.validate_csv(path)
            self.assertEqual(result["rows"], 6)
            self.assertEqual(result["puzzles"], 3)
            with self.assertRaises(ValueError):
                packing.validate_csv(path, complete=True)

    def test_invalid_csv_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text("id,n,square_id,x,y,angle\n0,2,0,0.5,0.5,0\n1,2,1,0.6,0.5,0\n")
            with self.assertRaisesRegex(ValueError, "intersecting"):
                packing.validate_csv(path)


if __name__ == "__main__":
    unittest.main()
