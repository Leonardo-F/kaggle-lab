"""Crash-safe, resumable execution of the single functional Santa solver.

Each solved puzzle is replayed and committed in its own durable SQLite
transaction.  A checkpoint is bound to the exact input file, the CLI, the
checkpoint and verifier sources, every production Python file in
``algorithms/`` (including the native build helper and its ``.cpp`` sources and
headers), the actual compiled binary hashes, the compiler identity/flags, the
Python implementation/platform and the frozen solver parameters, so a resumed
run can only continue the same experiment.  No submission is exported until
every input ID has been collected and the complete CSV passes the independent
verifier.

Layouts older than schema 3 are rejected: resume a V1-V7 checkpoint with the
historical versioned-layout commit, a V8 functional-layout checkpoint with the
V8 baseline commit, or start a new SQLite file.  The safety checks are never
relaxed to make an old file resumable.
"""

import csv
import fcntl
import hashlib
import json
import os
import platform
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import closing
from pathlib import Path

from algorithms.solver import DEFAULT_CONFIG, STAGES
from algorithms.native import build as native_build
from verify import verify

SRC = Path(__file__).resolve().parent
SCHEMA = 3
LAYOUT = "v9-functional"
LEGACY_REVISIONS = {
    "versioned": "9337a3549bea09257cbf36ae1f8da2cbd452942b",
    "functional": "287519977aa85a19ef9e3074e6bfd2b9e578b5c3",
}

ALGORITHM_SOURCES = tuple(sorted(
    path.relative_to(SRC).as_posix()
    for path in (SRC / "algorithms").rglob("*")
    if path.is_file() and "__pycache__" not in path.parts
    and path.suffix in {".py", ".cpp", ".h", ".hpp"}
))
BOUND_SOURCES = ("checkpoint.py", "graph_solver.py", "verify.py") + ALGORITHM_SOURCES

CONFIGS = {
    "v9": {
        "stages": STAGES,
        "baseline": "v9_stage1",
        "final": "v9final",
        "parameters": tuple(DEFAULT_CONFIG),
    },
}

