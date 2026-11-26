"""Version dispatch for the Santa 2026 independent solvers.

``SOLVER_VERSION`` is the single release identifier consumed by the CLI and the
web review builder.  V10 Full is the current default; V9 remains available as
an explicit ``--version v9`` reproduction path so the previous published
pipeline can still be rerun from the same checkout.  V1-V8 live in the fixed
historical Git revisions documented by ``graph_solver.py``.
"""

from . import v9, v10

SOLVER_VERSION = "v10"
VERSIONS = ("v9", "v10")
DEFAULT_CONFIG = v10.DEFAULT_CONFIG
STAGES = v10.STAGES


def solve(row, config=None, version=None):
    """Solve one puzzle with the selected version and return the public triple."""
    version = SOLVER_VERSION if version is None else version
    if version == "v10":
        return v10.solve(row, config)
    if version == "v9":
        return v9.solve(row, config)
    raise ValueError(f"unknown solver version: {version!r}; available: {', '.join(VERSIONS)}")
