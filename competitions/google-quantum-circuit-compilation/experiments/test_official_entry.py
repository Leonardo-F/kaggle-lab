"""Fail-closed prerequisites; full verifier integration needs competition data."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'algorithms' / 'verify_official.py'


class OfficialEntryTests(unittest.TestCase):
    def test_missing_official_data_cannot_produce_a_success_receipt(self):
        self.assertTrue(SOURCE.is_file(), 'official verifier entry is missing')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root/'report.json'
            report.write_text('{"official_circuit_verified": true}')
            result = subprocess.run([sys.executable, str(SOURCE), '--data-root', str(root/'absent'),
                                     '--submission', str(root/'absent'), '--report', str(report)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            receipt = json.loads(report.read_text())
            self.assertFalse(receipt['official_circuit_verified'])
            self.assertEqual(receipt['status'], 'blocked-or-failed')

    def test_duplicate_formats_and_angle_number_gaps_are_rejected(self):
        self.assertTrue(SOURCE.is_file(), 'official verifier entry is missing')
        spec = importlib.util.spec_from_file_location('verify_official', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'invsqrt.kmb').write_bytes(b'fixture')
            (root/'invsqrt.kmx').write_bytes(b'fixture')
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                module.circuit_path(root,'invsqrt')
            folder=root/'dfthcsos';folder.mkdir()
            (folder/'angle_k_0.kmb').write_bytes(b'fixture')
            (folder/'angle_k_2.kmb').write_bytes(b'fixture')
            with self.assertRaisesRegex(ValueError, 'continuous'):
                module.angle_paths(folder)


if __name__ == '__main__':
    unittest.main()
