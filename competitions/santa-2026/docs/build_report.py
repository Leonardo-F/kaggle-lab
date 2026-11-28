#!/usr/bin/env python3
"""Build the single-file Santa 2026 interactive learning report.

The learning text lives only in ``algorithm-evolution.md``.  This script turns
that Markdown into the checked-in ``Santa-2026-Interactive-Report.html`` using
``report_template.html`` for the page frame, existing interactive demos and
CSS.  Math is rendered at build time to MathML, so the report needs no network
and no client-side renderer.

Usage (from the repository root)::

    python competitions/santa-2026/docs/build_report.py
    python competitions/santa-2026/docs/build_report.py --check
    python competitions/santa-2026/docs/build_report.py --output /tmp/report.html
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import sys
from pathlib import Path

try:
    import markdown
    from markdown.extensions.toc import slugify_unicode
    from latex2mathml.converter import convert as latex_to_mathml
except ImportError as exc:  # pragma: no cover - depends on the local environment
    raise SystemExit(
        "build_report.py needs the pinned documentation dependencies. "
        "Run: python -m pip install -r competitions/santa-2026/docs/requirements-docs.txt\n"
        f"Import error: {exc}"
    ) from exc

HERE = Path(__file__).resolve().parent
SANTA = HERE.parent
REPO = SANTA.parents[1]
SOURCE_MD = HERE / "algorithm-evolution.md"
TEMPLATE = HERE / "report_template.html"
SIMULATOR = SANTA / "src" / "simulator.html"
REPORTS = HERE / "reports"
LATEST = SANTA / "submissions" / "latest.json"
REFACTOR_REPORT = REPORTS / "v8-refactor.json"
RESEARCH_VERSION = "v11"
RESEARCH_DIR = HERE / "v11"
ARTIFACT_STATUSES = ("archived-csv", "report-only")
EVIDENCE_FIELDS = ("validation", "audit")
OUTPUT = SANTA / "Santa-2026-Interactive-Report.html"
GITHUB_BLOB = "https://github.com/Leonardo-F/kaggle-lab/blob/main/"

# Demo blocks placed after a stable heading anchor.  The anchors are produced by
# the Markdown ``toc`` extension with its Unicode slugify, not by matching the
# heading text position.
INSERTS = (
    ("01-赛题与手算", "lab"),
    ("41-依赖替换与引用计数v2v3", "compare"),
    ("101-同一批-1000-题的本地成绩", "scores"),
    ("131-候选池中的精确图选择模型", "research"),
    ("124-重构验收状态", "refactor"),
)
REQUIRED_IDS = (
    "lab", "live-graph", "walk-slider", "walk-play", "walk-prev", "walk-next",
    "walk-reset", "step-readout", "op-line", "coverage", "visible-regs",
    "instruction-code", "compare", "scores", "chart-detail", "score-data",
    "sim-source", "sim-gate", "sim-frame", "refactor-status",
)
MATH_FENCE = re.compile(r"^\s*```\s*math\s*$", re.IGNORECASE)


class ReportError(RuntimeError):
    """A build input is missing, inconsistent or not safe to embed."""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReportError(f"invalid JSON in {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Report data (single machine-readable sources)
# ---------------------------------------------------------------------------

FORMAL_REPORT_RE = re.compile(r"v[0-9]+\.json")
FORMAL_VERSION_RE = re.compile(r"v[0-9]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{7,40}")

# Full commit SHAs recorded by the V8 audit.  A short SHA inside a historical
# report is accepted only when it is a unique prefix of one of these locally
# documented commits (plus any full SHA written in the report itself).  The
# build never runs Git and never touches the network.
DOCUMENTED_COMMITS = {
    "9337a354": "9337a3549bea09257cbf36ae1f8da2cbd452942b",
    "0ec0ec0": "0ec0ec011b2448180d04fb771ab3909781fa2f6a",
}

# The eight V8 stage keys recorded by the frozen V8 report and by the refactor
# acceptance report.  Order matters only for documentation.
V8_STAGES = (
    "v7", "list_schedule", "v8", "v81", "v82",
    "v8group_strict", "v8group_neutral", "v8final",
)


def _is_int(value: object) -> bool:
    """True for real integers; JSON ``true``/``false`` are bool subclasses."""
    return isinstance(value, int) and not isinstance(value, bool)


def _int_field(container: dict, field: str, context: str, *, minimum: int | None = None) -> int:
    if field not in container:
        raise ReportError(f"{context} is missing the {field!r} field")
    value = container[field]
    if not _is_int(value):
        raise ReportError(f"{context} {field!r} must be an integer (not a bool or string)")
    if minimum is not None and value < minimum:
        raise ReportError(f"{context} {field!r} must be >= {minimum}, got {value}")
    return value


def _sha256_field(container: dict, field: str, context: str) -> str:
    value = container[field]
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReportError(
            f"{context} {field!r} must be a 64-character lowercase hex SHA-256"
        )
    return value


def report_status(entry: dict) -> str:
    """How the report's submission artifact is available in this repository.

    ``archived-csv`` (the default for historical releases) means the exact CSV
    is shipped next to ``submissions/latest.json``.  ``report-only`` means the
    independent validation and audit are archived but no CSV exists; such a
    record may be charted, but it can never become the downloadable best.
    """
    status = entry["data"].get("artifact_status", "archived-csv")
    if status not in ARTIFACT_STATUSES:
        raise ReportError(
            f"{entry['path'].name} artifact_status must be one of {ARTIFACT_STATUSES}"
        )
    return status


def check_research_evidence(entry: dict, evidence_dir: Path) -> None:
    """Cross-check a report-only record against its archived validation/audit.

    The check is deliberately strict: score, puzzle counts, maximum steps and
    both hashes must equal the independent evidence.  No values are inferred.
    """
    data = entry["data"]
    context = entry["path"].name
    if data.get("local_filename"):
        raise ReportError(
            f"{context} is report-only but declares local_filename "
            f"{data['local_filename']!r}; a missing CSV must not be invented"
        )
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        raise ReportError(f"{context} is report-only but has no evidence mapping")
    for field in EVIDENCE_FIELDS:
        relative = evidence.get(field)
        if not isinstance(relative, str) or not relative.strip():
            raise ReportError(f"{context} evidence is missing the {field!r} path")
        path = evidence_dir / "v11" / Path(relative).name
        if not path.is_file():
            raise ReportError(f"{context} evidence file is missing: {path}")
        payload = _read_json(path)
        if not isinstance(payload, dict):
            raise ReportError(f"{path} must contain a JSON object")
        if field == "validation":
            for key in ("puzzles", "validated", "score", "max_steps",
                        "submission_sha256", "puzzles_sha256"):
                if payload.get(key) != data.get(key):
                    raise ReportError(
                        f"{context} {key}={data.get(key)!r} disagrees with "
                        f"{path.name} {payload.get(key)!r}"
                    )
        else:
            if payload.get("score") != data.get("score"):
                raise ReportError(f"{context} score disagrees with {path.name}")
            if payload.get("total") != data.get("puzzles"):
                raise ReportError(f"{context} puzzle count disagrees with {path.name}")
            if payload.get("complete") != data.get("validated"):
                raise ReportError(f"{context} validated count disagrees with {path.name}")
            if payload.get("puzzles_sha256") != data.get("puzzles_sha256"):
                raise ReportError(f"{context} dataset hash disagrees with {path.name}")
            routes = payload.get("groups_by_route")
            if routes is not None and (
                    not isinstance(routes, dict)
                    or len(routes) < 2
                    or any(not _is_int(value) or value < 0 for value in routes.values())
                    or sum(routes.values()) != payload.get("groups")):
                raise ReportError(f"{context} group inventory disagrees with {path.name}")


def _load_formal_reports(reports_dir: Path) -> tuple[list[dict], list[str]]:
    """Load every formal ``vN.json`` report and validate its identity fields.

    Historical reports keep their original flat schema.  When an old report does
    not record the input/output hashes, the compatibility rule is to skip only
    that comparison and note it; numbers are never invented.  The report of the
    current best submission must be complete (checked in ``load_report_data``).
    """
    entries: list[dict] = []
    for path in sorted(reports_dir.glob("v[0-9]*.json")):
        if not FORMAL_REPORT_RE.fullmatch(path.name):
            continue
        data = _read_json(path)
        if not isinstance(data, dict):
            raise ReportError(f"{path.name} must contain a JSON object")
        version = data.get("version")
        if not isinstance(version, str) or not FORMAL_VERSION_RE.fullmatch(version):
            raise ReportError(f"{path.name} does not declare a version field")
        if version != path.stem:
            raise ReportError(
                f"{path.name} declares version {version!r}; the file name and version must match"
            )
        puzzles = _int_field(data, "puzzles", path.name, minimum=1)
        validated = _int_field(data, "validated", path.name, minimum=0)
        if validated > puzzles:
            raise ReportError(
                f"{path.name} validated={validated} exceeds puzzles={puzzles}"
            )
        score = _int_field(data, "score", path.name, minimum=0)
        if "max_steps" in data:
            _int_field(data, "max_steps", path.name, minimum=1)
        dataset_sha256 = None
        if "puzzles_sha256" in data:
            dataset_sha256 = _sha256_field(data, "puzzles_sha256", path.name)
        if "submission_sha256" in data:
            _sha256_field(data, "submission_sha256", path.name)
        entries.append({
            "version": version,
            "path": path,
            "data": data,
            "score": score,
            "validated": validated,
            "puzzles": puzzles,
            "dataset_sha256": dataset_sha256,
        })
    if not entries:
        raise ReportError(f"no historical reports found in {reports_dir}")

    seen_numbers: dict[int, Path] = {}
    for entry in entries:
        number = int(entry["version"][1:])
        if number in seen_numbers:
            raise ReportError(
                f"{entry['path'].name} and {seen_numbers[number].name} use the same numeric "
                f"version v{number}; formal versions must be unique"
            )
        seen_numbers[number] = entry["path"]
    entries.sort(key=lambda row: int(row["version"][1:]))

    dataset_hashes = {
        entry["dataset_sha256"] for entry in entries if entry["dataset_sha256"] is not None
    }
    if len(dataset_hashes) > 1:
        raise ReportError(
            "formal reports disagree about the official dataset SHA-256; "
            "only the single official puzzle set may feed the formal curve"
        )

    compatibility_notes: list[str] = []
    for entry in entries:
        missing = [
            key for key in ("puzzles_sha256", "submission_sha256")
            if key not in entry["data"]
        ]
        if missing:
            compatibility_notes.append(
                f"{entry['path'].name} 为历史格式，缺少 {', '.join(missing)}；"
                "按兼容规则只核对已记录字段，不补造数值。"
            )
    return entries, compatibility_notes


def load_report_data(reports_dir: Path = REPORTS, latest_path: Path = LATEST) -> dict:
    """Load and cross-check historical reports and the best verified submission.

    ``submissions/latest.json`` is read only for the current best score and the
    formal version curve.  Historical acceptance evidence (for example the V8
    refactor report) must use the fixed per-version payloads in ``reports`` so a
    future best version can never invalidate an older acceptance record.
    """
    entries, compatibility_notes = _load_formal_reports(reports_dir)
    by_version = {entry["version"]: entry for entry in entries}
    for entry in entries:
        status = report_status(entry)
        if status == "report-only":
            check_research_evidence(entry, reports_dir.parent)

    latest = _read_json(latest_path)
    if not isinstance(latest, dict):
        raise ReportError(f"{latest_path} must contain a JSON object")
    for key in ("version", "score", "validated", "local_filename", "report",
                "submission_sha256", "puzzles_sha256"):
        if key not in latest:
            raise ReportError(f"{latest_path} is missing the {key!r} field")
    latest_version = latest["version"]
    if not isinstance(latest_version, str) or not FORMAL_VERSION_RE.fullmatch(latest_version):
        raise ReportError(f"{latest_path} declares an invalid version {latest_version!r}")
    if latest_version not in by_version:
        raise ReportError(f"latest.json version {latest_version!r} has no formal report")
    entry = by_version[latest_version]
    report = entry["data"]
    if report_status(entry) == "report-only":
        raise ReportError(
            f"{latest_path} points to report-only {latest_version}; the downloadable "
            "best must have a verified CSV. Keep latest.json on the archived version."
        )

    latest_score = _int_field(latest, "score", str(latest_path), minimum=0)
    latest_validated = _int_field(latest, "validated", str(latest_path), minimum=0)
    if latest_validated > entry["puzzles"]:
        raise ReportError(
            f"latest.json validated={latest_validated} exceeds puzzles={entry['puzzles']}"
        )
    if latest_score != entry["score"]:
        raise ReportError(
            f"latest.json score={latest_score!r} disagrees with "
            f"{entry['path'].name} score={entry['score']!r}"
        )
    if latest_validated != entry["validated"]:
        raise ReportError(
            f"latest.json validated={latest_validated!r} disagrees with "
            f"{entry['path'].name} validated={entry['validated']!r}"
        )

    report_field = latest["report"]
    if not isinstance(report_field, str) or not report_field.strip():
        raise ReportError(f"{latest_path} report field must be a non-empty path string")
    report_path = (latest_path.parent / report_field).resolve()
    if report_path != entry["path"].resolve():
        raise ReportError(
            f"latest.json points to {report_path}, but formal report "
            f"{entry['path'].name} declares version {latest_version!r}"
        )

    for key in ("submission_sha256", "puzzles_sha256"):
        if key not in report:
            raise ReportError(
                f"{entry['path'].name} must record {key} because it is the current best report"
            )
        _sha256_field(latest, key, str(latest_path))
        if latest[key] != report[key]:
            raise ReportError(
                f"latest.json {key} disagrees with {entry['path'].name}"
            )
    dataset_hashes = {
        item["dataset_sha256"] for item in entries if item["dataset_sha256"] is not None
    }
    if dataset_hashes and latest["puzzles_sha256"] not in dataset_hashes:
        raise ReportError(
            "latest.json puzzles_sha256 does not match the formal reports' dataset identity"
        )

    local_filename = latest["local_filename"]
    if not isinstance(local_filename, str) or not local_filename.strip():
        raise ReportError(f"{latest_path} local_filename must be a non-empty path string")
    submission = latest_path.parent / local_filename
    if not submission.is_file():
        raise ReportError(f"latest.json points to a missing submission CSV: {submission}")
    if _sha256(submission) != latest["submission_sha256"]:
        raise ReportError(f"submission SHA-256 does not match latest.json: {submission}")

    historical = [
        {
            "version": item["version"],
            "score": item["score"],
            "validated": item["validated"],
            "puzzles": item["puzzles"],
        }
        for item in entries
    ]
    return {
        "latest": latest,
        "latest_report": report,
        "historical": historical,
        "reports": {item["version"]: item["data"] for item in entries},
        "statuses": {item["version"]: report_status(item) for item in entries},
        "research": by_version.get(RESEARCH_VERSION, {}).get("data"),
        "submission": submission,
        "compatibility_notes": compatibility_notes,
    }


FORMAL_SCORE_TABLE_MARKER = "独立验证记录"


def _markdown_table_blocks(markdown_text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in markdown_text.replace("\r\n", "\n").split("\n"):
        if line.lstrip().startswith("|"):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_score(cell: str, context: str) -> int:
    cleaned = cell.replace("**", "").replace(",", "").strip()
    if not re.fullmatch(r"[0-9]+", cleaned):
        raise ReportError(f"{context} 的分数单元格无法解析为整数: {cell!r}")
    return int(cleaned)


def _parse_formal_score_table(markdown_text: str) -> dict[str, int]:
    """Parse the version→score pairing out of the formal score table.

    ``check_markdown_numbers`` must not accept a version merely because its
    number appears somewhere in the prose: the table cell has to belong to the
    matching version row.
    """
    tables = [
        block for block in _markdown_table_blocks(markdown_text)
        if any(FORMAL_SCORE_TABLE_MARKER in cell for cell in _table_cells(block[0]))
    ]
    if not tables:
        raise ReportError(
            "algorithm-evolution.md 缺少正式成绩表（表头应包含“独立验证记录”）"
        )
    if len(tables) > 1:
        raise ReportError("algorithm-evolution.md 包含多个正式成绩表，无法确定唯一分数来源")
    table = tables[0]
    if len(table) < 3:
        raise ReportError("algorithm-evolution.md 的正式成绩表为空")
    scores: dict[str, int] = {}
    for line in table[2:]:
        cells = _table_cells(line)
        if len(cells) < 3:
            raise ReportError(f"正式成绩表行缺少列: {line}")
        match = re.fullmatch(r"V([0-9]+)(?:\s+\S.*)?", cells[0])
        if match is None:
            raise ReportError(f"正式成绩表的版本标签无效: {cells[0]!r}")
        version = f"v{int(match.group(1))}"
        if version in scores:
            raise ReportError(f"正式成绩表重复列出 {version.upper()}")
        scores[version] = _table_score(cells[2], f"正式成绩表 {version.upper()}")
    return scores


def check_markdown_numbers(markdown_text: str, data: dict) -> None:
    """Fail when the document and the machine-readable reports disagree."""
    table_scores = _parse_formal_score_table(markdown_text)
    report_scores = {row["version"]: row["score"] for row in data["historical"]}

    extra = sorted(set(table_scores) - set(report_scores), key=lambda item: int(item[1:]))
    missing = sorted(set(report_scores) - set(table_scores), key=lambda item: int(item[1:]))
    if extra:
        raise ReportError(
            "正式成绩表包含没有正式报告的版本: " + ", ".join(item.upper() for item in extra)
        )
    if missing:
        raise ReportError(
            "正式成绩表缺少正式报告的版本: " + ", ".join(item.upper() for item in missing)
        )
    for version, expected in report_scores.items():
        actual = table_scores[version]
        if actual != expected:
            raise ReportError(
                f"正式成绩表中 {version.upper()} 的分数 {actual:,} 与 "
                f"docs/reports/{version}.json 的 {expected:,} 不一致"
            )
    latest = data["latest"]
    if f"{latest['score']:,}" not in markdown_text:
        raise ReportError(
            f"algorithm-evolution.md does not contain the latest verified score "
            f"{latest['score']:,} from submissions/latest.json"
        )


def score_payload(data: dict) -> list[dict]:
    return [
        {"version": row["version"].upper(), "score": row["score"],
         "validated": row["validated"], "status": data["statuses"][row["version"]]}
        for row in data["historical"]
    ]


def score_bars(data: dict) -> str:
    items = []
    for index, row in enumerate(data["historical"]):
        status = data["statuses"][row["version"]]
        suffix = "†" if status == "report-only" else ""
        items.append(
            '<li><button type="button" class="bar-row" data-score="%d" '
            'data-status="%s" aria-pressed="false">'
            '<span>%s%s</span><span class="bar-track" aria-hidden="true">'
            '<span class="bar-fill"></span></span><span class="bar-count">%s</span>'
            "</button></li>"
            % (index, status, row["version"].upper(), suffix, f"{row['score']:,}")
        )
    return "\n".join(items)


# ---------------------------------------------------------------------------
# Optional V8 refactor reproduction report
# ---------------------------------------------------------------------------

REFACTOR_KIND = "santa-v8-refactor"
GITHUB_REPORTS = GITHUB_BLOB + "competitions/santa-2026/docs/reports/"
V8_REFERENCE_VERSION = "v8"

REFACTOR_EQUIVALENCE_FLAGS = (
    "csv_byte_identical_to_archived",
    "csv_byte_identical_to_baseline_run",
    "per_puzzle_programs_identical_to_archived",
    "per_puzzle_programs_identical_to_baseline_run",
    "eight_stage_totals_identical_to_archived",
    "eight_stage_totals_identical_to_baseline_run",
    "per_puzzle_stage_metrics_identical_to_baseline_run",
)
REFACTOR_TOP_FLAGS = (
    "per_puzzle_programs_match",
    "stage_metrics_match",
    "score_matches_archived_v8",
)
REFACTOR_TEST_GROUPS = ("santa_python", "santa_node", "web")


def _resolve_commit(value, candidates, context, reasons):
    """Resolve a full or short commit SHA using only locally fixed evidence.

    A full 40-hex SHA stands for itself.  A short SHA is accepted only when it
    is a unique prefix of the documented commits or of a full SHA written in the
    report.  The build never runs Git and never uses the network.
    """
    if not isinstance(value, str) or not value.strip():
        reasons.append(f"{context} 必须为非空 commit 字符串")
        return None
    value = value.strip().lower()
    if not COMMIT_RE.fullmatch(value):
        reasons.append(f"{context} 不是 7–40 位十六进制 commit: {value!r}")
        return None
    if len(value) == 40:
        return value
    matches = sorted(candidate for candidate in candidates if candidate.startswith(value))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        reasons.append(
            f"{context} 的短 SHA {value} 无法在本地记录中唯一解析"
            "（离线构建不读 Git 历史、不联网）"
        )
    else:
        reasons.append(f"{context} 的短 SHA {value} 是多个提交的前缀，无法唯一解析")
    return None


def _validate_refactor_payload(data: dict, archived: dict) -> list[str]:
    """Cross-check v8-refactor.json against the fixed archived V8 report."""
    reasons: list[str] = []

    def add(message: str) -> None:
        reasons.append(message)

    if not isinstance(archived, dict) or archived.get("version") != V8_REFERENCE_VERSION:
        return [
            "缺少固定的原始 V8 正式报告 docs/reports/v8.json；无法核对 "
            "v8-refactor.json，也不会回退到当前最佳版本"
        ]

    def archived_int(field, *, minimum=None):
        value = archived.get(field)
        if not _is_int(value):
            add(f"原始 V8 报告缺少有效的整数字段 {field}")
            return None
        if minimum is not None and value < minimum:
            add(f"原始 V8 报告 {field}={value} 必须 >= {minimum}")
            return None
        return value

    def archived_sha256(field):
        value = archived.get(field)
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            add(f"原始 V8 报告缺少有效的 SHA-256 字段 {field}")
            return None
        return value

    def archived_stages():
        stages = archived.get("stages")
        if not isinstance(stages, dict) or set(stages) != set(V8_STAGES):
            add("原始 V8 报告缺少完整的 V8 八阶段 stages 记录")
            return None
        values = {}
        for stage in V8_STAGES:
            value = stages[stage]
            if not _is_int(value) or value < 0:
                add(f"原始 V8 报告 stages.{stage} 必须为非负整数")
                return None
            values[stage] = value
        return values

    expected = {
        "puzzles": archived_int("puzzles", minimum=1),
        "validated": archived_int("validated", minimum=0),
        "score": archived_int("score", minimum=0),
        "max_steps": archived_int("max_steps", minimum=1),
        "submission_sha256": archived_sha256("submission_sha256"),
        "puzzles_sha256": archived_sha256("puzzles_sha256"),
        "stages": archived_stages(),
    }

    def expect_equal(mapping, field, expected_value, context, *, kind="int"):
        if expected_value is None:
            return
        if not isinstance(mapping, dict) or field not in mapping:
            add(f"{context} 缺少 {field}")
            return
        value = mapping[field]
        if kind == "sha256":
            if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                add(f"{context}.{field} 必须是 64 位小写十六进制 SHA-256")
            elif value != expected_value:
                add(f"{context}.{field} 与原始 V8 报告不一致")
            return
        if not _is_int(value):
            add(f"{context}.{field} 必须为整数（拒绝 bool/字符串）")
            return
        if kind == "count" and value < 0:
            add(f"{context}.{field} 不能为负数")
            return
        if value != expected_value:
            add(f"{context}.{field}={value} 与原始 V8 报告 {expected_value} 不一致")

    def stage_totals(mapping, field, context):
        if not isinstance(mapping, dict) or field not in mapping:
            add(f"{context} 缺少 {field}")
            return None
        stages = mapping[field]
        if not isinstance(stages, dict):
            add(f"{context}.{field} 必须是 JSON 对象")
            return None
        if set(stages) != set(V8_STAGES):
            missing_keys = sorted(set(V8_STAGES) - set(stages))
            extra_keys = sorted(set(stages) - set(V8_STAGES))
            details = []
            if missing_keys:
                details.append("缺少 " + ", ".join(missing_keys))
            if extra_keys:
                details.append("多出 " + ", ".join(extra_keys))
            add(f"{context}.{field} 的 V8 八阶段键不完整（{'；'.join(details)}）")
            return None
        values = {}
        for stage in V8_STAGES:
            value = stages[stage]
            if not _is_int(value) or value < 0:
                add(f"{context}.{field}.{stage} 必须为非负整数")
                return None
            values[stage] = value
        return values

    # ---- schema, kind and acceptance status --------------------------------
    if not _is_int(data.get("schema")) or data["schema"] != 1:
        add("schema 必须为整数 1")
    if data.get("kind") != REFACTOR_KIND:
        add(f"kind 必须为 {REFACTOR_KIND!r}")
    if data.get("status") != "accepted":
        add("status 必须为 'accepted'；未通过的验收报告不得展示为等价重构成功")

    # ---- commits: top level, nested, documented identity and prefix rules ---
    baseline = data.get("baseline")
    refactor = data.get("refactor")
    if not isinstance(baseline, dict):
        add("缺少 baseline 对象")
    if not isinstance(refactor, dict):
        add("缺少 refactor 对象")
    nested_baseline = baseline.get("commit") if isinstance(baseline, dict) else None
    nested_refactor = refactor.get("commit") if isinstance(refactor, dict) else None
    candidates = set(DOCUMENTED_COMMITS.values())
    for value in (data.get("baseline_commit"), data.get("refactor_commit"),
                  nested_baseline, nested_refactor):
        if isinstance(value, str) and len(value) == 40 and COMMIT_RE.fullmatch(value):
            candidates.add(value)
    resolved = {
        "baseline_commit": _resolve_commit(
            data.get("baseline_commit"), candidates, "baseline_commit", reasons),
        "baseline.commit": _resolve_commit(
            nested_baseline, candidates, "baseline.commit", reasons),
        "refactor_commit": _resolve_commit(
            data.get("refactor_commit"), candidates, "refactor_commit", reasons),
        "refactor.commit": _resolve_commit(
            nested_refactor, candidates, "refactor.commit", reasons),
    }
    if resolved["baseline_commit"] and resolved["baseline.commit"]:
        if resolved["baseline_commit"] != resolved["baseline.commit"]:
            add("顶层 baseline_commit 与嵌套 baseline.commit 不一致")
    if resolved["refactor_commit"] and resolved["refactor.commit"]:
        if resolved["refactor_commit"] != resolved["refactor.commit"]:
            add("顶层 refactor_commit 与嵌套 refactor.commit 不一致")
    if resolved["baseline.commit"] and resolved["baseline.commit"] != DOCUMENTED_COMMITS["9337a354"]:
        add("baseline.commit 与记录中的 V8 冻结基线提交不一致")
    if resolved["refactor.commit"] and resolved["refactor.commit"] != DOCUMENTED_COMMITS["0ec0ec0"]:
        add("refactor.commit 与记录中的 V8 重构实现提交不一致")
    if isinstance(refactor, dict):
        if refactor.get("solver_version") != V8_REFERENCE_VERSION:
            add("refactor.solver_version 必须为 'v8'")
        for field in ("module_count_before", "module_count_after"):
            if field in refactor and (not _is_int(refactor[field]) or refactor[field] < 1):
                add(f"refactor.{field} 必须为正整数")

    # ---- top level numbers must equal the archived V8 release ---------------
    expect_equal(data, "puzzles", expected["puzzles"], "v8-refactor 顶层")
    expect_equal(data, "validated", expected["validated"], "v8-refactor 顶层")
    expect_equal(data, "score", expected["score"], "v8-refactor 顶层", kind="count")
    expect_equal(data, "submission_sha256", expected["submission_sha256"],
                 "v8-refactor 顶层", kind="sha256")
    for flag in REFACTOR_TOP_FLAGS:
        if data.get(flag) is not True:
            add(f"顶层 {flag} 必须为 true")

    # ---- nested baseline record ---------------------------------------------
    if isinstance(baseline, dict):
        expect_equal(baseline, "archived_score", expected["score"], "baseline",
                     kind="count")
        expect_equal(baseline, "archived_max_steps", expected["max_steps"], "baseline",
                     kind="count")
        expect_equal(baseline, "archived_submission_sha256",
                     expected["submission_sha256"], "baseline", kind="sha256")
        expect_equal(baseline, "puzzles_sha256", expected["puzzles_sha256"],
                     "baseline", kind="sha256")
        archived_submission = baseline.get("archived_submission")
        if not isinstance(archived_submission, str) or not archived_submission.strip():
            add("baseline.archived_submission 必须为归档 CSV 路径字符串")
        baseline_stages = stage_totals(baseline, "archived_stage_totals", "baseline")
        if baseline_stages is not None and expected["stages"] is not None:
            if baseline_stages != expected["stages"]:
                add("baseline.archived_stage_totals 与原始 V8 报告的八阶段总分不一致")

    # ---- both full runs, their stages and their checkpoints -----------------
    run_stages = {}
    runs = (("baseline_run", data.get("baseline_run")),
            ("refactored_run", data.get("refactored_run")))
    for name, run in runs:
        if not isinstance(run, dict):
            add(f"缺少 {name} 对象")
            continue
        expect_equal(run, "puzzles", expected["puzzles"], name)
        expect_equal(run, "validated", expected["validated"], name)
        expect_equal(run, "score", expected["score"], name, kind="count")
        expect_equal(run, "max_steps", expected["max_steps"], name, kind="count")
        expect_equal(run, "submission_sha256", expected["submission_sha256"], name,
                     kind="sha256")
        stages = stage_totals(run, "stage_totals", name)
        if stages is not None:
            run_stages[name] = stages
            if expected["stages"] is not None and stages != expected["stages"]:
                add(f"{name}.stage_totals 与原始 V8 报告八阶段总分不一致")
            if _is_int(run.get("score")) and stages["v8final"] != run["score"]:
                add(f"{name}.stage_totals.v8final 不等于该次运行的 score")
        checkpoint = run.get("checkpoint")
        if not isinstance(checkpoint, dict):
            add(f"{name} 缺少 checkpoint 记录")
        else:
            if checkpoint.get("integrity_check") != "ok":
                add(f"{name}.checkpoint.integrity_check 必须为 'ok'")
            expect_equal(checkpoint, "results", expected["puzzles"], f"{name}.checkpoint")
            if "fingerprint_schema" in checkpoint and not _is_int(
                    checkpoint["fingerprint_schema"]):
                add(f"{name}.checkpoint.fingerprint_schema 必须为整数")
        if not _is_int(run.get("jobs")) or run["jobs"] < 1:
            add(f"{name}.jobs 必须为正整数")
    if len(run_stages) == 2 and run_stages["baseline_run"] != run_stages["refactored_run"]:
        add("baseline_run 与 refactored_run 的八阶段总分逐键不一致")

    # ---- improved/unchanged/worse bookkeeping ------------------------------
    refactored_run = data.get("refactored_run")
    if isinstance(refactored_run, dict):
        counts = {}
        for field in ("improved", "unchanged", "worse"):
            value = refactored_run.get(field)
            if not _is_int(value) or value < 0:
                add(f"refactored_run.{field} 必须为非负整数")
            else:
                counts[field] = value
                if field in archived and _is_int(archived[field]) \
                        and value != archived[field]:
                    add(f"refactored_run.{field}={value} 与原始 V8 报告 "
                        f"{archived[field]} 不一致")
        if len(counts) == 3 and expected["puzzles"] is not None:
            total = counts["improved"] + counts["unchanged"] + counts["worse"]
            if total != expected["puzzles"]:
                add(f"refactored_run.improved+unchanged+worse={total} "
                    f"不等于题数 {expected['puzzles']}")

    # ---- equivalence flags and the per-puzzle diff count -------------------
    equivalence = data.get("equivalence")
    if not isinstance(equivalence, dict):
        add("缺少 equivalence 对象")
        equivalence = {}
    for flag in REFACTOR_EQUIVALENCE_FLAGS:
        if equivalence.get(flag) is not True:
            add(f"equivalence.{flag} 必须为 true")
    diff_count = equivalence.get("per_puzzle_metric_diff_count")
    if not _is_int(diff_count):
        add("equivalence.per_puzzle_metric_diff_count 必须为整数")
    elif diff_count != 0:
        add(f"equivalence.per_puzzle_metric_diff_count={diff_count} 必须为 0")

    # ---- test evidence, grouped counts and full-equivalence relation -------
    tests = data.get("tests")
    if not isinstance(tests, dict):
        add("缺少 tests 结果")
    else:
        group_total = 0
        groups_ok = True
        for group in REFACTOR_TEST_GROUPS:
            record = tests.get(group)
            if not isinstance(record, dict):
                add(f"tests.{group} 测试分组记录缺失")
                groups_ok = False
                continue
            count = record.get("tests")
            if not _is_int(count) or count < 1:
                add(f"tests.{group}.tests 必须为正整数")
                groups_ok = False
                continue
            if record.get("result") != "ok":
                add(f"tests.{group}.result 必须为 'ok'")
                groups_ok = False
            group_total += count
        passed = tests.get("passed")
        failed = tests.get("failed")
        if not _is_int(passed) or passed < 1:
            add("tests.passed 必须为正整数")
        if not _is_int(failed) or failed != 0:
            add("tests.failed 必须为 0")
        if groups_ok and _is_int(passed) and passed != group_total:
            add(f"tests.passed={passed} 与分组测试记录合计 {group_total} 不一致")
        full = tests.get("full_equivalence")
        if not isinstance(full, dict):
            add("tests.full_equivalence 记录缺失")
            full = {}
        programs = full.get("programs_identical")
        if not _is_int(programs):
            add("tests.full_equivalence.programs_identical 必须为整数")
        elif programs < 0:
            add("tests.full_equivalence.programs_identical 不能为负数")
        elif expected["puzzles"] is not None and programs != expected["puzzles"]:
            add(f"tests.full_equivalence.programs_identical={programs} "
                f"必须等于题数 {expected['puzzles']}")
        for flag in ("stage_totals_identical", "per_puzzle_metrics_identical"):
            if full.get(flag) is not True:
                add(f"tests.full_equivalence.{flag} 必须为 true")
        if full.get("stage_totals_identical") is True and \
                equivalence.get("eight_stage_totals_identical_to_archived") is not True:
            add("tests.full_equivalence.stage_totals_identical "
                "与 equivalence 阶段标志矛盾")
        if full.get("per_puzzle_metrics_identical") is True and \
                equivalence.get("per_puzzle_stage_metrics_identical_to_baseline_run") is not True:
            add("tests.full_equivalence.per_puzzle_metrics_identical "
                "与 equivalence 逐题指标标志矛盾")
        if data.get("per_puzzle_programs_match") is True and \
                equivalence.get("per_puzzle_programs_identical_to_archived") is not True:
            add("顶层 per_puzzle_programs_match 与 equivalence 逐题程序标志矛盾")
        independent_verify = tests.get("independent_verify")
        if not isinstance(independent_verify, dict):
            add("tests.independent_verify 记录缺失")
        else:
            expect_equal(independent_verify, "puzzles", expected["puzzles"],
                         "tests.independent_verify")
            expect_equal(independent_verify, "validated", expected["validated"],
                         "tests.independent_verify")
            expect_equal(independent_verify, "score", expected["score"],
                         "tests.independent_verify")
            if independent_verify.get("result") != "ok":
                add("tests.independent_verify.result 必须为 'ok'")
        for group, expected_result in (("report_check", "up to date"),
                                       ("bundle_check", "ok")):
            record = tests.get(group)
            if not isinstance(record, dict):
                add(f"tests.{group} 检查记录缺失")
            elif record.get("result") != expected_result:
                add(f"tests.{group}.result 必须为 {expected_result!r}")

    # ---- source fingerprints: format only, never compared to the worktree --
    sources = data.get("sources")
    if not isinstance(sources, dict):
        add("缺少 sources 源码指纹记录")
    else:
        fingerprints = sources.get("refactor_commit_solver_sources")
        if not isinstance(fingerprints, dict) or not fingerprints:
            add("sources.refactor_commit_solver_sources 必须为非空对象")
        else:
            for name, digest in fingerprints.items():
                if not isinstance(name, str) or not name.strip():
                    add("sources.refactor_commit_solver_sources 包含无效文件名")
                if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    add(f"sources.refactor_commit_solver_sources[{name!r}] "
                        "必须是 64 位 SHA-256")

    # ---- limitations must be preserved -------------------------------------
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        add("limitations 必须为非空列表（历史报告的限制说明不得丢失）")
    else:
        for item in limitations:
            if not isinstance(item, str) or not item.strip():
                add("limitations 的每个条目都必须为非空字符串")

    # ---- practice run is a separate dataset, never mixed with formal puzzles
    practice = data.get("practice_run")
    if not isinstance(practice, dict):
        add("缺少 practice_run 记录（练习题必须与正式题分开）")
    else:
        practice_puzzles = practice.get("puzzles")
        practice_validated = practice.get("validated")
        if not _is_int(practice_puzzles) or practice_puzzles < 1:
            add("practice_run.puzzles 必须为正整数")
        if not _is_int(practice_validated) or practice_validated < 0:
            add("practice_run.validated 必须为非负整数")
        elif _is_int(practice_puzzles) and practice_validated > practice_puzzles:
            add("practice_run.validated 不能超过 practice_run.puzzles")
        if not _is_int(practice.get("score")) or practice["score"] < 0:
            add("practice_run.score 必须为非负整数")
        practice_dataset = practice.get("puzzles_sha256")
        if not isinstance(practice_dataset, str) or not SHA256_RE.fullmatch(practice_dataset):
            add("practice_run.puzzles_sha256 必须是 64 位 SHA-256")
        elif expected["puzzles_sha256"] is not None \
                and practice_dataset == expected["puzzles_sha256"]:
            add("practice_run 的题目 SHA-256 与正式题相同；练习题不能与正式题混算")
        practice_submission = practice.get("submission_sha256")
        if not isinstance(practice_submission, str) or \
                not SHA256_RE.fullmatch(practice_submission):
            add("practice_run.submission_sha256 必须是 64 位 SHA-256")
        elif expected["submission_sha256"] is not None \
                and practice_submission == expected["submission_sha256"]:
            add("practice_run 的提交 SHA-256 与正式题相同；练习题不能与正式题混算")

    # ---- historical-only fields --------------------------------------------
    pushed = data.get("pushed")
    if pushed is not None and not isinstance(pushed, bool):
        add("pushed 必须为布尔值（只表示报告生成时的状态）")
    unverified = data.get("unverified")
    if unverified is not None:
        if not isinstance(unverified, list):
            add("unverified 必须为列表")
        elif unverified:
            add("报告仍有未验证项: " + "; ".join(str(item) for item in unverified))
    return reasons


def load_refactor_status(path, archived):
    """Validate the optional V8 refactor report without re-running the solver.

    ``archived`` must be the parsed ``docs/reports/v8.json`` payload, never the
    current best report or ``submissions/latest.json``: the V8 acceptance stays
    valid when a future version becomes the best.
    """
    if not path.exists():
        return {"state": "absent", "reasons": [], "data": {}}
    if not isinstance(archived, dict):
        return {
            "state": "invalid",
            "reasons": [
                "缺少固定的原始 V8 正式报告 docs/reports/v8.json；无法核对 "
                "v8-refactor.json，也不会回退到当前最佳版本"
            ],
            "data": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "state": "invalid",
            "reasons": [f"无法读取或解析 {path.name}: {exc}"],
            "data": {},
        }
    if not isinstance(data, dict):
        return {"state": "invalid", "reasons": ["报告必须是 JSON 对象"], "data": {}}
    reasons = _validate_refactor_payload(data, archived)
    return {"state": "valid" if not reasons else "invalid", "reasons": reasons, "data": data}


def _refactor_link(name):
    return f'<a href="{GITHUB_REPORTS}{name}">{name}</a>'


def render_refactor_panel(status):
    if status["state"] == "absent":
        return (
            '<h3>功能化重构复现报告（可选）</h3>'
            '<p class="sub">尚未生成 <code>docs/reports/v8-refactor.json</code>。</p>'
            "<p>历史参考固定为原始 V8 全量实验报告 "
            f"{_refactor_link('v8.json')}，不随 <code>submissions/latest.json</code> "
            "的当前最佳指针变化。缺少该可选文件不会导致构建失败，也不新增版本曲线或 "
            "CSV 回放槽位。重构复现报告生成并通过校验后，这里会自动展示它与原始 V8 "
            "报告的一致性结果。本页只做记录一致性核查，未执行求解。</p>"
        )
    if status["state"] == "invalid":
        items = "".join(f"<li>{html.escape(str(reason))}</li>" for reason in status["reasons"])
        return (
            "<h3>功能化重构复现报告：校验未通过</h3>"
            '<div class="refactor-bad" role="alert"><strong>未通过记录一致性校验。</strong>'
            " 不把该报告展示为等价重构成功，也不更新最佳成绩或回放槽位。</div>"
            f"<ul>{items}</ul>"
            '<p class="small">本页只做记录一致性核查，未执行求解；历史参考固定为原始 V8 '
            f"报告 {_refactor_link('v8.json')}，不会回退到当前最佳版本，也不会用最新报告"
            "的分数或哈希掩盖该失败。</p>"
        )
    data = status["data"]
    tests = data["tests"]
    equivalence = data["equivalence"]
    rows = [
        ("全量指令数", f"{data['score']:,}", "与原始 V8 报告一致"),
        ("独立验证", f"{data['validated']:,} / {data['puzzles']:,}", "与原始 V8 报告一致"),
        ("逐题程序一致",
         f"{equivalence['per_puzzle_metric_diff_count']} 个逐题指标差异",
         "与原始 V8 报告和基线运行逐键一致"),
        ("八阶段指标一致", "是", "八阶段总分与原始 V8 报告一致"),
        ("测试", f"{tests['passed']} 通过 / {tests['failed']} 失败", "报告记录的分组测试"),
        ("局限记录", f"{len(data['limitations'])} 条", "记录级核查，不是独立求解或形式化证明"),
    ]
    if isinstance(data.get("refactor_commit"), str) and data["refactor_commit"].strip():
        rows.append(("重构提交", f"<code>{html.escape(data['refactor_commit'])}</code>",
                     "报告声明"))
    rows.append(("基线提交", f"<code>{html.escape(data['baseline_commit'])}</code>",
                 "原始 V8 报告声明"))
    table = "".join(
        f'<tr><th scope="row">{html.escape(label)}</th><td>{value}</td>'
        f'<td class="small">{html.escape(note)}</td></tr>'
        for label, value, note in rows
    )
    return (
        "<h3>功能化重构复现报告</h3>"
        '<p class="sub">报告通过本页一致性校验：与原始 V8 报告一致；这是 V8 的等价代码重构，'
        "不是新的算法版本。</p>"
        f'<div class="refactor-ok" role="status"><strong>等价重构复现：{data["score"]:,} 步 · '
        f'{data["validated"]:,} / {data["puzzles"]:,} 题通过</strong></div>'
        f'<div class="table-wrap"><table>{table}</table></div>'
        '<p class="small">本页只做记录一致性核查，未执行求解；核对对象是 '
        "<code>docs/reports/v8-refactor.json</code> 与固定的原始 V8 报告 "
        f"{_refactor_link('v8.json')}，不涉及当前最佳版本的重新验收。"
        "原始证据仍以 v8.json 为准。报告文件：<code>docs/reports/v8-refactor.json</code>。</p>"
    )


# ---------------------------------------------------------------------------
# MathML rendering (offline, build time)
# ---------------------------------------------------------------------------

def _aligned_to_array(latex: str) -> str:
    """latex2mathml does not support ``aligned``; map it onto an array."""

    def replace(match: re.Match[str]) -> str:
        body = match.group(1)
        columns = max((row.count("&") for row in body.split("\\\\")), default=0) + 1
        columns = max(2, min(columns, 4))
        spec = "r" + "l" * (columns - 1)
        return f"\\begin{{array}}{{{spec}}}{body}\\end{{array}}"

    return re.sub(r"\\begin\{aligned\}(.*?)\\end\{aligned\}", replace, latex, flags=re.S)


def render_math(latex: str, display: str) -> str:
    latex = latex.strip()
    if not latex:
        raise ReportError("empty math expression")
    try:
        mathml = latex_to_mathml(_aligned_to_array(latex), display=display)
    except Exception as exc:  # latex2mathml raises many parser-specific errors
        raise ReportError(f"cannot render math {latex[:60]!r}: {exc}") from exc
    opening = mathml[: mathml.index(">") + 1]
    inner = mathml[mathml.index(">") + 1 :]
    if not inner.endswith("</math>"):
        raise ReportError(f"unexpected MathML output for {latex[:60]!r}")
    inner = inner[: -len("</math>")]
    annotation = html.escape(latex, quote=False)
    return (
        f"{opening}<semantics>{inner}"
        f'<annotation encoding="application/x-tex">{annotation}</annotation>'
        "</semantics></math>"
    )


# ---------------------------------------------------------------------------
# Markdown preprocessing
# ---------------------------------------------------------------------------

def _image_figure(docs_dir: Path, alt: str, target: str) -> str:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
        raise ReportError(f"only repository images may be embedded: {target}")
    path = (docs_dir / target).resolve()
    if not path.is_file():
        raise ReportError(f"missing image: {target}")
    if docs_dir.resolve() not in path.parents:
        raise ReportError(f"image escapes the docs directory: {target}")
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}.get(path.suffix.lower())
    if mime is None:
        raise ReportError(f"unsupported image type: {target}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    caption = html.escape(alt, quote=False)
    return (
        f'<figure class="report-figure"><img src="data:{mime};base64,{encoded}" '
        f'alt="{caption}" loading="lazy"><figcaption>{caption}</figcaption></figure>'
    )


def preprocess(markdown_text: str, docs_dir: Path) -> tuple[str, list[str], list[str]]:
    """Protect code, math and figures, returning placeholders and rendered HTML."""
    text = markdown_text.replace("\r\n", "\n")
    # md_in_html only converts Markdown inside HTML blocks that opt in.
    text = re.sub(r"<details(\s*)>", r'<details markdown="1">', text)
    blocks: list[str] = []
    inlines: list[str] = []

    def add_block(content: str) -> str:
        blocks.append(content)
        return f'<div data-rb="{len(blocks) - 1}"></div>'

    def add_inline(content: str) -> str:
        inlines.append(content)
        return f'<span data-ri="{len(inlines) - 1}"></span>'

    lines = text.split("\n")
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        fence = re.match(r"^(\s*)(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$", line)
        if fence:
            marker, language = fence.group(2), fence.group(3).lower()
            body: list[str] = []
            index += 1
            while index < len(lines) and not re.match(
                rf"^\s*{re.escape(marker[:3])}\s*$", lines[index]
            ):
                body.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ReportError(f"unclosed fenced code block near: {line.strip()!r}")
            index += 1
            if language == "math":
                output.extend(["", add_block(
                    '<div class="math-block">' + render_math("\n".join(body), "block") + "</div>"
                ), ""])
            elif language == "mermaid":
                escaped = html.escape("\n".join(body), quote=False)
                output.extend(["", add_block(
                    '<div class="mermaid-note">Mermaid 图源（本报告离线生成，不执行 Mermaid 渲染；'
                    "正文另有一段文字说明该图）。</div>"
                    f'<pre class="mermaid-source"><code>{escaped}</code></pre>'
                ), ""])
            else:
                escaped = html.escape("\n".join(body), quote=False)
                css = f' class="language-{language}"' if language else ""
                output.extend(["", add_block(f"<pre><code{css}>{escaped}</code></pre>"), ""])
            continue

        image = re.match(r"^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$", line)
        if image:
            output.extend(["", add_block(_image_figure(docs_dir, image.group(1), image.group(2))), ""])
            index += 1
            continue

        # Inline code spans are taken first so ``$`` inside code is not math.
        def code_span(match: re.Match[str]) -> str:
            return add_inline(f"<code>{html.escape(match.group(1), quote=False)}</code>")

        line = re.sub(r"`([^`\n]+)`", code_span, line)

        def inline_math(match: re.Match[str]) -> str:
            return add_inline(render_math(match.group(1), "inline"))

        line = re.sub(r"\$([^$\n]+?)\$", inline_math, line)
        output.append(line)
        index += 1
    return "\n".join(output), blocks, inlines


# ---------------------------------------------------------------------------
# Markdown rendering, links and anchors
# ---------------------------------------------------------------------------

def markdown_to_html(markdown_text: str, docs_dir: Path) -> tuple[str, list[dict]]:
    prepared, blocks, inlines = preprocess(markdown_text, docs_dir)
    parser = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists", "md_in_html"],
        extension_configs={"toc": {"slugify": slugify_unicode, "toc_depth": "2-3"}},
    )
    rendered = parser.convert(prepared)
    for position, content in enumerate(blocks):
        token = f'<div data-rb="{position}"></div>'
        if token not in rendered:
            raise ReportError(f"build placeholder for block {position} was lost")
        rendered = rendered.replace(token, content)
    for position, content in enumerate(inlines):
        token = f'<span data-ri="{position}"></span>'
        if token not in rendered:
            raise ReportError(f"build placeholder for inline {position} was lost")
        rendered = rendered.replace(token, content)
    if "data-rb=" in rendered or "data-ri=" in rendered:
        raise ReportError("unresolved build placeholders remain")
    return rendered, parser.toc_tokens


def render_toc(toc_tokens: list[dict]) -> str:
    items = []
    for token in toc_tokens:
        if token.get("level") != 2 or token.get("name") == "学习导航":
            continue
        items.append(f'<li><a href="#{token["id"]}">{html.escape(token["name"], quote=False)}</a></li>')
    if not items:
        raise ReportError("the document has no level-2 headings")
    return "".join(items)


def insert_blocks(article: str, blocks: dict[str, str]) -> str:
    heading = re.compile(r'<h([23]) id="([^"]+)"')
    for anchor, name in INSERTS:
        match = next((item for item in heading.finditer(article) if item.group(2) == anchor), None)
        if match is None:
            raise ReportError(f"missing insertion anchor #{anchor} for the {name!r} demo")
        level = int(match.group(1))
        end = len(article)
        for later in heading.finditer(article, match.end()):
            if int(later.group(1)) <= level:
                end = later.start()
                break
        article = article[:end] + blocks[name] + "\n" + article[end:]
    return article


def rewrite_links(article: str, docs_dir: Path, warnings: list[str] | None = None) -> str:
    """Resolve relative links to GitHub; report targets that are not present yet."""
    warnings = warnings if warnings is not None else []
    ids = set(re.findall(r'\bid="([^"]+)"', article))
    source = {
        SIMULATOR.resolve(): "#simulator",
        OUTPUT.resolve(): "#top",
        REFACTOR_REPORT.resolve(): "#refactor-status",
    }

    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        if href.startswith("#"):
            if href[1:] not in ids:
                raise ReportError(f"internal link points to a missing anchor: {href}")
            return match.group(0)
        if re.match(r"^(?:https?://|mailto:)", href):
            return match.group(0)
        target = href.split("#", 1)[0]
        path = (docs_dir / target).resolve()
        if path in source:
            return f'href="{source[path]}"'
        repo = REPO.resolve()
        if path == repo or repo in path.parents:
            if not path.is_file():
                warnings.append(f"link target is not present yet: {href}")
            return f'href="{GITHUB_BLOB}{path.relative_to(repo).as_posix()}"'
        raise ReportError(f"relative link points outside the repository: {href}")

    original_links = re.findall(r'href="' + re.escape(GITHUB_BLOB) + r'([^"]+)"', article)
    rewritten = re.sub(r'href="([^"]+)"', replace, article)
    for link in original_links:
        if not (REPO / link).is_file():
            warnings.append(f"GitHub link target is not present yet: {link}")
    return rewritten


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

def _extract_blocks(template: str) -> tuple[str, dict[str, str]]:
    blocks = {}
    for match in re.finditer(r'<template data-block="([a-z-]+)">(.*?)</template>', template, re.S):
        blocks[match.group(1)] = match.group(2).strip()
    missing = {name for _, name in INSERTS} - set(blocks)
    if missing:
        raise ReportError(f"template is missing demo blocks: {sorted(missing)}")
    template = re.sub(r'<template data-block="[a-z-]+">.*?</template>\s*', "", template, flags=re.S)
    return template, blocks


def _escape_script_json(value: object) -> str:
    """Serialise JSON so that it can never terminate the enclosing script tag."""
    text = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render_report(
    *,
    source: Path = SOURCE_MD,
    template_path: Path = TEMPLATE,
    simulator_path: Path = SIMULATOR,
    reports_dir: Path = REPORTS,
    latest_path: Path = LATEST,
    docs_dir: Path | None = None,
    refactor_path: Path = REFACTOR_REPORT,
    warnings: list[str] | None = None,
) -> str:
    data = load_report_data(reports_dir, latest_path)
    if warnings is not None:
        # Old reports that omit input/output hashes are accepted by the
        # documented compatibility rule; surface that instead of silently filling.
        warnings.extend(data["compatibility_notes"])
    # The refactor acceptance belongs to the fixed V8 release: compare it with
    # docs/reports/v8.json, never with the current best pointer or report.
    archived_v8 = data["reports"].get(V8_REFERENCE_VERSION)
    refactor = load_refactor_status(refactor_path, archived_v8)
    docs_dir = docs_dir or source.parent
    markdown_text = source.read_text(encoding="utf-8")
    check_markdown_numbers(markdown_text, data)
    article, toc_tokens = markdown_to_html(markdown_text, docs_dir)
    # The hero already carries the document title; drop the Markdown H1 so the
    # article starts with the reading-status note.
    article = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", article, count=1, flags=re.S)
    # Markdown tables need the same horizontal scroll container as the demos.
    article = re.sub(r"(<table>.*?</table>)", r'<div class="table-wrap">\1</div>',
                     article, flags=re.S)
    article = rewrite_links(article, docs_dir, warnings)

    template, blocks = _extract_blocks(template_path.read_text(encoding="utf-8"))
    article = insert_blocks(article, blocks)

    latest = data["latest"]
    historical = data["historical"]
    v1 = next(row for row in historical if row["version"] == "v1")
    best = next(row for row in historical if row["version"] == latest["version"])
    newest = historical[-1]
    current = next(row for row in historical if row["version"] == newest["version"])
    current_status = data["statuses"][newest["version"]]
    delta = (v1["score"] - current["score"]) * 100 / v1["score"]
    current_note = ("报告支持，未附 CSV" if current_status == "report-only"
                    else "可下载归档 CSV")
    tokens = {
        "ARTICLE": article,
        "TOC": render_toc(toc_tokens),
        "CURRENT_LABEL": f"当前算法 {current['version'].upper()}"
                         + (" · 历史独立研究" if current_status == "report-only" else ""),
        "CURRENT_SCORE": f"{current['score']:,}",
        "CURRENT_SUMMARY": (f"条指令 · {current['validated']:,} / {current['puzzles']:,} "
                            f"题通过 · {current_note}"),
        "ARCHIVE_LABEL": f"可下载最佳归档 {latest['version'].upper()}",
        "ARCHIVE_SCORE": f"{latest['score']:,}",
        "V1_SCORE": f"V1 {v1['score']:,} 步",
        "CURRENT_DELTA": f"较 V1 少 {delta:.2f}%",
        "SCORE_BARS": score_bars(data),
        "REFACTOR_BODY": render_refactor_panel(refactor),
        "SCORE_DATA": _escape_script_json(score_payload(data)),
        "SIM_SOURCE": _escape_script_json(simulator_path.read_text(encoding="utf-8")),
    }
    for name, value in tokens.items():
        template = template.replace("{{" + name + "}}", value)
    unresolved = re.findall(r"\{\{[A-Z_]+\}\}", template)
    if unresolved:
        raise ReportError(f"unresolved template tokens: {sorted(set(unresolved))}")

    for required in REQUIRED_IDS:
        count = len(re.findall(rf'\bid="{re.escape(required)}"', template))
        if count != 1:
            raise ReportError(f"report must contain exactly one #{required} element, found {count}")
    return template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the checked-in report is stale")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="write the report here")
    args = parser.parse_args(argv)
    warnings: list[str] = []
    try:
        content = render_report(warnings=warnings)
        if args.check:
            try:
                current = args.output.read_text(encoding="utf-8")
            except FileNotFoundError:
                raise ReportError(
                    f"{args.output} does not exist; run python "
                    "competitions/santa-2026/docs/build_report.py"
                )
            if current != content:
                raise ReportError(
                    f"{args.output} is stale; run python "
                    "competitions/santa-2026/docs/build_report.py"
                )
            print(f"{args.output} is up to date")
            return 0
        args.output.write_text(content, encoding="utf-8")
        print(args.output)
        for warning in sorted(set(warnings)):
            print(f"warning: {warning}", file=sys.stderr)
        return 0
    except (OSError, ReportError) as exc:
        print(f"report build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
