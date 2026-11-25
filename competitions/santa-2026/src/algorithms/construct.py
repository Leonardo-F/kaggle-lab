"""Four-route native dictionary construction.

``construct`` launches one of the two frozen C++17 constructor kernels on one
official puzzle row and strictly parses the value-DAG protocol it prints.  The
kernels build a finite multi-expression dictionary from the puzzle's own
starting values; they never read archived submissions, checkpoints or answers.

Protocol (the frozen research contract):

* argv: ``constructor <width> <mode>``
* stdin: ``limit count_start count_target start... target...``
* stdout: ``count`` followed by one ``value op left right`` line per node, in
  dependency (post-order) order.  Values already present in the starting set
  or materialised by the kernel's seed are emitted as nodes too, so the graph
  is self-contained.

Every line is checked for shape, arithmetic identity, range, duplicate
producers, dependency order and final target coverage.  A malformed protocol
must never be sanitised into a candidate.
"""

import json
import subprocess

from .common import arithmetic

SIGNED_64_MAX = 2 ** 63 - 1
TIMEOUT_SECONDS = 45
OPERATORS = frozenset('+-*/')
_BINARY_CACHE = None  # (manifest signature, kernel -> path)


def _manifest_signature():
    """Cheap identity of the current native build manifest for cache invalidation."""
    from .native import build as native_build
    path = native_build.BUILD_DIR / "manifest.json"
    try:
        stat = path.stat()
        return (str(native_build.BUILD_DIR), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return (str(native_build.BUILD_DIR), None, None)


def binary_paths():
    """Kernel name -> absolute binary path, built lazily and cached per process.

    The cache is keyed by the manifest file signature, so a rebuild (for
    example after switching ``SANTA_CXX`` or using ``--force``) is noticed even
    in a long-lived process; a stale binary path can never stay bound to a new
    checkpoint fingerprint.
    """
    global _BINARY_CACHE
    signature = _manifest_signature()
    if _BINARY_CACHE is None or _BINARY_CACHE[0] != signature:
        from .native.build import binaries
        _BINARY_CACHE = (_manifest_signature(), binaries())
    return _BINARY_CACHE[1]


def reset_binaries():
    """Forget the cached build (tests and long-lived research shells)."""
    global _BINARY_CACHE
    _BINARY_CACHE = None


def puzzle_numbers(row):
    """Parse and range-check the integers sent to the native kernels."""
    starting = json.loads(row['starting_values'])
    targets = json.loads(row['targets'])
    limit = int(row['value_limit'])
    if type(limit) is not int or not 0 < limit <= SIGNED_64_MAX:
        raise ValueError(f"{row.get('id', '?')}: value_limit outside the native signed 64-bit range")
    for label, values in (('starting_values', starting), ('targets', targets)):
        if not isinstance(values, list) or not values:
            raise ValueError(f"{row.get('id', '?')}: {label} must be a nonempty list")
        for value in values:
            if type(value) is not int or not 0 < value <= SIGNED_64_MAX:
                raise ValueError(
                    f"{row.get('id', '?')}: {label} value outside the native signed 64-bit range"
                )
            if value > limit:
                raise ValueError(f"{row.get('id', '?')}: {label} value exceeds value_limit")
    if len(set(starting)) != len(starting):
        raise ValueError(f"{row.get('id', '?')}: duplicate starting values")
    if len(starting) > int(row['registers']):
        raise ValueError(f"{row.get('id', '?')}: more starting values than registers")
    return starting, targets, limit


def parse_graph(text, row):
    """Strictly parse the native ``value op left right`` graph protocol."""
    starting, targets, limit = puzzle_numbers(row)
    start = set(starting)
    lines = text.splitlines()
    if not lines or not lines[0].strip().isdigit():
        raise ValueError(f"{row.get('id', '?')}: native constructor emitted no protocol header")
    count = int(lines[0].strip())
    body = [line for line in lines[1:] if line.strip()]
    if len(body) != count:
        raise ValueError(
            f"{row.get('id', '?')}: native constructor declared {count} nodes but emitted {len(body)}"
        )
    graph = {}
    for number, line in enumerate(body, start=1):
        parts = line.split()
        if len(parts) != 4:
            raise ValueError(f"{row.get('id', '?')}: malformed native node line {number}: {line!r}")
        value_text, op, left_text, right_text = parts
        try:
            value, left, right = int(value_text), int(left_text), int(right_text)
        except ValueError as exc:
            raise ValueError(
                f"{row.get('id', '?')}: non-integer native node line {number}: {line!r}"
            ) from exc
        if op not in OPERATORS:
            raise ValueError(f"{row.get('id', '?')}: unknown native operator {op!r} on line {number}")
        if not 1 <= value <= limit:
            raise ValueError(f"{row.get('id', '?')}: native value {value} outside 1..{limit}")
        if value in graph or value in start:
            raise ValueError(f"{row.get('id', '?')}: duplicate native producer for value {value}")
        for operand in (left, right):
            if operand in start:
                continue
            if operand not in graph:
                raise ValueError(
                    f"{row.get('id', '?')}: native node {value} depends on undefined value {operand}"
                )
        try:
            produced = arithmetic(op, left, right)
        except ValueError as exc:
            raise ValueError(
                f"{row.get('id', '?')}: native node {value} does not satisfy {left} {op} {right}"
            ) from exc
        if produced != value:
            raise ValueError(
                f"{row.get('id', '?')}: native node {value} does not satisfy {left} {op} {right}"
            )
        graph[value] = (op, left, right)
    missing = [value for value in targets if value not in start and value not in graph]
    if missing:
        raise ValueError(
            f"{row.get('id', '?')}: native graph is missing {len(missing)} target(s): {missing[:3]}"
        )
    return graph


def construct(row, width, mode, kernel, binary=None, timeout=TIMEOUT_SECONDS):
    """Run one native kernel and return its validated value DAG."""
    from .native.build import KERNELS
    if kernel not in KERNELS:
        raise ValueError(f"unknown native constructor kernel: {kernel!r}")
    if type(width) is not int or width < 1:
        raise ValueError(f"invalid native constructor width: {width!r}")
    if type(mode) is not int or mode < 0:
        raise ValueError(f"invalid native constructor mode: {mode!r}")
    starting, targets, limit = puzzle_numbers(row)
    executable = binary if binary is not None else binary_paths()[kernel]
    payload = ' '.join(map(str, [limit, len(starting), len(targets), *starting, *targets]))
    try:
        result = subprocess.run(
            [str(executable), str(width), str(mode)],
            input=payload, text=True, capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"{row.get('id', '?')}: native {kernel} timed out after {timeout}s"
        ) from exc
    except OSError as exc:
        raise ValueError(f"{row.get('id', '?')}: cannot run native {kernel}: {exc}") from exc
    if result.returncode != 0:
        stderr = (result.stderr or '').strip().splitlines()
        detail = stderr[0] if stderr else 'no stderr'
        raise ValueError(
            f"{row.get('id', '?')}: native {kernel} exited {result.returncode}: {detail}"
        )
    return parse_graph(result.stdout, row)
