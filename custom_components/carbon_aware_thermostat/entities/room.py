from __future__ import annotations

from dataclasses import dataclass

from .mpc import RLS


@dataclass
class Thermostat:
    power: float


class VirtualRoom:
    """Simple single-zone room model used for demo/simulation mode."""

    def __init__(self, T0: float, size: float, exposed_area: float, thermostat: Thermostat):
        self.temp = float(T0)
        self.roomsize = float(size)
        self.exposed_area = float(exposed_area)
        self.thermostat = thermostat
        self.window_conductivity = 1.5
        self.insulation_conductivity = 0.04
        self.wall_thickness = 0.05

    def thermal_conductivity(self, window_percent: float = 0.3) -> float:
        return (
            (1 - window_percent) * self.insulation_conductivity / self.wall_thickness
            + window_percent * self.window_conductivity
        )

    def update_temp(
        self,
        dt_seconds: float,
        T_out: float,
        window_percent: float = 0.3,
        show_data: bool = False,
    ):
        assert 0 <= window_percent <= 1
        Q_added = self.thermostat.power * dt_seconds
        Q_loss_cond = (
            self.thermal_conductivity(window_percent)
            * self.exposed_area
            * (self.temp - T_out)
            * dt_seconds
        )
        Q_loss_rad = 0.0
        Q_tot = Q_added - Q_loss_cond - Q_loss_rad
        c = 1007.0
        m = self.roomsize * 1.225
        self.temp += Q_tot / (c * m)
        if show_data:
            return Q_added, Q_loss_cond, Q_loss_rad, self.temp
        return self.temp

    def generate_rls(self, dt_seconds: float, window_percent: float = 0.3) -> RLS:
        b = dt_seconds / (1007.0 * self.roomsize * 1.225)
        kl = self.thermal_conductivity(window_percent)
        c = b * kl * self.exposed_area
        a = 1.0 - c
        d = 0.0
        return RLS(a, b, c, d)
