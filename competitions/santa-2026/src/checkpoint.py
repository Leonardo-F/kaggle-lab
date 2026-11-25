"""Crash-safe, resumable execution of the single functional Santa solver.

Each solved puzzle is replayed and committed in its own durable SQLite
transaction.  A checkpoint is bound to the exact input file, the CLI,
checkpoint and verifier sources, every file in ``algorithms/``, the Python
implementation and the solver parameters, so a resumed run can only continue
the same experiment.  No submission is exported until every input ID has been
collected and the complete CSV passes the independent verifier.

Checkpoints written by the legacy V1-V8 layout (schema 1) are rejected: resume
them with the original Git commit, or start a new SQLite file.
"""
import csv
import fcntl
import hashlib
import json
import os
import platform
import sqlite3
import time
from contextlib import closing
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from algorithms.solver import DEFAULT_CONFIG, STAGES
from verify import verify

SRC = Path(__file__).resolve().parent
SCHEMA = 2
LAYOUT = "functional"

ALGORITHM_SOURCES = tuple(sorted(
    path.relative_to(SRC).as_posix()
    for path in (SRC / "algorithms").rglob("*.py")
    if "__pycache__" not in path.parts
))
BOUND_SOURCES = ("checkpoint.py", "graph_solver.py", "verify.py") + ALGORITHM_SOURCES

CONFIGS = {
    "v8": {
        "stages": STAGES,
        "baseline": "v7",
        "final": "v8final",
        "parameters": tuple(DEFAULT_CONFIG),
    },
}

DEFAULTS = {"v8": dict(DEFAULT_CONFIG)}


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
    stages = CONFIGS[version]["stages"]
    costs = [metrics[k] for k in stages]
    if any(type(x) is not int or x < 0 for x in costs) or costs[-1] != len(program):
        raise ValueError(f'{row["id"]}: invalid metrics')
    if any(a < b for a, b in zip(costs, costs[1:])):
        raise ValueError(f'{row["id"]}: increasing candidate cost')


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
        sources={name: sha(SRC / name) for name in BOUND_SOURCES},
        parameters={key: parameters[key] for key in config["parameters"]},
    )


def _is_legacy_metadata(payload):
    try:
        stored = json.loads(payload)
    except (TypeError, ValueError):
        return False
    return not (isinstance(stored, dict)
                and stored.get("schema") == SCHEMA
                and stored.get("layout") == LAYOUT)


def run_checkpoint(puzzles, output, checkpoint, version="v8", jobs=4, resume=False,
                   stop_after=None, parameters=None):
    """Solve ``puzzles`` with the functional solver, persisting every result."""
    if version not in CONFIGS:
        raise ValueError(f"the functional solver only supports v8, not {version}")
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
                if _is_legacy_metadata(stored[0]):
                    raise ValueError(
                        "checkpoint uses the legacy versioned layout; resume it with the original "
                        "Git commit (9337a35) or create a new SQLite file"
                    )
                if stored[0] != metadata:
                    raise ValueError("checkpoint provenance mismatch: input, source, Python or parameters changed")
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
