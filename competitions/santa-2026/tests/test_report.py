import copy
import hashlib
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
REFACTOR_REPORT = REPORTS / 'v8-refactor.json'

spec = importlib.util.spec_from_file_location('santa_report_build', BUILDER)
report_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_mod)

DATASET_SHA256 = 'b0c70d849eca078a0e1cf9a4f7b47fd40b7435663f6f84de6725f84724500428'
V8_SCORE = 194_444
SIMULATED_SCORE = 185_000
NEW_SUBMISSION_TEXT = 'puzzle_id,program\nscored_0001,"0,1"\n'


def render(**kwargs):
    warnings = []
    content = report_mod.render_report(warnings=warnings, **kwargs)
    return content, warnings


def extract_json(html_text, name):
    match = re.search(rf'<script type="application/json" id="{name}">(.*?)</script>',
                      html_text, re.S)
    assert match, name
    return json.loads(match.group(1))


def embedded_report_json(name):
    return extract_json(REPORT.read_text(encoding='utf-8'), name)


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def formal_payload(version, score, submission_sha256='0' * 64, **overrides):
    """A complete formal vN.json fixture with the current flat schema."""
    payload = {
        'version': version,
        'puzzles': 1000,
        'validated': 1000,
        'score': score,
        'max_steps': 500,
        'submission_sha256': submission_sha256,
        'puzzles_sha256': DATASET_SHA256,
    }
    payload.update(overrides)
    return payload


def make_reports_env(directory, reports, latest_version, *,
                     csv_text=NEW_SUBMISSION_TEXT, csv_name='best.csv'):
    """Write a reports/ directory plus submissions/latest.json and its CSV."""
    directory = Path(directory)
    reports_dir = directory / 'reports'
    submissions_dir = directory / 'submissions'
    reports_dir.mkdir(parents=True)
    submissions_dir.mkdir(parents=True)
    csv_path = submissions_dir / csv_name
    csv_path.write_text(csv_text, encoding='utf-8')
    submission_sha256 = sha256_text(csv_text)
    payloads = {version: copy.deepcopy(payload) for version, payload in reports.items()}
    payloads[latest_version]['submission_sha256'] = submission_sha256
    for version, payload in payloads.items():
        (reports_dir / f'{version}.json').write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    latest = {
        'version': latest_version,
        'score': payloads[latest_version]['score'],
        'validated': payloads[latest_version]['validated'],
        'submission_sha256': submission_sha256,
        'puzzles_sha256': payloads[latest_version]['puzzles_sha256'],
        'local_filename': csv_name,
        'report': f'../reports/{latest_version}.json',
    }
    latest_path = submissions_dir / 'latest.json'
    latest_path.write_text(json.dumps(latest, indent=2, ensure_ascii=False) + '\n',
                           encoding='utf-8')
    return reports_dir, latest_path


def markdown_row(prefix):
    for line in SOURCE.read_text(encoding='utf-8').splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f'missing Markdown row starting with {prefix!r}')


