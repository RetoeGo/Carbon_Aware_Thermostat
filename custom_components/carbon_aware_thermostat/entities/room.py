from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt
from mpc import *


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
    dt = 600
    time = np.arange(0, 60*60*24+1, dt)
    N = 30
    
    T0 = 15         # initial room temp (clesius)
    T_out = 5 + 10 * np.sin(np.pi / (60*60*24) * time)
    T_out = np.concatenate((T_out, T_out[:N]))

    # carbon_intensity = np.ones(len(time)) * 1
    # sun = len(time)//3
    # carbon_intensity[sun:sun*2] -= 7 * (np.sin(np.pi / (60*60*24) * time[sun:sun*2]) - np.sin(np.pi / (60*60*24) * time[sun]))
    # carbon_intensity = np.concatenate((carbon_intensity, carbon_intensity[:N]))
    
    carbon_intensity = np.array(42*[1] + 12*[0.5] + 48*[0.1] + 12*[0.5] + (30+N+1)*[1])

    h = 3           # room height
    w = 6           # room width
    l = 10          # room length

    thermo = Thermostat(1000)
    myroom = VirtualRoom(T0, h*l*w, h*l + h*w, thermo)

    room_temp = []
    Q_thermo = []
    Q_conduc = []
    Q_rad = []

    rls_model = myroom.generate_rls(dt)

    for i, t in enumerate(time):
        input_power = mpc_control(rls_model, N, myroom.temp, 21, T_out[i:i+N], carbon_intensity[i:i+N])
        thermo.power = input_power
        print(f'input at time {t}: {input_power} W')
        
        Qt, Qc, Qr, T = myroom.update_temp(dt, T_out[i], window_percent=0.3, show_data=True)
        room_temp.append(T)
        Q_thermo.append(Qt)
        Q_conduc.append(Qc)
        Q_rad.append(Qr)
    
    fig, ax = plt.subplots(2,1)

    ax[0].plot(time/3600, room_temp, label='Room temperature (C)')
    ax[0].axhline(21, linestyle='dotted', color='red', label='target temp (C)')
    ax[0].plot(time/3600, T_out[:-N], label='Outside temperature (C)')
    
    ax[1].plot(time/3600, np.array(Q_thermo)/dt, label='Heating (W)')
    ax[1].plot(time/3600, np.array(Q_conduc)/dt, label='Heat loss conduction (W)')
    ax[1].plot(time/3600, np.array(Q_rad)/dt, label='Heat loss radiation (W)')
    ax[1].plot(time/3600, 1000*carbon_intensity[:-N], label='carbon intensity (*1000)')

    ax[0].set_ylim(0, 30)

    ax[1].set_xlabel('Time (hours)')

    ax[0].legend()
    ax[1].legend()

    plt.show()


if __name__ == '__main__':
    main()
