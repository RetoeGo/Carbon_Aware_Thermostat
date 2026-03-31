"""Small, dependency-free MPC + RLS helpers used by the integration.

Why this file exists
--------------------
Home Assistant custom integrations should avoid heavy solver dependencies such as
cvxpy when possible. This module keeps the control logic simple and readable:

* ``RLS`` learns a 1-step linear temperature model from history.
* ``mpc_control`` uses that learned model to look a few steps into the future
  and chooses the best *heating level* for the next control step.

The model we learn is:

    T_next = a * T_now + b * heating_level + c * outside_temp + d

where:
* ``T_now`` is the current indoor temperature
* ``heating_level`` is one of the discrete control levels (eco/preferred/aggressive)
* ``outside_temp`` is the current outside temperature
* ``T_next`` is the predicted indoor temperature at the next step
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .const import HEATING_LEVELS, HEATING_LEVEL_AGGRESSIVE


@dataclass
class RLS:
    """Recursive Least Squares model for 1-step room-temperature prediction.

    ``theta`` stores the learned coefficients ``[a, b, c, d]`` of:

        T_next = a * T_now + b * heating_level + c * outside_temp + d

    Notes:
    * ``P`` is the covariance / confidence matrix used by the RLS update rule.
    * ``lam`` is the forgetting factor. Values close to 1.0 keep more memory
      from older observations.
    * ``init_good`` is just a convenience flag the integration can inspect to
      know whether the model has seen enough non-zero data to be trusted more.
    """

    theta: np.ndarray
    P: np.ndarray
    lam: float
    init_good: bool = False

    def __init__(self, a: float, b: float, c: float, d: float, lam: float = 0.99, init_good: bool = False):
        # Start from a reasonable default model. The coordinator will refine these
        # values using historical thermostat data.
        self.theta = np.array([[a], [b], [c], [d]], dtype=float)

        # Identity is a simple, standard initial covariance choice.
        self.P = np.eye(4, dtype=float)

        # ``lam`` near 1 means "adapt slowly"; lower values adapt faster.
        self.lam = float(lam)
        self.init_good = bool(init_good)

    def update(
        self,
        T_k: float,
        u_k: float,
        T_outk: float,
        T_k1: float,
        show_data: bool = False,
    ) -> float | None:
        """Update the model using one observed transition.

        Inputs:
        * ``T_k``: current indoor temperature
        * ``u_k``: heating level applied during this interval
        * ``T_outk``: outside temperature during this interval
        * ``T_k1``: next indoor temperature actually observed

        Internally we build the feature vector:

            phi = [T_k, u_k, T_outk, 1]

        and fit it against ``T_k1``.
        """

        # Regressor / feature vector for this timestep.
        phi = np.array([[T_k], [u_k], [T_outk], [1.0]], dtype=float)

        # Observed "answer" we want the model to predict.
        Tk1 = np.array([[T_k1]], dtype=float)

        # Prediction error before updating the model.
        e_k = Tk1 - phi.T @ self.theta

        # Denominator of the RLS gain calculation.
        denom = float(self.lam + phi.T @ self.P @ phi)
        if denom == 0:
            # Defensive guard. In practice this should be extremely rare.
            return float(e_k[0, 0]) if show_data else None

        # Kalman-like gain term: tells us how much to trust this new sample.
        K = self.P @ phi / denom

        # Update the learned coefficients.
        self.theta = self.theta + K @ e_k

        # Update covariance / uncertainty for the next sample.
        self.P = (self.P - K @ phi.T @ self.P) / self.lam

        # Mark the model as "initialized" once all coefficients have seen
        # non-zero values at least once.
        if not self.init_good and not (0 in self.theta):
            self.init_good = True

        if show_data:
            return float(e_k[0, 0])
        return None


def mpc_control(
    RLS_model: RLS,
    N: int,
    T0: float,
    T_target,
    T_out,
    carbon_intensity,
) -> int:
    """Choose the best heating level for the next step.

    This is still MPC even though it does not use cvxpy:
    * we use a model (the learned RLS model)
    * we optimize over a horizon
    * we apply only the first action
    * then we re-run the optimization on the next control cycle

    Inputs
    ------
    * ``RLS_model``: learned temperature dynamics model
    * ``N``: horizon length in control steps
    * ``T0``: current indoor temperature
    * ``T_target``: target temperature sequence for the horizon
    * ``T_out``: outside temperature forecast for the horizon
    * ``carbon_intensity``: carbon forecast for the horizon

    Returns
    -------
    The chosen heating level for the *next* step only.
    """

    # Fixed weights requested for this integration.
    # ``weight_input`` penalizes stronger heating when carbon is high.
    # ``weight_tracking`` penalizes being far from the target temperature.
    weight_input = 6
    weight_tracking = 100

    # Never optimize past the data we actually have available.
    N = max(1, min(int(N), len(T_target), len(T_out), len(carbon_intensity)))
    targets = [float(x) for x in T_target[:N]]
    outside = [float(x) for x in T_out[:N]]
    carbon = [float(x) for x in carbon_intensity[:N]]

    # Extract learned model coefficients:
    #     T_next = a*T_now + b*u + c*T_out + d
    a, b, c, d = [float(v) for v in RLS_model.theta[:, 0]]

    # We quantize temperatures before caching dynamic-programming subproblems.
    # This keeps the state space small and makes repeated solves much faster.
    quant = 0.25

    @lru_cache(maxsize=None)
    def solve(step: int, temp_key: int) -> tuple[float, int]:
        """Return the best future cost and first action from this state.

        ``temp_key`` is a quantized temperature state:
            temp = temp_key * quant
        """

        temp = temp_key * quant

        # Base case: no steps left, so no future cost remains.
        if step >= N:
            return 0.0, HEATING_LEVELS[0]

        best_cost = float("inf")
        best_action = HEATING_LEVELS[0]

        target = targets[step]
        outside_temp = outside[step]
        carbon_int = carbon[step]

        # Try every allowed heating level at this timestep.
        for action in HEATING_LEVELS:
            # Predict the next indoor temperature if we choose this action.
            next_temp = a * temp + b * action + c * outside_temp + d

            # Comfort guard:
            # never allow the room to end up more than 3°C below target.
            if target - next_temp > 3.0:
                continue

            # Recurse into the next timestep.
            next_key = int(round(next_temp / quant))
            future_cost, _ = solve(step + 1, next_key)

            # Immediate cost for this action:
            # 1) stronger heating is more expensive when carbon is high
            # 2) temperature error from target is penalized
            stage_cost = (
                weight_input * action * carbon_int
                + weight_tracking * abs(next_temp - target)
            )
            total_cost = float(stage_cost + future_cost)

            if total_cost < best_cost:
                best_cost = total_cost
                best_action = action

        # If every action violated the comfort constraint, choose the strongest
        # heating level as a fallback so the room recovers quickly.
        if best_cost == float("inf"):
            return weight_tracking * 1000.0, HEATING_LEVEL_AGGRESSIVE

        return best_cost, best_action

    # Start the optimization from the current indoor temperature.
    start_key = int(round(float(T0) / quant))
    _, action = solve(0, start_key)
    return int(action)
