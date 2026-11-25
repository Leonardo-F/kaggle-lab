import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SANTA = ROOT / 'competitions' / 'santa-2026'
DOCS = SANTA / 'docs'
BUILDER = DOCS / 'build_report.py'
SOURCE = DOCS / 'algorithm-evolution.md'
REPORT = SANTA / 'Santa-2026-Interactive-Report.html'
SIMULATOR = SANTA / 'src' / 'simulator.html'
LATEST = SANTA / 'submissions' / 'latest.json'
REPORTS = DOCS / 'reports'

spec = importlib.util.spec_from_file_location('santa_report_build', BUILDER)
report_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_mod)


def render(**kwargs):
    warnings = []
    content = report_mod.render_report(warnings=warnings, **kwargs)
    return content, warnings


def embedded_report_json(name):
    html = REPORT.read_text(encoding='utf-8')
    match = re.search(rf'<script type="application/json" id="{name}">(.*?)</script>', html, re.S)
    assert match, name
    return json.loads(match.group(1))


class ReportBuildTests(unittest.TestCase):
    def test_build_is_deterministic_and_matches_the_checked_in_report(self):
        first, _ = render()
        second, _ = render()
        self.assertEqual(first, second)
        self.assertEqual(REPORT.read_text(encoding='utf-8'), first)

    def test_check_accepts_current_and_rejects_missing_or_modified_output(self):
        result = subprocess.run([sys.executable, str(BUILDER), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / 'stale.html'
            stale.write_text(REPORT.read_text(encoding='utf-8') + '<!-- stale -->', encoding='utf-8')
            result = subprocess.run([sys.executable, str(BUILDER), '--check', '--output', str(stale)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stale', result.stderr)
            missing = Path(tmp) / 'missing.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--check', '--output', str(missing)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_output_option_writes_the_same_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'report.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(encoding='utf-8'), REPORT.read_text(encoding='utf-8'))

    def test_markdown_and_simulator_changes_make_the_old_report_stale(self):
        current = REPORT.read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as tmp:
            changed_md = Path(tmp) / 'algorithm-evolution.md'
            changed_md.write_text(SOURCE.read_text(encoding='utf-8') + '\n\n## 新增章节\n\n新的正文。\n',
                                  encoding='utf-8')
            content, _ = render(source=changed_md, docs_dir=DOCS)
            self.assertNotEqual(content, current)
            self.assertIn('id="新增章节"', content)

            changed_sim = Path(tmp) / 'simulator.html'
            changed_sim.write_text(SIMULATOR.read_text(encoding='utf-8') + '\n<!-- changed -->\n',
                                   encoding='utf-8')
            content, _ = render(simulator_path=changed_sim)
            self.assertNotEqual(content, current)
            self.assertIn('changed', json.loads(re.search(
                r'<script type="application/json" id="sim-source">(.*?)</script>', content, re.S).group(1)))


class ReportContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = REPORT.read_text(encoding='utf-8')

    def test_embedded_simulator_matches_source_bytes(self):
        self.assertEqual(embedded_report_json('sim-source').encode('utf-8'),
                         SIMULATOR.read_bytes())

    def test_latest_score_and_range_come_from_machine_readable_files(self):
        latest = json.loads(LATEST.read_text(encoding='utf-8'))
        scores = embedded_report_json('score-data')
        self.assertEqual(scores[-1]['score'], latest['score'])
        self.assertEqual(scores[-1]['validated'], latest['validated'])
        self.assertIn(f"{latest['score']:,}", self.html)
        for index, row in enumerate(scores, start=1):
            data = json.loads((REPORTS / f'v{index}.json').read_text(encoding='utf-8'))
            self.assertEqual(row['version'], f'V{index}')
            self.assertEqual(row['score'], data['score'])
            self.assertIn(f"{data['score']:,}", self.html)

    def test_required_interaction_anchors_exist_exactly_once(self):
        for element_id in report_mod.REQUIRED_IDS:
            self.assertEqual(len(re.findall(rf'\bid="{re.escape(element_id)}"', self.html)), 1,
                             element_id)
        self.assertIn('data-plan="before"', self.html)
        self.assertIn('data-open-plan="after"', self.html)
        self.assertIn('id="chart-detail"', self.html)
        self.assertIn('id="sim-gate"', self.html)

    def test_headings_foldouts_math_images_and_toc_are_rendered(self):
        markdown_text = SOURCE.read_text(encoding='utf-8')
        _, toc_tokens = report_mod.markdown_to_html(markdown_text, DOCS)
        for token in toc_tokens:
            self.assertIn(f'id="{token["id"]}"', self.html)
        self.assertEqual(self.html.count('<details>'), markdown_text.count('<details>'))
        self.assertEqual(self.html.count('<div class="math-block">'),
                         len(re.findall(r'^\s*```\s*math\s*$', markdown_text, re.M)))
        self.assertNotIn('<mi>&</mi>', self.html)
        self.assertNotIn('\\begin{aligned}', re.sub(r'<annotation[^>]*>.*?</annotation>', '', self.html, flags=re.S))
        figures = re.findall(r'<figure class="report-figure">.*?</figure>', self.html, re.S)
        self.assertEqual(len(figures), len(re.findall(r'^\s*!\[[^\]]*\]\([^)]+\)\s*$', markdown_text, re.M)))
        for figure in figures:
            self.assertIn('src="data:image/', figure)
            self.assertIn('<figcaption>', figure)
        self.assertTrue(all(f'#{token["id"]}' in self.html for token in toc_tokens if token['level'] == 2))
        for match in re.finditer(r'<table>', self.html):
            self.assertTrue(self.html[:match.start()].endswith('<div class="table-wrap">'),
                            'Markdown tables need a scroll container')

    def test_internal_links_resolve_and_report_has_no_network_dependencies(self):
        ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        for anchor in re.findall(r'href="#([^"]+)"', self.html):
            self.assertIn(anchor, ids)
        self.assertIsNone(re.search(
            r'<(?:script|link|img)[^>]+(?:src|href)="(?:https?:)?//', self.html))
        self.assertNotIn('url(http', self.html)
        self.assertNotIn('@import', self.html)
        self.assertNotIn('<script src=', self.html)

    def test_historical_versions_and_verified_scope_are_shown(self):
        for version in range(1, 9):
            self.assertIn(f'V{version}', self.html)
        self.assertIn('1,000 / 1,000', self.html)
        self.assertIn('不是 Kaggle 榜单成绩', self.html)


class ReportValidationTests(unittest.TestCase):
    def test_missing_historical_number_is_rejected(self):
        text = SOURCE.read_text(encoding='utf-8').replace('194,444', '194,445')
        data = report_mod.load_report_data()
        with self.assertRaisesRegex(report_mod.ReportError, '194,444'):
            report_mod.check_markdown_numbers(text, data)

    def test_broken_internal_anchor_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'algorithm-evolution.md'
            source.write_text(SOURCE.read_text(encoding='utf-8') + '\n[坏链接](#不存在的章节)\n',
                              encoding='utf-8')
            with self.assertRaisesRegex(report_mod.ReportError, 'missing anchor'):
                render(source=source, docs_dir=DOCS)

    def test_images_must_stay_inside_the_docs_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'algorithm-evolution.md'
            source.write_text(SOURCE.read_text(encoding='utf-8') + '\n![x](../outside.png)\n',
                              encoding='utf-8')
            with self.assertRaisesRegex(report_mod.ReportError, 'missing image|escapes'):
                render(source=source, docs_dir=DOCS)

    def test_math_is_rendered_to_offline_mathml(self):
        mathml = report_mod.render_math(r'\begin{aligned}a&=b\\c&=d\end{aligned}', 'block')
        self.assertIn('<math', mathml)
        self.assertIn('<mtable>', mathml)
        self.assertIn('<annotation encoding="application/x-tex">', mathml)
        self.assertIn('display="block"', mathml)


if __name__ == '__main__':
    unittest.main()
