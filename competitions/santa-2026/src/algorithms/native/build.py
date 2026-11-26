"""Build the seven frozen C++17 constructor kernels used by the V10 solver.

The ``.cpp`` sources are byte-identical to the frozen V10 research handoff and
are compiled before a solve starts into ``competitions/santa-2026/experiments/
native-build/`` (git-ignored).  The bundled research archive contains prebuilt
ELF binaries; those are never used as a release dependency.  V9 uses the first
two kernels and keeps working through the same manifest.

The build records the compiler identity (resolved path, ``--version`` line,
family), flags, whether the libstdc++ compatibility header was needed, source
hashes and binary hashes in ``manifest.json``.  The manifest is what the
checkpoint fingerprint binds, so a resumed run can only reuse the exact same
native pipeline.  Bump ``MANIFEST_SCHEMA`` whenever this module's build
contract changes.

An explicitly requested compiler (``SANTA_CXX`` or the ``explicit`` argument)
always wins: it has priority over a cached manifest, it is resolved through the
PATH/absolute-path/symlink rules below, and it is never silently replaced by
the cached compiler or by auto-detection.  When it is missing or unusable the
build fails loudly.  Without an explicit compiler the previous behaviour is
kept: a valid manifest is reused, otherwise the usual GCC-before-clang
candidate list is probed.

GCC/libstdc++ on Linux is the reference toolchain (the frozen full run used
``g++ -O3 -std=c++17``).  A compiler without libstdc++, such as Apple Clang,
is supported through the small ``compat/bits/stdc++.h`` forwarding header;
this module adds it only when a compiler probe shows the real aggregate header
is missing.  Compiler-dependent candidate ordering was checked against the
frozen per-puzzle records; see ``docs/progress.md`` for the exact platforms
and results.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

try:  # POSIX only; Windows would need a different lock, which is not shipped.
    import fcntl
except ImportError:  # pragma: no cover - CI and release platforms are POSIX
    fcntl = None

NATIVE_DIR = Path(__file__).resolve().parent
SANTA_ROOT = NATIVE_DIR.parents[2]
BUILD_DIR = Path(
    os.environ.get("SANTA_NATIVE_BUILD_DIR", SANTA_ROOT / "experiments" / "native-build")
)
COMPAT_DIR = NATIVE_DIR / "compat"
KERNELS = (
    "constructor_wide",
    "constructor_mitm",
    "constructor_pressure",
    "constructor_joint",
    "constructor_cf",
    "constructor_order_fast",
    "constructor_order_cf",
)
FLAGS = ("-O3", "-std=c++17")
MANIFEST_SCHEMA = 3
COMPILE_TIMEOUT = 180
SANTA_CXX_ENV = "SANTA_CXX"
COMPILER_CANDIDATES = (
    "g++-15", "g++-14", "g++-13", "g++-12", "g++-11", "g++-10", "g++", "c++",
)
PROBE_SOURCE = """\
#include <bits/stdc++.h>
#include <random>
int main() {
    __int128 big = 1;
    big <<= 100;
    std::mt19937_64 rng(1909);
    return (big == 0 || rng() == 0) ? 1 : 0;
}
"""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_metadata_junk(path):
    """macOS AppleDouble/sidecar files that must never enter a source fingerprint."""
    return any(part.startswith("._") or part == ".DS_Store" or part == "__pycache__"
               for part in path.parts)


def source_files():
    """Stable relative-path -> absolute-path map of build inputs."""
    files = {Path("build.py"): Path(__file__).resolve()}
    for kernel in KERNELS:
        files[Path(kernel + ".cpp")] = NATIVE_DIR / (kernel + ".cpp")
    for shim in sorted(COMPAT_DIR.rglob("*")):
        if not shim.is_file():
            continue
        relative = shim.relative_to(NATIVE_DIR)
        if _is_metadata_junk(relative):
            continue
        files[relative] = shim
    return {path.as_posix(): absolute for path, absolute in sorted(files.items())}


def _run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


def _normalize(path):
    """Absolute real path used as the compiler identity (symlinks resolved)."""
    return str(Path(path).resolve())


def _compiler_version(compiler):
    result = _run([str(compiler), "--version"])
    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        detail = stderr[0] if stderr else f"exit {result.returncode}"
        raise RuntimeError(f"cannot query compiler {compiler}: {detail}")
    first = (result.stdout.splitlines() or [""])[0]
    lower = first.lower()
    if "gcc" in lower or "g++" in lower or "free software foundation" in lower:
        family = "gcc"
    elif "clang" in lower:
        family = "clang"
    else:
        family = "unknown"
    return {"path": _normalize(compiler), "version": first, "family": family}


def _probe(compiler, include_compat):
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(BUILD_DIR)) as directory:
        source = Path(directory) / "probe.cpp"
        binary = Path(directory) / "probe"
        source.write_text(PROBE_SOURCE)
        command = [str(compiler), *FLAGS]
        if include_compat:
            command += ["-I", str(COMPAT_DIR)]
        command += ["-o", str(binary), str(source)]
        result = _run(command, timeout=COMPILE_TIMEOUT)
        return result.returncode == 0, result.stderr


def _probe_compat(compiler):
    """Return ``(usable, compat_include, stderr)`` for one concrete compiler path."""
    ok, stderr = _probe(compiler, include_compat=False)
    if ok:
        return True, False, ""
    ok, shim_stderr = _probe(compiler, include_compat=True)
    if ok:
        return True, True, ""
    return False, False, (stderr or shim_stderr)


def _resolve_candidate(candidate):
    """Resolve a compiler name/absolute path; return its real path or ``None``."""
    resolved = shutil.which(candidate)
    if resolved is None:
        expanded = Path(candidate).expanduser()
        if expanded.is_file():
            resolved = str(expanded)
        else:
            return None
    return _normalize(resolved)


def _requested_compiler(explicit=None):
    value = explicit if explicit is not None else os.environ.get(SANTA_CXX_ENV)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _explicit_compiler_info(requested):
    """Resolve and identify the explicitly requested compiler; fail loudly."""
    resolved = _resolve_candidate(requested)
    if resolved is None:
        raise RuntimeError(
            f"explicit compiler from {SANTA_CXX_ENV} {requested!r} was not found "
            "or is not executable; refusing to fall back to auto-detection"
        )
    try:
        return _compiler_version(resolved)
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(
            f"explicit compiler from {SANTA_CXX_ENV} {requested!r} is not usable: {exc}"
        ) from exc


def choose_compiler(explicit=None):
    """Return ``(version_info, compat_include)`` for the selected compiler.

    An explicit compiler (``SANTA_CXX``/``explicit``) is mandatory: it is
    resolved and probed on its own and any failure raises.  Otherwise the
    historical candidate order is probed and the first working compiler wins.
    """
    requested = _requested_compiler(explicit)
    if requested is not None:
        info = _explicit_compiler_info(requested)
        usable, compat, stderr = _probe_compat(info["path"])
        if not usable:
            detail = (stderr or "").strip().splitlines()[:1]
            raise RuntimeError(
                f"explicit compiler from {SANTA_CXX_ENV} {requested!r} "
                f"({info['version']}) cannot compile the C++17 probe: {detail}"
            )
        info = dict(info, source=SANTA_CXX_ENV)
        return info, compat

    failures = []
    for candidate in COMPILER_CANDIDATES:
        resolved = _resolve_candidate(candidate)
        if resolved is None:
            failures.append(f"{candidate}: not found")
            continue
        try:
            version = _compiler_version(resolved)
        except (OSError, RuntimeError) as exc:
            failures.append(f"{candidate}: {exc}")
            continue
        usable, compat, stderr = _probe_compat(resolved)
        if usable:
            return dict(version, source="auto"), compat
        failures.append(f"{candidate}: probe failed: {(stderr or '').strip().splitlines()[:1]}")
    detail = "; ".join(failures) or "no compiler candidates"
    raise RuntimeError(
        "no working C++17 compiler with __int128 support was found; "
        "install g++/libstdc++ (recommended) or set SANTA_CXX. " + detail
    )


def _expected_manifest():
    sources = source_files()
    return {
        "schema": MANIFEST_SCHEMA,
        "flags": list(FLAGS),
        "sources": {name: sha256(path) for name, path in sources.items()},
    }


def _manifest_matches(manifest, expected_compiler=None):
    """True only when the cached manifest describes the current build inputs.

    ``expected_compiler`` is the identity of the explicitly requested compiler
    (or ``None``).  When it is given, the cached compiler must be the exact
    same resolved binary/version/family; otherwise a rebuild is forced.
    """
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        return False
    expected = _expected_manifest()
    if manifest.get("flags") != expected["flags"]:
        return False
    if manifest.get("sources") != expected["sources"]:
        return False
    if not isinstance(manifest.get("compat_include"), bool):
        return False
    compiler = manifest.get("compiler") or {}
    path, version = compiler.get("path"), compiler.get("version")
    family = compiler.get("family")
    if not path or not version:
        return False
    if expected_compiler is not None:
        if (_normalize(path) != expected_compiler["path"]
                or version != expected_compiler["version"]
                or family != expected_compiler["family"]):
            return False
    else:
        if not Path(path).exists():
            return False
        try:
            current = _compiler_version(path)
        except (OSError, RuntimeError):
            return False
        if current["version"] != version or current["family"] != family:
            return False
    for kernel in KERNELS:
        info = (manifest.get("binaries") or {}).get(kernel) or {}
        binary = Path(info.get("path", ""))
        if binary != BUILD_DIR / kernel:
            return False
        if not binary.is_file() or sha256(binary) != info.get("sha256"):
            return False
    return True


def _lock():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(BUILD_DIR / ".lock", "a")
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def _smoke(binary):
    result = _run([str(binary), "6", "3"], input="100 1 1 3 9\n")
    if result.returncode != 0:
        raise RuntimeError(f"native smoke test failed for {binary.name}: {result.stderr.strip()}")
    lines = result.stdout.splitlines()
    if not lines or not lines[0].strip().isdigit():
        raise RuntimeError(f"native smoke test produced no protocol header for {binary.name}")


def _select_compiler(manifest, explicit_info):
    """Pick the compiler for a rebuild, honouring an explicit request first."""
    requested = _requested_compiler()
    if requested is not None:
        info = explicit_info or _explicit_compiler_info(requested)
        usable, compat, stderr = _probe_compat(info["path"])
        if not usable:
            detail = (stderr or "").strip().splitlines()[:1]
            raise RuntimeError(
                f"explicit compiler from {SANTA_CXX_ENV} {requested!r} "
                f"({info['version']}) cannot compile the C++17 probe: {detail}"
            )
        return dict(info, source=SANTA_CXX_ENV), compat
    cached = (manifest or {}).get("compiler") or {}
    if cached.get("path") and Path(cached["path"]).exists():
        try:
            info = _compiler_version(cached["path"])
            if info["version"] != cached.get("version") or info["family"] != cached.get("family"):
                raise RuntimeError("cached compiler version changed")
            usable, compat, _ = _probe_compat(info["path"])
            if usable:
                return dict(info, source=cached.get("source", "auto")), compat
        except (OSError, RuntimeError):
            pass
    return choose_compiler()


def _build_locked(manifest, explicit_info=None):
    info = dict(_expected_manifest())
    compiler, compat = _select_compiler(manifest, explicit_info)
    info.update(compiler=compiler, compat_include=compat)
    binaries = {}
    commands = []
    for kernel in KERNELS:
        source = NATIVE_DIR / (kernel + ".cpp")
        temporary = BUILD_DIR / (kernel + ".tmp")
        final = BUILD_DIR / kernel
        command = [compiler["path"], *FLAGS]
        if compat:
            command += ["-I", str(COMPAT_DIR)]
        command += ["-o", str(temporary), str(source)]
        result = _run(command, timeout=COMPILE_TIMEOUT)
        if result.returncode != 0:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(
                f"native build failed for {kernel}:\n{result.stderr.strip()}"
            )
        os.replace(temporary, final)
        final.chmod(0o755)
        _smoke(final)
        binaries[kernel] = {"path": str(final), "sha256": sha256(final)}
        commands.append(command)
    info.update(binaries=binaries, commands=commands,
                built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    temporary = BUILD_DIR / "manifest.json.tmp"
    temporary.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, BUILD_DIR / "manifest.json")
    return info


def ensure_built(force=False):
    """Build the kernels when missing or stale and return the manifest data."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = BUILD_DIR / "manifest.json"
    requested = _requested_compiler()
    explicit_info = _explicit_compiler_info(requested) if requested is not None else None
    handle = _lock()
    try:
        manifest = None
        if manifest_path.is_file() and not force:
            try:
                manifest = json.loads(manifest_path.read_text())
            except (OSError, ValueError):
                manifest = None
            if _manifest_matches(manifest, explicit_info):
                return manifest
        return _build_locked(manifest, explicit_info)
    finally:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def built_info():
    """Return the manifest of an existing build without compiling anything."""
    path = BUILD_DIR / "manifest.json"
    if not path.is_file():
        raise RuntimeError(
            f"native constructors are not built in {BUILD_DIR}; "
            "run: python competitions/santa-2026/src/algorithms/native/build.py"
        )
    manifest = json.loads(path.read_text())
    requested = _requested_compiler()
    explicit_info = _explicit_compiler_info(requested) if requested is not None else None
    if not _manifest_matches(manifest, explicit_info):
        raise RuntimeError(
            "native constructor sources, binaries or requested compiler changed; "
            "run the native build again"
        )
    return manifest


def binaries():
    """Map kernel name -> binary path, building the kernels if necessary."""
    manifest = ensure_built()
    return {kernel: Path(info["path"]) for kernel, info in manifest["binaries"].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild even when the manifest matches")
    parser.add_argument("--json", action="store_true", help="print the manifest instead of a summary")
    args = parser.parse_args()
    manifest = ensure_built(force=args.force)
    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return
    compiler = manifest["compiler"]
    print(f"build dir: {BUILD_DIR}")
    print(f"compiler: {compiler['family']} {compiler['version']} ({compiler['path']})")
    print(f"flags: {' '.join(manifest['flags'])}"
          + (" + compat header" if manifest.get("compat_include") else ""))
    for kernel, info in manifest["binaries"].items():
        print(f"{kernel}: sha256 {info['sha256']} ({info['path']})")
    for name, digest in manifest["sources"].items():
        print(f"source {name}: sha256 {digest}")


if __name__ == "__main__":
    main()
