import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify import verify


class VerifyTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.puzzles = Path(directory.name) / "puzzles.csv"
        self.puzzles.write_text(
            'id,starting_values,targets,value_limit,registers\n'
            'p,"[12,5]",[7],30,48\n'
        )
        self.answer = self.puzzles.with_name("answer.csv")

    def write_answer(self, *rows):
        with self.answer.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("id", "program"))
            writer.writerows(rows)

    def test_valid_exact_program(self):
        self.write_answer(("p", '[["-",0,1,2]]'))
        report = verify(self.puzzles, self.answer)
        self.assertEqual((report["validated"], report["score"]), (1, 1))

    def test_rejects_illegal_programs(self):
        for program, error in [
            ('[["/",0,1,2]]', "nonexact division"),
            ('[["-",3,1,2]]', "undefined register"),
            ('[["-",0,1,48]]', "invalid register"),
            ('[["-",true,1,2]]', "invalid register"),
            ('[["*",0,1,2]]', "result out of range"),
            ('[]', "missing"),
            ('[["-",0,1,2,3]]', "invalid instruction"),
            ('[' + ','.join(['["-",0,1,2]'] * 4097) + ']', "program length"),
            ('é' * 65536 + '[]', "program bytes"),
        ]:
            with self.subTest(error=error):
                self.write_answer(("p", program))
                with self.assertRaisesRegex(ValueError, error):
                    verify(self.puzzles, self.answer)

    def test_requires_exact_unique_ids(self):
        for rows in [(), (("q", "[]"),), (("p", "[]"), ("p", "[]"))]:
            with self.subTest(rows=rows):
                self.write_answer(*rows)
                with self.assertRaisesRegex(ValueError, "puzzle IDs"):
                    verify(self.puzzles, self.answer)
