from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt
from mpc import *


@dataclass
class Thermostat:
    power: int

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
    T0 = 15         # initial room temp (clesius)
    T_out = 10      # outside temp (celsius)

    h = 3           # room height
    w = 6           # room width
    l = 10          # room length

    dt = 60
    time = np.arange(0, 3601, dt)

    thermo = Thermostat(1000)
    myroom = VirtualRoom(T0, h*l*w, h*l + h*w, thermo)

    room_temp = []
    Q_thermo = []
    Q_conduc = []
    Q_rad = []

    rls_model = myroom.generate_rls(dt)

    for t in time:
        input_power = mpc_control(rls_model, 20, myroom.temp, 21, T_out)[0]
        thermo.power = input_power
        print(f'input at time {t}: {input_power} W')
        
        Qt, Qc, Qr, T = myroom.update_temp(dt, T_out, window_percent=0.3, show_data=True)
        room_temp.append(T)
        Q_thermo.append(Qt)
        Q_conduc.append(Qc)
        Q_rad.append(Qr)
    
    fig, ax = plt.subplots(2,1)

    ax[0].plot(time/60, room_temp, label='Room temperature (C)')
    
    ax[1].plot(time/60, np.array(Q_thermo)/dt, label='Heating (W)')
    ax[1].plot(time/60, np.array(Q_conduc)/dt, label='Heat loss conduction (W)')
    ax[1].plot(time/60, np.array(Q_rad)/dt, label='Heat loss radiation (W)')

    ax[0].set_ylim(0, 30)

    ax[0].set_xlabel('Time (min)')
    ax[1].set_xlabel('Time (min)')

    ax[0].legend()
    ax[1].legend()

    plt.show()


if __name__ == '__main__':
    main()
