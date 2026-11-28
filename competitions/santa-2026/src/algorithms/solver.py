"""Version dispatch for the Santa 2026 independent solvers."""

from . import v9, v10, v11

SOLVER_VERSION = "v11"
VERSIONS = ("v9", "v10", "v11")
DEFAULT_CONFIG = v10.DEFAULT_CONFIG
STAGES = v10.STAGES


def solve(row, config=None, version=None):
    """Solve one puzzle with the selected version and return the public triple."""
    version = SOLVER_VERSION if version is None else version
    if version == "v11":
        return v11.solve(row, config)
    if version == "v10":
        return v10.solve(row, config)
    if version == "v9":
        return v9.solve(row, config)
    raise ValueError(f"unknown solver version: {version!r}; available: {', '.join(VERSIONS)}")
