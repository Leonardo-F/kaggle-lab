import base64
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / 'web' / 'build' / 'build.py'


class BundleTests(unittest.TestCase):
    def test_generated_bundle_contains_original_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'bundle.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            content = output.read_text(encoding='utf-8')
            self.assertIn('正方形装箱', content)
            self.assertIn('Santa 2026', content)
            self.assertIn('srcdoc', content)
            embedded = json.loads(re.search(r'const documents = (.*);', content).group(1))
            for key, name in [('square', 'competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html'),
                              ('santa', 'competitions/santa-2026/src/simulator.html')]:
                self.assertEqual(base64.b64decode(embedded[key]), (ROOT / name).read_bytes())

    def test_checked_in_bundle_is_up_to_date(self):
        result = subprocess.run([sys.executable, str(BUILDER), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
