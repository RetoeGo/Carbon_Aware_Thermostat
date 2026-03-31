from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt
from .mpc import *
import csv
import time as tm
import pandas as pd


class Progress:
    def __init__(self, goal, step):
        self.state = 0
        self.goal = goal
        self.step = step
        print(f"Progress: {self.state}/{self.goal}")

    def update(self):
        self.state += self.step
        print('\033[1A', end='\x1b[2K')  # resets line
        if self.state >= self.goal:
            print("Done!")
        else:
            print(f"Progress: {self.state}/{self.goal}")


@dataclass
class Thermostat:
    power: float


class VirtualRoom:
    """Virtual Room Entity"""

    def __init__(self, T0, size, exposed_area, thermostat):
        self.temp = T0
        self.roomsize = size
        self.exposed_area = exposed_area
        self.thermostat = thermostat

        self.U_window = 1.5                     # Conductance            W / (m^2 * K)
        self.k_insulation = 0.04                # thermal conductivity   W / (m * K)
        self.k_brick = 0.75                     # thermal conductivity   W / (m * K)
        self.brick_thickness = 0.10             #                        m
        self.insul_thickness = 0.15             #                        m

    def conductance(self, window_percent=0.20):
        U_brick = self.k_brick / self.brick_thickness
        U_insul = self.k_insulation / self.insul_thickness

        U_wall = 1 / (1/U_brick + 1/U_insul + 1/U_brick)
        
        return window_percent * self.U_window + (1-window_percent) * U_wall

    def update_temp(self, dt, T_out, window_percent=0.2, show_data=False):
        assert 0 <= window_percent <= 1

        Q_added = self.thermostat.power * dt
        Q_loss_cond = self.conductance(window_percent) * self.exposed_area * (self.temp - T_out) * dt
        Q_loss_rad = 0
        Q_tot = Q_added - Q_loss_cond - Q_loss_rad

        c_p = 1006                      # specific heat air
        rho_air = 1.204                 # air density at 20 Celsius
        m = self.roomsize * rho_air     # total airmass in room

        self.temp += Q_tot / (c_p * m)

        if show_data:
            return Q_added, Q_loss_cond, Q_loss_rad, self.temp

    def generate_rls(self, dt):
        b = dt / (1006 * self.roomsize * 1.204)
        U = self.conductance()

        c = b * U * self.exposed_area
        a = 1 - c
        d = 0

        return RLS(a, b, c, d, lam=0.9, init_good=True)


def load_external_data(csv_path, case):
    df = pd.read_csv(csv_path)

    required_columns = [
        "validfrom",
        "temperature_c_delft",
        "carbon_intensity_gco2_per_kwh",
    ]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s) in {csv_path}: {missing}")

    # Keep only the columns the simulation actually uses.
    # This avoids pandas trying to interpolate string/object columns during resampling.
    df = df[required_columns].copy()

    df["validfrom"] = pd.to_datetime(df["validfrom"], utc=True)
    df["temperature_c_delft"] = pd.to_numeric(df["temperature_c_delft"], errors="coerce")
    df["carbon_intensity_gco2_per_kwh"] = pd.to_numeric(
        df["carbon_intensity_gco2_per_kwh"], errors="coerce"
    )

    df = df.sort_values("validfrom").drop_duplicates(subset=["validfrom"]).reset_index(drop=True)

    diffs = df["validfrom"].diff().dropna()
    invalid_diffs = diffs[diffs != pd.Timedelta(minutes=15)]
    if not invalid_diffs.empty:
        raise ValueError(
            "CSV timestamps are not strictly 15 minutes apart for every row. "
            "Please fix gaps/duplicates first."
        )

    if case == "bang":
        # Create one data point per minute only for bang control.
        # Interpolate only the numeric series we need.
        df = (
            df.set_index("validfrom")
            .resample("1min")
            .interpolate(method="time")
            .reset_index()
        )
    elif case != "MPC":
        raise ValueError(f"Unsupported case: {case}")

    timestamps = df["validfrom"].to_numpy()
    T_out = df["temperature_c_delft"].to_numpy(dtype=float)

    # Scale down for MPC to match the rough magnitude used in the original code.
    carbon_intensity = df["carbon_intensity_gco2_per_kwh"].to_numpy(dtype=float) / 1000.0

    return timestamps, T_out, carbon_intensity


def main():
    # case = "bang"
    case = "MPC"

    start_time = tm.time()

    if case == "bang":
        dt = 60          # 1 minute
        N = 18           # not used by bang, kept for compatibility
        output_csv = "room_data_bang.csv"
    elif case == "MPC":
        dt = 900         # 15 minutes
        N = 18           # 18 x 15 min = 4.5 hour horizon
        output_csv = "room_data_mpc.csv"
    else:
        raise ValueError(f"Unsupported case: {case}")

    data_file = "data/test.csv"
    timestamps, T_out, carbon_intensity = load_external_data(data_file, case)

    days_to_simulate = 5      # Change this to control how many days are simulated/output/plotted
    start_day = 0             # 0 = start from the first day in the dataset, 1 = start from day 2, etc.

    steps_per_day = int((24 * 3600) / dt)
    start_idx = start_day * steps_per_day
    end_idx = start_idx + days_to_simulate * steps_per_day

    if start_idx >= len(timestamps):
        raise ValueError(
            f"start_day={start_day} is outside the available dataset. "
            f"The dataset only contains about {len(timestamps) / steps_per_day:.2f} days for case '{case}'."
        )

    min_len = min(len(T_out), len(carbon_intensity), len(timestamps), end_idx)
    T_out = T_out[start_idx:min_len]
    carbon_intensity = carbon_intensity[start_idx:min_len]
    timestamps = timestamps[start_idx:min_len]

    sim_len = len(timestamps)
    time = np.arange(0, sim_len * dt, dt)
    n = 3600 // dt      # timesteps per hour

    T0 = 15             # initial room temp (celsius)

