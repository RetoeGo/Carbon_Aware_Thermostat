from dataclasses import dataclass
import numpy as np
import matplotlib.pyplot as plt


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
    
    def update_temp(self, dt, T_out, show_data=False):
        Q_added = self.thermostat.power * dt
        Q_loss_cond = 0.04 * self.exposed_area * (self.temp - T_out) / (0.05) * dt
        Q_loss_rad = 0
        Q_tot = Q_added - Q_loss_cond - Q_loss_rad

        c = 1007                        # specific heat air
        m = self.roomsize * 1.225       # total airmass in room
        
        self.temp += (Q_tot) / (c * m)

        if show_data:
            return Q_added, Q_loss_cond, Q_loss_rad, self.temp


def main():
    T0 = 15         # initial room temp (clesius)
    T_out = 10      # outside temp (celsius)

    h = 3           # room height
    w = 6           # room width
    l = 10          # room length

    thermo = Thermostat(300)
    myroom = VirtualRoom(T0, h*l*w, h*w, thermo)

    room_temp = []
    Q_thermo = []
    Q_conduc = []
    Q_rad = []

    dt = 60
    time = np.arange(0, 3601, dt)

    for t in time:
        Qt, Qc, Qr, T = myroom.update_temp(dt, T_out, show_data=True)
        room_temp.append(T)
        Q_thermo.append(Qt)
        Q_conduc.append(Qc)
        Q_rad.append(Qr)
    
    fig, ax = plt.subplots(2,1)

    ax[0].plot(time, room_temp, label='Room temperature (C)')
    
    ax[1].plot(time, Q_thermo, label='Heating (J)')
    ax[1].plot(time, Q_conduc, label='Heat loss conduction (J)')
    ax[1].plot(time, Q_rad, label='Heat loss radiation (J)')

    ax[0].legend()
    ax[1].legend()

    plt.show()


if __name__ == '__main__':
    main()
