"""Final CSV tests: official geometry and the pandas transport are both gates."""
import importlib.util
from pathlib import Path
import sys
import subprocess
import json
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'algorithms' / 'certify.py'


class CertificationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'official CSV certification has not been implemented')
        spec = importlib.util.spec_from_file_location('packing_certify', SOURCE)
        self.certify = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.certify
        spec.loader.exec_module(self.certify)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def csv(self, text):
        path = Path(self.temp.name) / 'submission.csv'
        path.write_text('id,n,square_id,x,y,angle\n' + text)
        return path

    def test_exact_grid_contact_is_accepted_by_both_routes(self):
        result = self.certify.certify_csv(self.csv('0,2,0,0.5,0.5,0\n1,2,1,1.5,0.5,0\n'))
        self.assertTrue(result['valid'])
        self.assertEqual(result['accepted_literal'], 1)
        self.assertEqual(result['accepted_transport'], 1)
        self.assertEqual(result['details'][0]['literal']['reason'], 'ok')

    def test_microscopic_overlap_is_rejected_despite_grid_penalty_score(self):
        report = self.certify.certify_csv(self.csv('0,2,0,0.5,0.5,0\n1,2,1,1.499999999999999999999999999999,0.5,0\n'))
        self.assertFalse(report['valid'])
        self.assertEqual(report['accepted_literal'], 0)
        self.assertIsNone(report['details'][0]['literal']['L'])

    def test_literal_clearance_can_be_destroyed_by_numeric_transport(self):
        result = self.certify.certify_csv(self.csv('0,2,0,3e-18,0.5,0\n1,2,1,1.00000000000000000301,0.5,0\n'))
        self.assertEqual(result['accepted_literal'], 1)
        self.assertEqual(result['accepted_transport'], 0)
        self.assertFalse(result['valid'])

    def test_structural_errors_and_incomplete_files_are_not_scored_as_valid(self):
        for text in ('0,2,0,.5,.5,0\n0,2,1,1.5,.5,0\n',
                     '0,2,0,.5,.5,0\n1,2,0,1.5,.5,0\n',
                     '0,2,0,.5,.5,0\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.certify.certify_csv(self.csv(text))
        with self.assertRaisesRegex(ValueError, '1000'):
            self.certify.certify_csv(self.csv('0,1,0,.5,.5,0\n'), complete=True)

    def test_report_fingerprints_written_bytes(self):
        import hashlib
        path = self.csv('0,1,0,.5,.5,0\n')
        result = self.certify.certify_csv(path)
        self.assertEqual(result['csv_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result['metric_version'], 20)
        self.assertEqual(len(result['metric_sha256']), 64)

    def test_cli_failed_rerun_replaces_stale_success_receipt(self):
        path = self.csv('0,2,0,.5,.5,0\n')
        report = Path(self.temp.name)/'report.json'
        report.write_text('{"valid":true,"csv_sha256":"old-file"}')
        result = subprocess.run([sys.executable, str(SOURCE), '--input', str(path),
                                 '--report', str(report), '--workers', '1'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(report.read_text())
        self.assertFalse(receipt['valid'])
        self.assertIn('error', receipt)
        self.assertNotEqual(receipt['csv_sha256'], 'old-file')

    def test_report_cannot_overwrite_input(self):
        path = self.csv('0,1,0,.5,.5,0\n')
        original = path.read_bytes()
        result = subprocess.run([sys.executable, str(SOURCE), '--input', str(path),
                                 '--report', str(path), '--workers', '1'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
