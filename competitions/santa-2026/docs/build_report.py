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
OUTPUT = SANTA / "Santa-2026-Interactive-Report.html"
GITHUB_BLOB = "https://github.com/Leonardo-F/kaggle-lab/blob/main/"

# Demo blocks placed after a stable heading anchor.  The anchors are produced by
# the Markdown ``toc`` extension with its Unicode slugify, not by matching the
# heading text position.
INSERTS = (
    ("01-赛题与手算", "lab"),
    ("41-依赖替换与引用计数v2v3", "compare"),
    ("71-同一批-1000-题的本地成绩", "scores"),
    ("101-候选池中的精确图选择模型", "research"),
)
REQUIRED_IDS = (
    "lab", "live-graph", "walk-slider", "walk-play", "walk-prev", "walk-next",
    "walk-reset", "step-readout", "op-line", "coverage", "visible-regs",
    "instruction-code", "compare", "scores", "chart-detail", "score-data",
    "sim-source", "sim-gate", "sim-frame",
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

def load_report_data(reports_dir: Path = REPORTS, latest_path: Path = LATEST) -> dict:
    """Load and cross-check historical reports and the best verified submission."""
    latest = _read_json(latest_path)
    for key in ("version", "score", "validated", "local_filename", "report"):
        if key not in latest:
            raise ReportError(f"{latest_path} is missing the {key!r} field")
    report_path = (latest_path.parent / latest["report"]).resolve()
    if not report_path.is_file():
        raise ReportError(f"latest.json points to a missing report: {report_path}")
    report = _read_json(report_path)
    for key in ("version", "score", "validated"):
        if key in report and report[key] != latest[key]:
            raise ReportError(
                f"latest.json {key}={latest[key]!r} disagrees with {report_path.name} "
                f"{key}={report[key]!r}"
            )
    submission = latest_path.parent / latest["local_filename"]
    if not submission.is_file():
        raise ReportError(f"latest.json points to a missing submission CSV: {submission}")
    expected_hash = latest.get("submission_sha256")
    if expected_hash and _sha256(submission) != expected_hash:
        raise ReportError(f"submission SHA-256 does not match latest.json: {submission}")

    versions = []
    for path in sorted(reports_dir.glob("v[0-9]*.json")):
        if not re.fullmatch(r"v[0-9]+\.json", path.name):
            continue
        data = _read_json(path)
        version = data.get("version")
        if not version or not re.fullmatch(r"v[0-9]+", str(version)):
            raise ReportError(f"{path.name} does not declare a version field")
        if not isinstance(data.get("score"), int) or not isinstance(data.get("validated"), int):
            raise ReportError(f"{path.name} needs integer score and validated fields")
        versions.append({
            "version": version,
            "score": data["score"],
            "validated": data["validated"],
            "puzzles": data.get("puzzles", data["validated"]),
        })
    versions.sort(key=lambda row: int(row["version"][1:]))
    if not versions:
        raise ReportError(f"no historical reports found in {reports_dir}")
    if latest["version"] not in {row["version"] for row in versions}:
        raise ReportError(f"latest.json version {latest['version']!r} has no report")
    return {
        "latest": latest,
        "latest_report": report,
        "historical": versions,
        "submission": submission,
    }


def check_markdown_numbers(markdown_text: str, data: dict) -> None:
    """Fail when the document and the machine-readable reports disagree."""
    for row in data["historical"]:
        score = f"{row['score']:,}"
        if score not in markdown_text:
            raise ReportError(
                f"algorithm-evolution.md does not contain {row['version'].upper()} score "
                f"{score} from docs/reports/{row['version']}.json"
            )
    latest = data["latest"]
    if f"{latest['score']:,}" not in markdown_text:
        raise ReportError(
            f"algorithm-evolution.md does not contain the latest verified score "
            f"{latest['score']:,} from submissions/latest.json"
        )


def score_payload(data: dict) -> list[dict]:
    return [
        {"version": row["version"].upper(), "score": row["score"], "validated": row["validated"]}
        for row in data["historical"]
    ]


def score_bars(data: dict) -> str:
    items = []
    for index, row in enumerate(data["historical"]):
        items.append(
            '<li><button type="button" class="bar-row" data-score="%d" aria-pressed="false">'
            '<span>%s</span><span class="bar-track" aria-hidden="true">'
            '<span class="bar-fill"></span></span><span class="bar-count">%s</span>'
            "</button></li>"
            % (index, row["version"].upper(), f"{row['score']:,}")
        )
    return "\n".join(items)


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
    warnings: list[str] | None = None,
) -> str:
    data = load_report_data(reports_dir, latest_path)
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
    delta = (v1["score"] - latest["score"]) * 100 / v1["score"]
    validated = f"{latest['validated']:,}"
    puzzles = f"{best['puzzles']:,}"
    tokens = {
        "ARTICLE": article,
        "TOC": render_toc(toc_tokens),
        "BEST_LABEL": f"{latest['version'].upper()} Final 全量独立验证",
        "BEST_SCORE": f"{latest['score']:,}",
        "BEST_SUMMARY": f"条指令 · {validated} / {puzzles} 题通过",
        "V1_SCORE": f"V1 {v1['score']:,} 步",
        "BEST_DELTA": f"较 V1 少 {delta:.2f}%",
        "SCORE_BARS": score_bars(data),
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
