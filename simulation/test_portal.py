import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PortalTest(unittest.TestCase):
    def test_portal_has_two_competition_pages(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for marker in ('id="squares"', 'id="santa"', "正方形装箱", "Santa 2026", "Google 量子"):
            self.assertIn(marker, html)
        sources = re.findall(r'(?:src|data-src)="(competitions/[^"]+)"', html)
        self.assertEqual(len(set(sources)), 2)
        for source in set(sources):
            self.assertTrue((ROOT / source).is_file(), source)


if __name__ == "__main__":
    unittest.main()
