from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

try:
    import cvxpy as cp
except Exception:  # pragma: no cover - optional dependency
    cp = None


@dataclass
class MPCWeights:
    input_weight: float = 0.5
    tracking_weight: float = 5.0
    smoothing_weight: float = 0.0001


class RLS:
    def __init__(self, a: float, b: float, c: float, d: float, lam: float = 0.99):
        self.theta = np.array([[a], [b], [c], [d]], dtype=float)
        self.P = 100.0 * np.eye(4)
        self.lam = float(lam)

    def update(self, T_k: float, u_k: float, T_outk: float, T_k1: float) -> None:
        phi = np.array([[T_k], [u_k], [T_outk], [1.0]], dtype=float)
        Tk1 = np.array([[T_k1]], dtype=float)
        e_k = Tk1 - phi.T @ self.theta
        denom = self.lam + phi.T @ self.P @ phi
        K = self.P @ phi / denom
        self.theta = self.theta + K @ e_k
        self.P = (self.P - K @ phi.T @ self.P) / self.lam


def _clip_horizon(arr: Iterable[float], N: int, fill: float) -> np.ndarray:
    values = list(float(x) for x in arr)
    if not values:
        values = [fill]
    if len(values) < N:
        values.extend([values[-1]] * (N - len(values)))
    return np.array(values[:N], dtype=float)


def _heuristic_mpc_control(
    rls_model: RLS,
    N: int,
    T0: float,
    T_target: float,
    T_out: Iterable[float],
    carbon_intensity: Iterable[float],
    max_power: float,
) -> float:
    """Fallback when cvxpy isn't available.

    Tries a small discrete set of powers and picks the one with the best one-step score.
    """
    a, b, c, d = rls_model.theta[:, 0]
    outside = _clip_horizon(T_out, N, fill=T0)
    carbon = _clip_horizon(carbon_intensity, N, fill=carbon_intensity[0] if list(carbon_intensity) else 300.0)
    candidates = np.linspace(0.0, max_power, 7)
    best_u = 0.0
    best_cost = float("inf")
    for u in candidates:
        temp = float(T0)
        cost = 0.0
        for k in range(N):
            temp = float(a * temp + b * u + c * outside[k] + d)
            tracking = (temp - T_target) ** 2
            cost += 0.5 * u * max(carbon[k], 0.0) / 1000.0
            cost += 5.0 * tracking
            cost += 0.0001 * (u ** 2)
        if cost < best_cost:
            best_cost = cost
            best_u = float(u)
    return best_u


def mpc_control(
    rls_model: RLS,
    N: int,
    T0: float,
    T_target: float,
    T_out: Iterable[float],
    carbon_intensity: Iterable[float],
    max_power: float = 1500.0,
    weights: MPCWeights | None = None,
) -> float:
    weights = weights or MPCWeights()
    outside = _clip_horizon(T_out, N, fill=T0)
    carbon = _clip_horizon(carbon_intensity, N, fill=300.0)

    if cp is None:
        return _heuristic_mpc_control(rls_model, N, T0, T_target, outside, carbon, max_power)

    T = cp.Variable((1, N + 1))
    u = cp.Variable((1, N))
    a, b, c, d = rls_model.theta[:, 0]
    cost = 0.0
    constraints = [T[:, 0] == T0, u >= 0, u <= max_power]

    for k in range(N):
        T_outk = outside[k]
        C_int = carbon[k]
        T_k = T[:, k]
        T_k1 = T[:, k + 1]
        u_k = u[:, k]
        constraints += [T_k1 == a * T_k + b * u_k + c * T_outk + d]
        cost += weights.input_weight * u_k * (C_int / 1000.0)
        cost += weights.tracking_weight * cp.square(T_k1 - T_target)
        cost += weights.smoothing_weight * cp.square(u_k)

    problem = cp.Problem(cp.Minimize(cost), constraints)
    try:
        problem.solve(solver=cp.CLARABEL, verbose=False)
    except Exception:
        try:
            problem.solve(verbose=False)
        except Exception:
            return _heuristic_mpc_control(rls_model, N, T0, T_target, outside, carbon, max_power)

    value = u[0, 0].value
    if value is None:
        return _heuristic_mpc_control(rls_model, N, T0, T_target, outside, carbon, max_power)
    return float(np.clip(value, 0.0, max_power))
