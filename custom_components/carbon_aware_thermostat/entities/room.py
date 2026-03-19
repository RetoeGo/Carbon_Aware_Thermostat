from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt
from mpc import *
import csv
import time as tm


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

        self.window_conductivity = 1.5           # W / (m^2 * K)
        self.insulation_conductivity = 0.04      # W / (m * K)
        self.wall_thickness = 0.05               # m

    def thermal_conductivity(self, window_percent=0.3):        
        return ((1-window_percent)*self.insulation_conductivity/self.wall_thickness + window_percent*self.window_conductivity)
    
    def update_temp(self, dt, T_out, window_percent=0.3, show_data=False):
        assert 0 <= window_percent <= 1
        
        Q_added = self.thermostat.power * dt
        Q_loss_cond = self.thermal_conductivity(window_percent) * self.exposed_area * (self.temp - T_out) * dt
        Q_loss_rad = 0
        Q_tot = Q_added - Q_loss_cond - Q_loss_rad

        c = 1007                        # specific heat air
        m = self.roomsize * 1.225       # total airmass in room
        
        self.temp += (Q_tot) / (c * m)

        if show_data:
            return Q_added, Q_loss_cond, Q_loss_rad, self.temp
        
    def generate_rls(self, dt):
        b = dt / (1007 * self.roomsize * 1.225)
        kl = self.thermal_conductivity()

        c = b * kl * self.exposed_area
        a = 1 - c
        d = 0

        return RLS(a,b,c,d)


def main():
    start_time = tm.time()
    
    dt = 600
    time = np.arange(0, 60*60*24+1, dt)
    n = 3600//dt        # timesteps per hour
    N = 18
    
    T0 = 15         # initial room temp (clesius)
    T_out = 5 + 10 * np.sin(np.pi / (60*60*24) * time)
    T_out = np.concatenate((T_out, T_out[:N]))

    T_target = np.array(n*6*[15] + n*3*[21] + n*5*[18] + n*8*[21] + n*2*[15])
    T_target = np.concatenate((T_target, T_target[:N+1]))
    
    carbon_intensity = np.array(n*7*[1] + n*2*[0.5] + n*8*[0.1] + n*2*[0.5] + (n*5+N+1)*[1])

    h = 3           # room height
    w = 6           # room width
    l = 10          # room length

    heat_stages = 500

    thermo = Thermostat(0)
    myroom = VirtualRoom(T0, h*l*w, h*l + h*w, thermo)

    room_temp = []
    Q_thermo = []
    Q_conduc = []
    Q_rad = []
    RLS_errors = []
    csv_rows = []

    rls_model = myroom.generate_rls(dt)

    for i, t in enumerate(time):
        T_k = myroom.temp
        input_power = mpc_control(rls_model, N, T_k, T_target[i:i+N], T_out[i:i+N], carbon_intensity[i:i+N], heat_stages)
        #input_power = bang_bang(myroom.temp, 21, T_out[i:i+N], carbon_intensity[i:i+N])

        thermo.power = input_power
        print(f'input at time {t}: {input_power} W')
        
        Qt, Qc, Qr, T_k1 = myroom.update_temp(dt, T_out[i], window_percent=0.3, show_data=True)
        room_temp.append(T_k1)
        Q_thermo.append(Qt)
        Q_conduc.append(Qc)
        Q_rad.append(Qr)

        csv_rows.append([
            t/3600,
            T_target[i],
            T_out[i],
            carbon_intensity[i],
            input_power,
            T_k1,
            Qt,
            Qc,
            Qr
        ])

        e_k = rls_model.update(T_k, input_power, T_out[i], T_k1, show_data=True)
        RLS_errors.append(e_k)
    
    end_time = tm.time()
    print(f'Total time: {round(end_time - start_time, 3)} s')

    with open("room_data.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_h",
            "preferred_room_temperature_C",
            "outside_temperature_C",
            "co2_consumption_electricity_net",
            "heating_wattage_W",
            "room_temprature",
            "Q_thermo",
            "Q_conduc",
            "Q_rad"
        ])
        writer.writerows(csv_rows)


    fig, ax = plt.subplots(1,3, figsize=(12,4))

    ax[0].plot(time/3600, room_temp, label='Room temperature (C)')
    ax[0].plot(time/3600, T_target[:-N], linestyle='dotted', color='red', label='target temp (C)')
    ax[0].plot(time/3600, T_out[:-N], label='Outside temperature (C)')
    ax[0].plot(time/3600, 25*carbon_intensity[:-N], label='carbon intensity (*25)')
    
    ax[1].plot(time/3600, np.array(Q_thermo)/dt, label='Heating (W)')
    ax[1].plot(time/3600, np.array(Q_conduc)/dt, label='Heat loss conduction (W)')
    ax[1].plot(time/3600, np.array(Q_rad)/dt, label='Heat loss radiation (W)')
    ax[1].plot(time/3600, 1000*carbon_intensity[:-N], label='carbon intensity (*1000)')

    ax[2].plot(time/3600, RLS_errors)

    ax[0].set_ylim(0, 30)

    ax[0].set_xlabel('Time (hours)')
    ax[1].set_xlabel('Time (hours)')
    ax[2].set_xlabel('Time (hours)')

    ax[0].legend()
    # ax[1].legend()

    plt.show()


if __name__ == '__main__':
    main()
