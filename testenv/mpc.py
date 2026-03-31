import cvxpy as cp
import numpy as np

class RLS:
    def __init__(self, a, b, c, d, lam=0.99, init_good=False):
        self.theta = np.array([[a], [b], [c], [d]]) #init matrix
        self.P = np.eye(4) # I matrix
        self.lam = lam # forgetting factor
        self.init_good = init_good
    
    def update(self, T_k, u_k, T_outk, T_k1, show_data=False):
        phi = np.array([[T_k], [u_k], [T_outk], [1]])
        Tk1 = np.array([[T_k1]])
        #error
        e_k = Tk1 - phi.T @ self.theta
        # gain matrix
        K = self.P @ phi / (self.lam + phi.T @ self.P @ phi)
        #updates
        self.theta = self.theta + K @ e_k
        self.P = (self.P - K @ phi.T @self.P) / self.lam
        if not self.init_good and not(0 in self.theta):
            self.init_good = True

        if show_data:
            return e_k[0]

def bang_bang_control(T_k, T_target, max_power):
    if T_target - T_k > 0:
        return max_power
    return 0

def mpc_control(RLS_model, N, T0, T_target, T_out, carbon_intensity, max_power, power_options):
    weight_input = 6
    weight_tracking = 100
    
    cost = 0.0
    constraints = []

    # cp.Variable((dim_1, dim_2))
    T = cp.Variable((1, N + 1)) 
    u = cp.Variable((1, N), integer=True)

    a, b, c, d = RLS_model.theta[:,0]

    heat_stage = max_power // power_options

    # to add constraint:    constraints += [expression]
    # to add cost:          cost += value

    for k in range(N):
        T_outk = T_out[k]
        C_int = carbon_intensity[k]
        T_targetk = T_target[k]
        T_k = T[:,k]
        T_k1 = T[:,k+1]
        u_k = u[:,k]

        # model dynamics
        constraints += [T_k1 == a*T_k + b*heat_stage*u_k + c*T_outk + d]
        
        # temp cant be more then 3 degrees below target
        constraints += [T_targetk - T_k1 <= 3]

        cost += weight_input * u_k * heat_stage * C_int
        cost += weight_tracking * cp.abs(T_k1 - T_targetk)

    # initial temperature    
    constraints += [T[:,0] == T0]

    # input constraints
    constraints += [u >= 0]
    constraints += [u <= power_options]


    problem = cp.Problem(cp.Minimize(cost), constraints)
    problem.solve(solver=cp.GLPK_MI, **{'tm_lim': 1000})

    # return next input
    return u[0, 0].value * heat_stage if not (u[0, 0].value is None) else 0
