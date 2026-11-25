"""Build the two frozen C++17 constructor kernels used by the V9 solver.

The ``.cpp`` sources are byte-identical to the frozen V9 research handoff and
are compiled before a solve starts into ``competitions/santa-2026/experiments/
native-build/`` (git-ignored).  The bundled research archive contains prebuilt
ELF binaries; those are never used as a release dependency.

The build records the compiler identity, flags, source hashes and binary
hashes in ``manifest.json``.  The manifest is what the checkpoint fingerprint
binds, so a resumed run can only reuse the exact same native pipeline.  Bump
``MANIFEST_SCHEMA`` whenever this module's build contract changes.

GCC/libstdc++ on Linux is the reference toolchain (the frozen full run used
``g++ -O3 -std=c++17``).  A local compiler without libstdc++, such as Apple
Clang, is supported through the small ``compat/bits/stdc++.h`` forwarding
header; ``native/build.py`` adds it only when a compiler probe shows the real
aggregate header is missing.  Compiler-dependent candidate ordering was checked
against the frozen per-puzzle records; see ``docs/progress.md`` for the exact
platforms and results.
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
KERNELS = ("constructor_wide", "constructor_mitm")
FLAGS = ("-O3", "-std=c++17")
MANIFEST_SCHEMA = 1
COMPILE_TIMEOUT = 180
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


def source_files():
    """Stable relative-path -> absolute-path map of build inputs."""
    files = {Path("build.py"): Path(__file__).resolve()}
    for kernel in KERNELS:
        files[Path(kernel + ".cpp")] = NATIVE_DIR / (kernel + ".cpp")
    for shim in sorted(COMPAT_DIR.rglob("*")):
        if shim.is_file():
            files[shim.relative_to(NATIVE_DIR)] = shim
    return {path.as_posix(): absolute for path, absolute in sorted(files.items())}


def _run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


def _compiler_version(compiler):
    result = _run([compiler, "--version"])
    if result.returncode != 0:
        raise RuntimeError(f"cannot query compiler {compiler}: {result.stderr.strip()}")
    first = (result.stdout.splitlines() or [""])[0]
    lower = first.lower()
    if "gcc" in lower or "g++" in lower or "free software foundation" in lower:
        family = "gcc"
    elif "clang" in lower:
        family = "clang"
    else:
        family = "unknown"
    return {"path": str(compiler), "version": first, "family": family}


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


def choose_compiler(explicit=None):
    """Return ``(compiler_path, version_info, compat_include)``.

    ``SANTA_CXX``/``explicit`` wins, then GCC names before the generic ``g++``
    and ``c++`` aliases (which are Apple Clang on macOS).  The first candidate
    that compiles the probe is used; libstdc++'s aggregate header is preferred
    and the compatibility shim is a documented fallback.
    """
    requested = explicit or os.environ.get("SANTA_CXX")
    candidates = []
    if requested:
        candidates.append(requested)
    else:
        candidates.extend(COMPILER_CANDIDATES)
    failures = []
    for candidate in candidates:
        resolved = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if resolved is None:
            failures.append(f"{candidate}: not found")
            continue
        try:
            version = _compiler_version(resolved)
        except (OSError, RuntimeError) as exc:
            failures.append(f"{candidate}: {exc}")
            continue
        ok, stderr = _probe(resolved, include_compat=False)
        if ok:
            return version, False
        ok, shim_stderr = _probe(resolved, include_compat=True)
        if ok:
            return version, True
        failures.append(f"{candidate}: probe failed: {(stderr or shim_stderr).strip().splitlines()[:1]}")
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


def _manifest_matches(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        return False
    expected = _expected_manifest()
    if manifest.get("flags") != expected["flags"]:
        return False
    if manifest.get("sources") != expected["sources"]:
        return False
    compiler = manifest.get("compiler") or {}
    if not compiler.get("path") or not compiler.get("version"):
        return False
    if not Path(compiler["path"]).exists():
        return False
    try:
        if _compiler_version(compiler["path"])["version"] != compiler["version"]:
            return False
    except (OSError, RuntimeError):
        return False
    for kernel in KERNELS:
        info = (manifest.get("binaries") or {}).get(kernel) or {}
        binary = Path(info.get("path", ""))
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


def _build_locked(manifest):
    sources = source_files()
    info = dict(_expected_manifest())
    if manifest and manifest.get("compiler") and Path(manifest["compiler"].get("path", "")).exists():
        try:
            compiler = {"path": manifest["compiler"]["path"],
                        "version": manifest["compiler"]["version"],
                        "family": manifest["compiler"]["family"]}
            version = _compiler_version(compiler["path"])
            if version["version"] != compiler["version"]:
                raise RuntimeError("compiler version changed")
            ok, _ = _probe(compiler["path"], include_compat=bool(manifest.get("compat_include")))
            if not ok:
                raise RuntimeError("compiler probe failed")
            compat = bool(manifest.get("compat_include"))
        except (OSError, RuntimeError):
            compiler, compat = choose_compiler()
    else:
        compiler, compat = choose_compiler()
    info.update(compiler=compiler, compat_include=compat)
    binaries = {}
    commands = []
    for kernel in KERNELS:
        source = sources[kernel + ".cpp"]
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
    info.update(binaries=binaries, commands=commands, built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    temporary = BUILD_DIR / "manifest.json.tmp"
    temporary.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, BUILD_DIR / "manifest.json")
    return info


def ensure_built(force=False):
    """Build the kernels when missing or stale and return the manifest data."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = BUILD_DIR / "manifest.json"
    handle = _lock()
    try:
        manifest = None
        if manifest_path.is_file() and not force:
            try:
                manifest = json.loads(manifest_path.read_text())
            except (OSError, ValueError):
                manifest = None
            if _manifest_matches(manifest):
                return manifest
        return _build_locked(manifest)
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
    if not _manifest_matches(manifest):
        raise RuntimeError(
            "native constructor sources or binaries are stale; run the native build again"
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
