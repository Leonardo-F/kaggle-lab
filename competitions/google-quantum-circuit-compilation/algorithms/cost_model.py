"""Standalone original calculator for published competition resource formulas.

This is *not* a circuit generator and does not substitute for the official metric.
"""
from __future__ import annotations

import math


def invsqrt_cost(qubits: int, toffoli: int, t_gates: int) -> float:
    if qubits <= 0 or toffoli < 0 or t_gates < 0:
        raise ValueError("Invalid nonnegative gate counts / positive qubit count required")
    return qubits * (toffoli + t_gates / 4)


def dqi_repetition(epsilon_upper: float) -> float:
    if not 0 <= epsilon_upper < 1 / 16:
        raise ValueError("epsilon_upper must be in [0, 1/16)")
    return math.log(2) / (-math.log(0.5 + 2 * math.sqrt(epsilon_upper)))


def dqi_cost(qubits: int, toffoli: int, epsilon_upper: float) -> float:
    if qubits <= 0 or toffoli < 0:
        raise ValueError("Invalid qubit or Toffoli count")
    return dqi_repetition(epsilon_upper) * qubits**2 * toffoli


def dfthcsos_lambda(e_gap: float, lam: float) -> float:
    if e_gap < 0 or lam <= 0 or 2 * lam < e_gap:
        raise ValueError("Invalid spectral gap or lambda")
    return math.sqrt(e_gap * (2 * lam - e_gap))


def dfthcsos_cost(e_gap: float, lam: float, toffoli: int, qubits: int) -> float:
    if toffoli < 0 or qubits <= 0:
        raise ValueError("Invalid qubit or Toffoli count")
    return dfthcsos_lambda(e_gap, lam) * toffoli * qubits


def overall_score(reference: dict[str, float], candidate: dict[str, float]) -> float:
    required = {"invsqrt", "dqi", "dfthcsos"}
    if set(reference) != required or set(candidate) != required:
        raise ValueError(f"Expected exactly these task names: {sorted(required)}")
    if any(not math.isfinite(reference[k]) or not math.isfinite(candidate[k]) or reference[k] <= 0 or candidate[k] <= 0 for k in required):
        raise ValueError("All costs must be positive and finite")
    return math.exp(sum(math.log(reference[k] / candidate[k]) for k in required) / 3)