##### Preferred warmer temp #####
    # base_target = np.array(
    #     n * 6 * [15]
    #     + n * 3 * [21]
    #     + n * 5 * [18]
    #     + n * 8 * [21]
    #     + n * 2 * [15]
    # )
##### Preferred colder temp #####
    base_target = np.array(
        n * 6 * [15]
        + n * 3 * [19]
        + n * 5 * [16]
        + n * 8 * [19]
        + n * 2 * [15]
    )

    repeats = int(np.ceil((len(time) + N + 1) / len(base_target)))
    T_target = np.tile(base_target, repeats)[:len(time) + N + 1]

    # Extend real series for MPC horizon only.
    if case == "MPC":
        if len(T_out) < N:
            raise ValueError(
                f"Not enough data points for MPC horizon: need at least {N}, got {len(T_out)}."
            )
        T_out = np.concatenate((T_out, T_out[:N]))
        carbon_intensity = np.concatenate((carbon_intensity, carbon_intensity[:N]))

    h = 3           # room height
    w = 6           # room width
    l = 10          # room length

    power_options = 2
    max_power = 1500

    thermo = Thermostat(0)
    myroom = VirtualRoom(T0, h * l * w, h * l + h * w, thermo)

    room_temp = []
    Q_thermo = []
    Q_conduc = []
    Q_rad = []
    RLS_errors = []
    csv_rows = []

    # rls_model = myroom.generate_rls(dt)
    rls_model = RLS(0, 0, 0, 0, lam=0.9)

    sim_steps = len(time)
    progress = Progress(sim_steps, 1)

    for i, t in enumerate(time):
        T_k = myroom.temp

        if case == "MPC":
            if not rls_model.init_good:
                input_power = bang_bang_control(T_k, T_target[i], max_power)
            else:
                input_power = mpc_control(
                    rls_model,
                    N,
                    T_k,
                    T_target[i:i + N],
                    T_out[i:i + N],
                    carbon_intensity[i:i + N],
                    max_power,
                    power_options
                )
        elif case == "bang":
            input_power = bang_bang_control(T_k, T_target[i], max_power)

        thermo.power = input_power
        progress.update()

        Qt, Qc, Qr, T_k1 = myroom.update_temp(dt, T_out[i], window_percent=0.2, show_data=True)
        room_temp.append(T_k1)
        Q_thermo.append(Qt)
        Q_conduc.append(Qc)
        Q_rad.append(Qr)

        csv_rows.append([
            str(timestamps[i]),
            t / 3600,
            T_target[i],
            T_out[i],
            carbon_intensity[i] * 1000,   # back to gCO2/kWh in output CSV
            input_power,
            T_k1,
            Qt,
            Qc,
            dt
        ])

        e_k = rls_model.update(T_k, input_power, T_out[i], T_k1, show_data=True)
        RLS_errors.append(e_k)

    end_time = tm.time()
    print(f'Total time: {round(end_time - start_time, 3)} s')

    output_csv = f"{output_csv.rsplit('.', 1)[0]}_{days_to_simulate}d_from_day_{start_day}.csv"

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "time_h",
            "preferred_room_temperature_C",
            "outside_temperature_C",
            "carbon_intensity_gco2_per_kj",
            "heating_wattage_W",
            "room_temprature",
            "Q_thermo",
            "Q_conduc",
            "dt"
        ])
        writer.writerows(csv_rows)

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))

    ax[0].plot(time / 3600, room_temp, label='Room temperature (C)')
    ax[0].plot(time / 3600, T_target[:len(time)], linestyle='dotted', color='red', label='target temp (C)')
    ax[0].plot(time / 3600, T_out[:len(time)], label='Outside temperature (C)')

    ax[1].plot(time / 3600, np.array(Q_thermo) / dt, label='Heating (W)')
    ax[1].plot(time / 3600, np.array(Q_conduc) / dt, label='Heat loss conduction (W)')
    ax[1].plot(time / 3600, np.array(Q_rad) / dt, label='Heat loss radiation (W)')
    ax[1].plot(time / 3600, carbon_intensity[:len(time)] * 1000, label='carbon intensity (gCO2/kWh)')

    ax[0].set_ylim(0, 30)

    ax[0].set_xlabel('Time (hours)')
    ax[1].set_xlabel('Time (hours)')

    ax[0].legend()
    ax[1].legend()

    plt.show()


if __name__ == '__main__':
    main()
