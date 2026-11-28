"""Durable current-solver group checkpoints, never seeded from prior submissions."""
import csv
import fcntl
import hashlib
import json
import os
import platform
import sqlite3
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

import numpy
import scipy
from algorithms.common import replay
from algorithms.solver import ROUTES, SOLVER_VERSION, choose, solve_group
from verify import verify

SRC = Path(__file__).resolve().parent
SCHEMA = 5
BOUND_SOURCES = ("checkpoint.py", "graph_solver.py", "verify.py") + tuple(sorted(
    p.relative_to(SRC).as_posix() for p in (SRC / "algorithms").rglob("*")
    if p.is_file() and p.suffix in {".py", ".cpp", ".h", ".hpp", ".json"}
    and "__pycache__" not in p.parts))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def fingerprint(puzzles, split, manifest):
    return canon({"schema": SCHEMA, "version": SOLVER_VERSION, "input": sha(puzzles),
                  "split": split, "python": sys.version, "platform": platform.platform(),
                  "numpy": numpy.__version__, "scipy": scipy.__version__,
                  "threads": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONHASHSEED")},
                  "sources": {name: sha(SRC / name) for name in BOUND_SOURCES},
                  "compiler": manifest["compiler"], "flags": manifest["flags"],
                  "compat_include": manifest["compat_include"],
                  "binaries": {k: v["sha256"] for k, v in manifest["binaries"].items()}})


def validate_group(row, result):
    programs, scores = result["programs"], result["scores"]
    if result["id"] != row["id"] or not programs or programs.keys() != scores.keys():
        raise ValueError("checkpoint group identity or candidate inventory mismatch")
    for name, program in programs.items():
        if type(scores[name]) is not int or replay(row, program) != scores[name]:
            raise ValueError("checkpoint candidate score mismatch")


def digest(meta, pid, group, payload):
    return hashlib.sha256(canon([meta, pid, group, payload]).encode()).hexdigest()


@contextmanager
def open_checkpoint(path, resume, meta, rows):
    if path is None:
        yield {}, lambda *args: None
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if path.exists() != resume:
            raise ValueError("use --resume only with an existing checkpoint; otherwise choose a fresh path")
        db = sqlite3.connect(path)
        try:
            if resume:
                try:
                    old = db.execute("SELECT value FROM metadata").fetchone()
                except sqlite3.Error as exc:
                    raise ValueError("legacy or invalid checkpoint; start a new database") from exc
                if old != (meta,):
                    raise ValueError("checkpoint fingerprint changed; start a new database")
            else:
                with db:
                    db.execute("CREATE TABLE metadata (value TEXT NOT NULL)")
                    db.execute("INSERT INTO metadata VALUES (?)", (meta,))
                    db.execute("CREATE TABLE groups (id TEXT, route TEXT, payload TEXT, digest TEXT, PRIMARY KEY(id, route))")
            saved = {}
            for pid, group, raw, checksum in db.execute("SELECT id, route, payload, digest FROM groups"):
                if pid not in rows or group not in ROUTES or checksum != digest(meta, pid, group, raw):
                    raise ValueError("checkpoint record identity or digest mismatch")
                result = json.loads(raw)
                validate_group(rows[pid], result)
                saved[pid, group] = result

            def commit(pid, group, result):
                # Do not sort program keys: frozen tie-breaking depends on insertion order.
                raw = json.dumps(result, separators=(",", ":"))
                with db:
                    db.execute("INSERT INTO groups VALUES (?, ?, ?, ?)", (pid, group, raw, digest(meta, pid, group, raw)))
            yield saved, commit
        finally:
            db.close()


def export(puzzles, rows, saved, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        tmp = Path(tmp)
        candidate = tmp / "submission.csv"
        with candidate.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(("id", "program"))
            for pid, row in rows.items():
                _, program, _ = choose(row, {g: saved[pid, g] for g in ROUTES})
                writer.writerow((pid, json.dumps(program, separators=(",", ":"))))
        subset = tmp / "puzzles.csv"
        with subset.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(next(iter(rows.values()))))
            writer.writeheader()
            writer.writerows(rows.values())
        report = verify(subset, candidate)
        # The independent validator hashes the actual input for full runs.
        with puzzles.open(newline="", encoding="utf-8") as f:
            if list(csv.DictReader(f)) == list(rows.values()):
                report = verify(puzzles, candidate)
        os.link(candidate, output)  # atomic publication; never overwrite a result
        return report


def run(puzzles, rows, output, manifest, *, checkpoint=None, resume=False, jobs=4, split="all", limit=None):
    meta = fingerprint(puzzles, split, manifest)
    with open_checkpoint(checkpoint, resume, meta, rows) as (saved, commit):
        ordered = sorted(rows, key=lambda pid: -sum((pid, g) in saved for g in ROUTES))
        tasks = [(pid, g) for pid in ordered for g in ROUTES if (pid, g) not in saved]
        if limit is not None:
            tasks = tasks[:limit]
        failures = []
        if tasks:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                futures = {pool.submit(solve_group, g, rows[pid]): (pid, g) for pid, g in tasks}
                for future in as_completed(futures):
                    pid, group = futures[future]
                    try:
                        result = future.result()
                        validate_group(rows[pid], result)
                    except Exception as exc:
                        failures.append((pid, group, repr(exc)))
                        print(f"FAIL {pid} {group}: {exc!r}", flush=True)
                        continue
                    commit(pid, group, result)
                    saved[pid, group] = result
                    print(pid, group, min(result["scores"].values()), flush=True)
        complete = [pid for pid in rows if all((pid, g) in saved for g in ROUTES)]
        score = sum(min(len(p) for g in ROUTES for p in saved[pid, g]["programs"].values()) for pid in complete)
        print(f"SUMMARY {len(complete)}/{len(rows)} puzzles · {score} instructions", flush=True)
        if failures:
            raise ValueError(f"{len(failures)} group(s) failed; no output exported")
        if len(complete) != len(rows):
            if checkpoint is None or limit is None:
                raise ValueError("refuse to export incomplete submission")
            return None
        if limit is not None:  # preserve frozen runner's bounded-run semantics
            return None
        return export(puzzles, rows, saved, output)