DEFAULTS = {"v9": dict(DEFAULT_CONFIG)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canon(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def record_digest(pid, program, metrics, meta):
    return hashlib.sha256(canon([meta, pid, program, metrics]).encode()).hexdigest()


def solve_job(job):
    """Worker entry point: the same public solver used by the CLI."""
    row, parameters = job
    from algorithms.solver import solve
    return solve(row, parameters)


def validate_record(version, row, program, metrics):
    from algorithms.common import replay
    if replay(row, program) != len(program):
        raise ValueError(f'{row["id"]}: replay count mismatch')
    config = CONFIGS[version]
    stages = config["stages"]
    costs = [metrics[k] for k in stages]
    if any(type(x) is not int or x < 0 for x in costs) or costs[-1] != len(program):
        raise ValueError(f'{row["id"]}: invalid stage metrics')
    if any(a < b for a, b in zip(costs, costs[1:])):
        raise ValueError(f'{row["id"]}: increasing incumbent cost')
    for key in ("nodes", "schedule_attempts"):
        if type(metrics.get(key)) is not int or metrics[key] < 0:
            raise ValueError(f'{row["id"]}: invalid {key} metric')
    routes = metrics.get("routes")
    expected = len(DEFAULT_CONFIG["stage1_routes"])
    if type(routes) is not list or len(routes) != expected:
        raise ValueError(f'{row["id"]}: invalid route metrics')
    for entry in routes:
        if not isinstance(entry, dict) or not isinstance(entry.get("config"), list):
            raise ValueError(f'{row["id"]}: invalid route entry')
        if len(entry["config"]) != 3 or type(entry["config"][1]) is not int:
            raise ValueError(f'{row["id"]}: invalid route configuration')
        error = entry.get("error")
        if error is not None:
            if not isinstance(error, str) or entry.get("nodes") is not None or entry.get("score") is not None:
                raise ValueError(f'{row["id"]}: malformed failed route')
            continue
        if any(type(entry.get(key)) is not int or entry[key] < 0 for key in ("nodes", "score")):
            raise ValueError(f'{row["id"]}: invalid route score')


def atomic_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_rows(puzzles):
    with puzzles.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"id", "starting_values", "targets", "value_limit", "registers"} <= set(reader.fieldnames or []):
            raise ValueError("official puzzle CSV required")
        rows = list(reader)
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("input must contain nonempty unique IDs")
    return rows


def native_binding():
    """Compiler, flags and binary hashes of the native constructors used for this run."""
    manifest = native_build.ensure_built()
    return {
        "compiler": dict(manifest["compiler"]),
        "flags": list(manifest["flags"]),
        "compat_include": bool(manifest.get("compat_include")),
        "binaries": {kernel: info["sha256"] for kernel, info in manifest["binaries"].items()},
        "sources": dict(manifest["sources"]),
    }


def fingerprint(version, puzzles, rows, parameters):
    config = CONFIGS[version]
    return dict(
        schema=SCHEMA,
        layout=LAYOUT,
        version=version,
        input_sha256=sha(puzzles),
        count=len(rows),
        python=platform.python_version(),
        implementation=platform.python_implementation(),
        platform={"system": platform.system(), "machine": platform.machine()},
        sources={name: sha(SRC / name) for name in BOUND_SOURCES},
        native=native_binding(),
        parameters={key: parameters[key] for key in config["parameters"]},
    )


def _layout_of(payload):
    try:
        stored = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(stored, dict):
        return None
    return stored.get("layout")


def _reject_legacy_metadata(payload):
    layout = _layout_of(payload)
    if layout == "versioned":
        raise ValueError(
            "checkpoint uses the legacy versioned layout; resume it with the original "
            f"Git commit ({LEGACY_REVISIONS['versioned']}) or create a new SQLite file"
        )
    if layout == "functional":
        raise ValueError(
            "checkpoint uses the V8 functional layout (schema 2); resume it with the V8 "
            f"baseline commit ({LEGACY_REVISIONS['functional']}) or create a new SQLite file"
        )
    raise ValueError(
        "checkpoint layout is not the current v9-functional schema; "
        "resume it with the commit that produced it or create a new SQLite file"
    )


def run_checkpoint(puzzles, output, checkpoint, version="v9", jobs=4, resume=False,
                   stop_after=None, parameters=None):
    """Solve ``puzzles`` with the frozen solver, persisting every result."""
    if version not in CONFIGS:
        hint = ""
        if version == "v8":
            hint = f" resume it with the V8 baseline commit ({LEGACY_REVISIONS['functional']})"
        raise ValueError(f"the functional solver only supports v9, not {version};{hint}")
    config = CONFIGS[version]
    stages = config["stages"]
    resolved = dict(DEFAULTS[version])
    if parameters is not None:
        unknown = set(parameters) - set(config["parameters"])
        if unknown:
            raise ValueError(f"unknown parameters: {sorted(unknown)}")
        resolved.update(parameters)
    parameters = resolved
    missing = [key for key in config["parameters"] if key not in parameters]
    if missing:
        raise ValueError(f"missing parameters: {missing}")
    rows = read_rows(puzzles)
    row_by_id = {row["id"]: row for row in rows}
    native_build.ensure_built()
    metadata = canon(fingerprint(version, puzzles, rows, parameters))
    started = time.monotonic()
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with open(str(checkpoint) + ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("checkpoint is locked by another running experiment") from exc
        exists = checkpoint.exists()
        if exists != resume:
            raise ValueError("existing checkpoint requires --resume; resume requires existing checkpoint")
        with closing(sqlite3.connect(checkpoint)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            if not exists:
                with db:
                    db.execute("CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
                    db.execute("CREATE TABLE results (pid TEXT PRIMARY KEY, program TEXT NOT NULL, "
                               "metrics TEXT NOT NULL, digest TEXT NOT NULL)")
                    db.execute("INSERT INTO meta VALUES (1,?)", (metadata,))
            else:
                stored = db.execute("SELECT payload FROM meta WHERE id=1").fetchone()
                if stored is None:
                    raise ValueError("checkpoint has no provenance metadata")
                stored_payload = stored[0]
                try:
                    stored_layout = json.loads(stored_payload).get("layout")
                except (TypeError, ValueError):
                    stored_layout = None
                if stored_layout != LAYOUT:
                    _reject_legacy_metadata(stored_payload)
                if stored_payload != metadata:
                    raise ValueError("checkpoint provenance mismatch: input, source, Python, "
                                     "native build or parameters changed")
            programs, metrics = {}, {}
            for pid, raw, mraw, digest in db.execute("SELECT pid,program,metrics,digest FROM results"):
                if pid not in row_by_id or digest != record_digest(pid, raw, mraw, metadata):
                    raise ValueError(f"checkpoint integrity error: {pid}")
                program, record_metrics = json.loads(raw), json.loads(mraw)
                validate_record(version, row_by_id[pid], program, record_metrics)
                programs[pid] = program
                metrics[pid] = record_metrics
            resumed = len(programs)
            todo = [row for row in rows if row["id"] not in programs]
            if stop_after is not None:
                todo = todo[:stop_after]
            print(f"checkpoint: {resumed}/{len(rows)}; scheduled {len(todo)}; jobs={jobs}", flush=True)
            totals = {stage: sum(record[stage] for record in metrics.values()) for stage in stages}
            with ProcessPoolExecutor(max_workers=jobs) as executor:
                futures = {executor.submit(solve_job, (row, parameters)): row["id"] for row in todo}
                for future in as_completed(futures):
                    pid, program, record_metrics = future.result()
                    if pid != futures[future] or pid in programs:
                        raise ValueError("worker returned an unexpected puzzle ID")
                    validate_record(version, row_by_id[pid], program, record_metrics)
                    raw, mraw = canon(program), canon(record_metrics)
                    with db:
                        db.execute("INSERT INTO results VALUES (?,?,?,?)",
                                   (pid, raw, mraw, record_digest(pid, raw, mraw, metadata)))
                    programs[pid] = program
                    metrics[pid] = record_metrics
                    for stage in stages:
                        totals[stage] += record_metrics[stage]
                    count = len(programs)
                    if count % 10 == 0 or count == len(rows) or count == resumed + len(todo):
                        print(f"{count}/{len(rows)} {config['final']}={totals[config['final']]} "
                              f"elapsed={time.monotonic() - started:.2f}s", flush=True)
            if len(programs) != len(rows):
                print(f"PARTIAL: {len(programs)}/{len(rows)}; no submission exported", flush=True)
                return None
            output.parent.mkdir(parents=True, exist_ok=True)
            temp = output.with_name(output.name + ".tmp")
            try:
                with temp.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(("id", "program"))
                    for row in rows:
                        writer.writerow((row["id"], json.dumps(programs[row["id"]], separators=(",", ":"))))
                    stream.flush()
                    os.fsync(stream.fileno())
                report = verify(puzzles, temp)
                if report["score"] != totals[config["final"]]:
                    raise ValueError("score mismatch between checkpoint totals and independent replay")
                report.update(totals)
                final, baseline = config["final"], config["baseline"]
                report.update(
                    version=version,
                    resumed_at_start=resumed,
                    session_elapsed_seconds=round(time.monotonic() - started, 2),
                    improved=sum(record[final] < record[baseline] for record in metrics.values()),
                    unchanged=sum(record[final] == record[baseline] for record in metrics.values()),
                    worse=sum(record[final] > record[baseline] for record in metrics.values()),
                    fingerprint=fingerprint(version, puzzles, rows, parameters),
                )
                os.replace(temp, output)
            finally:
                if temp.exists():
                    temp.unlink()
            atomic_json(Path(str(output) + ".metrics.json"), metrics)
            atomic_json(Path(str(output) + ".validation.json"), report)
            print(json.dumps(report, indent=2), flush=True)
            return report