class ReportBuildTests(unittest.TestCase):
    def test_build_is_deterministic_and_the_cli_writes_the_same_page(self):
        first, _ = render()
        second, _ = render()
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'report.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(encoding='utf-8'), first)
        # The one checked-in page is rebuilt once in the integration commit; its
        # currency is enforced by `build_report.py --check` in CI, not here.

    def test_check_accepts_a_fresh_page_and_rejects_missing_or_modified_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / 'fresh.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--output', str(fresh)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([sys.executable, str(BUILDER), '--check',
                                     '--output', str(fresh)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('up to date', result.stdout)

            stale = Path(tmp) / 'stale.html'
            stale.write_text(fresh.read_text(encoding='utf-8') + '<!-- stale -->',
                             encoding='utf-8')
            result = subprocess.run([sys.executable, str(BUILDER), '--check',
                                     '--output', str(stale)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stale', result.stderr)
            missing = Path(tmp) / 'missing.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--check',
                                     '--output', str(missing)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_output_option_writes_the_same_report(self):
        expected, _ = render()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'report.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(encoding='utf-8'), expected)

    def test_markdown_and_simulator_changes_make_the_old_report_stale(self):
        current, _ = render()
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
            self.assertIn('changed', extract_json(content, 'sim-source'))


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
        self.assertNotIn('\\begin{aligned}', re.sub(r'<annotation[^>]*>.*?</annotation>', '',
                                                    self.html, flags=re.S))
        figures = re.findall(r'<figure class="report-figure">.*?</figure>', self.html, re.S)
        self.assertEqual(len(figures), len(re.findall(r'^\s*!\[[^\]]*\]\([^)]+\)\s*$',
                                                      markdown_text, re.M)))
        for figure in figures:
            self.assertIn('src="data:image/', figure)
            self.assertIn('<figcaption>', figure)
        self.assertTrue(all(f'#{token["id"]}' in self.html for token in toc_tokens
                            if token['level'] == 2))
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


class OptionalRefactorReportTests(unittest.TestCase):
    """The V8 refactor report is optional and fixed to the archived v8.json."""

    @classmethod
    def setUpClass(cls):
        cls.latest = json.loads(LATEST.read_text(encoding='utf-8'))
        cls.archived = json.loads((REPORTS / 'v8.json').read_text(encoding='utf-8'))
        cls.refactor = json.loads(REFACTOR_REPORT.read_text(encoding='utf-8'))

    def payload(self):
        return copy.deepcopy(self.refactor)

    def render_with(self, payload=None, raw=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'v8-refactor.json'
            if raw is not None:
                path.write_text(raw, encoding='utf-8')
            elif payload is not None:
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            content, _ = render(refactor_path=path)
        return content

    def assert_rejected(self, payload):
        content = self.render_with(payload=payload)
        self.assertIn('校验未通过', content)
        self.assertIn('class="refactor-bad"', content)
        self.assertNotIn('class="refactor-ok"', content)
        self.assertNotIn('报告通过本页一致性校验', content)
        return content

    def test_archived_v8_report_is_the_fixed_reference(self):
        data = report_mod.load_report_data()
        archived = data['reports']['v8']
        self.assertEqual(archived['score'], self.archived['score'])
        self.assertEqual([row['version'] for row in data['historical']],
                         [f'v{number}' for number in range(1, 10)])
        status = report_mod.load_refactor_status(REFACTOR_REPORT, archived)
        self.assertEqual(status['state'], 'valid', status['reasons'])

    def test_real_refactor_report_passes_against_the_fixed_v8_report(self):
        status = report_mod.load_refactor_status(REFACTOR_REPORT, self.archived)
        self.assertEqual(status['state'], 'valid', status['reasons'])
        self.assertEqual(status['data']['score'], V8_SCORE)
        self.assertIsNot(status['data'], self.refactor)

    def test_missing_fixed_v8_evidence_is_reported_without_fallback(self):
        status = report_mod.load_refactor_status(REFACTOR_REPORT, None)
        self.assertEqual(status['state'], 'invalid')
        self.assertTrue(any('V8' in reason for reason in status['reasons']))
        panel = report_mod.render_refactor_panel(status)
        self.assertIn('class="refactor-bad"', panel)
        self.assertNotIn('class="refactor-ok"', panel)
        self.assertIn('不会回退到当前最佳版本', panel)

    def test_missing_optional_report_builds_and_shows_pending_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            content, _ = render(refactor_path=Path(tmp) / 'v8-refactor.json')
        self.assertIn('尚未生成', content)
        self.assertIn('id="refactor-status"', content)
        self.assertNotIn('class="refactor-ok"', content)
        self.assertNotIn('class="refactor-bad"', content)
        self.assertIn('原始 V8 全量实验报告', content)

    def test_valid_report_matches_original_v8_and_adds_no_new_score_nodes(self):
        content = self.render_with(payload=self.payload())
        self.assertIn('报告通过本页一致性校验：与原始 V8 报告一致', content)
        self.assertIn('本页只做记录一致性核查，未执行求解', content)
        self.assertIn(f'等价重构复现：{V8_SCORE:,} 步', content)
        self.assertNotIn('class="refactor-bad"', content)
        scores = extract_json(content, 'score-data')
        self.assertEqual([row['version'] for row in scores],
                         [f'V{number}' for number in range(1, 10)])
        latest = json.loads(LATEST.read_text(encoding='utf-8'))
        self.assertEqual(scores[-1]['score'], latest['score'])
        self.assertEqual(scores[-1]['version'], latest['version'].upper())
        self.assertNotIn('V8 Refactored', content.split('id="score-data"')[1])

    def test_v8_acceptance_survives_a_simulated_v10_best_version(self):
        # Test-only fixtures: a future V10 formal report with a different but
        # valid CSV and latest pointer.  Nothing is written under docs/reports.
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            reports = {
                f'v{number}': json.loads(
                    (REPORTS / f'v{number}.json').read_text(encoding='utf-8'))
                for number in range(1, 10)
            }
            reports['v10'] = formal_payload('v10', SIMULATED_SCORE)
            reports_dir, latest_path = make_reports_env(tmpdir, reports, 'v10')
            markdown_text = SOURCE.read_text(encoding='utf-8')
            v9_row = markdown_row('| V9 |')
            v10_row = ('| V10 | 模拟的未来版本（仅测试夹具） | 185,000 | 9,444 | 0/0/0 | '
                       '[测试夹具](reports/v10.json) |')
            markdown_text = markdown_text.replace(v9_row, v9_row + '\n' + v10_row)
            source = tmpdir / 'algorithm-evolution.md'
            source.write_text(markdown_text, encoding='utf-8')
            content, _ = render(source=source, docs_dir=DOCS,
                                reports_dir=reports_dir, latest_path=latest_path)
        self.assertIn('V10 Final 全量独立验证', content)
        self.assertIn('185,000', content)
        self.assertIn('报告通过本页一致性校验：与原始 V8 报告一致', content)
        self.assertIn(f'等价重构复现：{V8_SCORE:,} 步', content)
        self.assertNotIn(f'等价重构复现：{SIMULATED_SCORE:,} 步', content)
        self.assertNotIn('class="refactor-bad"', content)
        scores = extract_json(content, 'score-data')
        self.assertEqual([row['version'] for row in scores],
                         [f'V{number}' for number in range(1, 11)])
        self.assertEqual(scores[7], {'version': 'V8', 'score': V8_SCORE,
                                     'validated': 1000})
        self.assertEqual(scores[8]['version'], 'V9')
        self.assertEqual(scores[-1], {'version': 'V10', 'score': SIMULATED_SCORE,
                                      'validated': 1000})
        self.assertNotIn('V8 Refactored', content.split('id="score-data"')[1])

    def test_tampered_stage_total_is_rejected_even_with_true_flags(self):
        payload = self.payload()
        payload['refactored_run']['stage_totals']['v8'] += 1
        content = self.assert_rejected(payload)
        self.assertIn('stage_totals', content)

    def test_top_level_and_nested_hash_conflict_is_rejected(self):
        payload = self.payload()
        payload['submission_sha256'] = 'f' * 64
        content = self.assert_rejected(payload)
        self.assertIn('submission_sha256', content)
        self.assertIn('与原始 V8 报告不一致', content)

    def test_commit_conflicts_and_unresolvable_short_sha_are_rejected(self):
        payload = self.payload()
        payload['baseline_commit'] = report_mod.DOCUMENTED_COMMITS['0ec0ec0']
        content = self.assert_rejected(payload)
        self.assertIn('顶层 baseline_commit 与嵌套 baseline.commit 不一致', content)

        payload = self.payload()
        payload['refactor_commit'] = 'deadbee'
        payload['refactor']['commit'] = 'deadbee'
        content = self.assert_rejected(payload)
        self.assertIn('无法在本地记录中唯一解析', content)

    def test_metric_diff_count_nonzero_is_rejected(self):
        payload = self.payload()
        payload['equivalence']['per_puzzle_metric_diff_count'] = 3
        content = self.assert_rejected(payload)
        self.assertIn('per_puzzle_metric_diff_count=3 必须为 0', content)

    def test_puzzle_count_mismatch_is_rejected(self):
        payload = self.payload()
        payload['refactored_run']['puzzles'] = 999
        payload['tests']['full_equivalence']['programs_identical'] = 999
        payload['refactored_run']['improved'] = 774
        content = self.assert_rejected(payload)
        self.assertIn('puzzles=999', content)
        self.assertIn('improved+unchanged+worse=999', content)

    def test_missing_nested_evidence_is_rejected(self):
        payload = self.payload()
        del payload['baseline']['archived_stage_totals']
        content = self.assert_rejected(payload)
        self.assertIn('archived_stage_totals', content)

        payload = self.payload()
        del payload['refactored_run']['checkpoint']
        content = self.assert_rejected(payload)
        self.assertIn('checkpoint', content)

    def test_test_failures_and_group_count_conflicts_are_rejected(self):
        payload = self.payload()
        payload['tests']['failed'] = 1
        content = self.assert_rejected(payload)
        self.assertIn('tests.failed 必须为 0', content)

        payload = self.payload()
        payload['tests']['santa_python']['tests'] = 44
        content = self.assert_rejected(payload)
        self.assertIn('分组测试记录合计 66', content)

    def test_practice_dataset_must_stay_separate_from_formal_puzzles(self):
        payload = self.payload()
        payload['practice_run']['puzzles_sha256'] = payload['baseline']['puzzles_sha256']
        content = self.assert_rejected(payload)
        self.assertIn('practice_run 的题目 SHA-256 与正式题相同', content)

    def test_unverified_items_and_failed_acceptance_are_rejected(self):
        payload = self.payload()
        payload['unverified'] = ['尚未完成全量复跑']
        self.assertIn('未验证项', self.render_with(payload=payload))

        payload = self.payload()
        payload['status'] = 'failed'
        content = self.assert_rejected(payload)
        self.assertIn('status 必须为', content)

    def test_hash_format_and_bool_counts_are_rejected(self):
        payload = self.payload()
        payload['submission_sha256'] = 'not-a-sha'
        content = self.assert_rejected(payload)
        self.assertIn('64 位', content)

        payload = self.payload()
        payload['puzzles'] = True
        content = self.assert_rejected(payload)
        self.assertIn('puzzles', content)

    def test_malformed_json_is_reported_as_failure(self):
        content = self.render_with(raw='{not json')
        self.assertIn('校验未通过', content)
        self.assertIn('无法读取或解析', content)

    def test_build_does_not_touch_latest_or_archived_reports(self):
        latest_before = LATEST.read_bytes()
        archived_before = (REPORTS / 'v8.json').read_bytes()
        refactor_before = REFACTOR_REPORT.read_bytes()
        self.render_with(payload=self.payload())
        self.assertEqual(LATEST.read_bytes(), latest_before)
        self.assertEqual((REPORTS / 'v8.json').read_bytes(), archived_before)
        self.assertEqual(REFACTOR_REPORT.read_bytes(), refactor_before)


class FormalReportValidationTests(unittest.TestCase):
    """Formal vN.json reports, the latest pointer and the archived CSV hash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._case = 0

    def tearDown(self):
        self._tmp.cleanup()

    def env(self, reports, latest_version, **kwargs):
        self._case += 1
        return make_reports_env(self.tmp / f'case{self._case}', reports,
                                latest_version, **kwargs)

    def load(self, reports, latest_version, **kwargs):
        reports_dir, latest_path = self.env(reports, latest_version, **kwargs)
        return report_mod.load_report_data(reports_dir, latest_path)

    def rewrite_latest(self, reports_dir, latest_path, **changes):
        latest = json.loads(latest_path.read_text(encoding='utf-8'))
        latest.update(changes)
        latest_path.write_text(json.dumps(latest, indent=2), encoding='utf-8')
        return reports_dir, latest_path

    def test_history_is_numerically_sorted_and_full_payloads_are_exposed(self):
        data = self.load({
            'v1': formal_payload('v1', 250_642),
            'v9': formal_payload('v9', 198_000),
            'v10': formal_payload('v10', 190_000),
        }, 'v10')
        self.assertEqual([row['version'] for row in data['historical']],
                         ['v1', 'v9', 'v10'])
        self.assertEqual(data['reports']['v10']['score'], 190_000)
        self.assertEqual(data['latest_report'], data['reports']['v10'])
        self.assertEqual(data['submission'].name, 'best.csv')
        self.assertEqual(data['compatibility_notes'], [])

    def test_formal_version_must_match_file_name(self):
        with self.assertRaisesRegex(report_mod.ReportError, 'must match'):
            self.load({'v1': formal_payload('v1', 250_642),
                       'v9': formal_payload('v8', 190_000)}, 'v9')

    def test_duplicate_numeric_versions_are_rejected(self):
        with self.assertRaisesRegex(report_mod.ReportError, 'unique'):
            self.load({'v9': formal_payload('v9', 190_000),
                       'v09': formal_payload('v09', 191_000)}, 'v9')

    def test_invalid_counts_scores_and_bool_values_are_rejected(self):
        cases = (
            ('negative score', {'score': -1}, 'score'),
            ('zero puzzles', {'puzzles': 0}, 'puzzles'),
            ('validated above puzzles', {'validated': 1001}, 'validated'),
            ('bool score', {'score': True}, 'integer'),
            ('bool validated', {'validated': True}, 'integer'),
            ('non-hex submission hash', {'submission_sha256': 'xyz'}, 'SHA-256'),
        )
        for label, overrides, message in cases:
            with self.subTest(label):
                broken = formal_payload('v1', 250_642)
                broken.update(overrides)
                reports = {'v1': broken, 'v2': formal_payload('v2', 240_000)}
                with self.assertRaisesRegex(report_mod.ReportError, message):
                    self.load(reports, 'v2')

    def test_latest_pointer_must_match_the_report_fields(self):
        reports_dir, latest_path = self.env({
            'v1': formal_payload('v1', 250_642),
            'v2': formal_payload('v2', 240_000),
        }, 'v2')
        latest = json.loads(latest_path.read_text(encoding='utf-8'))
        for field, value in (
            ('score', latest['score'] + 1),
            ('validated', latest['validated'] - 1),
            ('submission_sha256', 'f' * 64),
            ('puzzles_sha256', 'e' * 64),
            ('version', 'v1'),
        ):
            with self.subTest(field):
                mutated = dict(latest)
                mutated[field] = value
                latest_path.write_text(json.dumps(mutated), encoding='utf-8')
                with self.assertRaises(report_mod.ReportError):
                    report_mod.load_report_data(reports_dir, latest_path)
        latest_path.write_text(json.dumps(latest), encoding='utf-8')
        report_mod.load_report_data(reports_dir, latest_path)

    def test_latest_and_best_report_must_be_complete(self):
        reports_dir, latest_path = self.env({
            'v1': formal_payload('v1', 250_642),
            'v2': formal_payload('v2', 240_000),
        }, 'v2')
        original = json.loads(latest_path.read_text(encoding='utf-8'))
        for field in ('submission_sha256', 'puzzles_sha256'):
            with self.subTest(field):
                mutated = dict(original)
                del mutated[field]
                latest_path.write_text(json.dumps(mutated), encoding='utf-8')
                with self.assertRaisesRegex(report_mod.ReportError, field):
                    report_mod.load_report_data(reports_dir, latest_path)
        latest_path.write_text(json.dumps(original), encoding='utf-8')
        report_path = reports_dir / 'v2.json'
        report = json.loads(report_path.read_text(encoding='utf-8'))
        del report['puzzles_sha256']
        report_path.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaisesRegex(report_mod.ReportError, 'puzzles_sha256'):
            report_mod.load_report_data(reports_dir, latest_path)

    def test_submission_csv_is_required_and_hash_checked(self):
        reports_dir, latest_path = self.env({
            'v1': formal_payload('v1', 250_642),
            'v2': formal_payload('v2', 240_000),
        }, 'v2')
        csv_path = latest_path.parent / 'best.csv'
        original = csv_path.read_text(encoding='utf-8')
        csv_path.unlink()
        with self.assertRaisesRegex(report_mod.ReportError, 'missing submission CSV'):
            report_mod.load_report_data(reports_dir, latest_path)
        csv_path.write_text(original + '<!-- changed -->\n', encoding='utf-8')
        with self.assertRaisesRegex(report_mod.ReportError, 'SHA-256 does not match'):
            report_mod.load_report_data(reports_dir, latest_path)

    def test_reports_must_share_one_dataset_identity(self):
        reports = {
            'v1': formal_payload('v1', 250_642, puzzles_sha256='a' * 64),
            'v2': formal_payload('v2', 240_000),
        }
        with self.assertRaisesRegex(report_mod.ReportError, 'dataset SHA-256'):
            self.load(reports, 'v2')


class MarkdownScoreTableTests(unittest.TestCase):
    """The formal score table pairs each version with its own score."""

    @classmethod
    def setUpClass(cls):
        cls.data = report_mod.load_report_data()
        cls.text = SOURCE.read_text(encoding='utf-8')

    def test_swapping_two_version_scores_is_rejected(self):
        swapped = (self.text.replace('250,642', '__SWAP__')
                   .replace('236,449', '250,642')
                   .replace('__SWAP__', '236,449'))
        # A naive "number appears somewhere in the text" check would pass here.
        self.assertIn('250,642', swapped)
        self.assertIn('236,449', swapped)
        with self.assertRaisesRegex(report_mod.ReportError, 'V1|V2|250,642|236,449'):
            report_mod.check_markdown_numbers(swapped, self.data)

    def test_missing_or_extra_version_row_is_rejected(self):
        v3_row = markdown_row('| V3 |')
        without_v3 = self.text.replace(v3_row + '\n', '')
        with self.assertRaisesRegex(report_mod.ReportError, '缺少正式报告的版本: V3'):
            report_mod.check_markdown_numbers(without_v3, self.data)

        v9_row = markdown_row('| V9 |')
        fake_v10 = ('| V10 | 模拟未来版本（仅测试夹具） | 185,000 | 9,444 | 0/0/0 | '
                    '[测试夹具](reports/v10.json) |')
        with_fake = self.text.replace(v9_row, v9_row + '\n' + fake_v10)
        with self.assertRaisesRegex(report_mod.ReportError, '没有正式报告的版本: V10'):
            report_mod.check_markdown_numbers(with_fake, self.data)

    def test_number_in_wrong_version_cell_is_rejected(self):
        v5_row = markdown_row('| V5 |')
        broken = self.text.replace(v5_row, v5_row.replace('216,404', '216,405', 1))
        self.assertIn('216,404', broken)
        with self.assertRaisesRegex(report_mod.ReportError, 'V5'):
            report_mod.check_markdown_numbers(broken, self.data)

    def test_formal_score_table_is_required(self):
        without_marker = self.text.replace('独立验证记录', '验证记录（测试移除标记）')
        with self.assertRaisesRegex(report_mod.ReportError, '正式成绩表'):
            report_mod.check_markdown_numbers(without_marker, self.data)


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
