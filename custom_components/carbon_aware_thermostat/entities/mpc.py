import cvxpy as cp
import numpy as np

class RLS:
    def __init__(self, a, b, c, d, lam=0.99):
        self.theta = np.array([[a], [b], [c], [d]]) #init matrix
        self.P = 100 * np.eye(4) # I matrix with 100 on each (i,i)
        self.lam = lam # forgetting factor
    
    def update(self, T_k, u_k, T_outk, T_k1):
        phi = np.array([[T_k], [u_k], [T_outk], [1]])
        Tk1 = np.array([[T_k1]])
        #error
        e_k = Tk1 - phi.T @ self.theta
        # gain matrix
        K = self.P @ phi / (self.lam + phi.T @ self.P @ phi)
        #updates
        self.theta = self.theta + K @ e_k
        self.P = (self.P - K @ phi.T @self.P) / self.lam

def mpc_control(RLS_model, N, T0, T_target, T_out, carbon_intensity):
    weight_input = 0.5
    weight_tracking = 5
    weight_smoothing = 0.0001
    
    cost = 0.0
    constraints = []

    # cp.Variable((dim_1, dim_2))
    T = cp.Variable((1, N + 1)) 
    u = cp.Variable((1, N))

    a, b, c, d = RLS_model.theta[:,0]

    # to add constraint:    constraints += [expression]
    # to add cost:          cost += value

    for k in range(N):
        T_outk = T_out[k]
        C_int = carbon_intensity[k]
        T_k = T[:,k]
        T_k1 = T[:,k+1]
        u_k = u[:,k]

        constraints += [T_k1 == a*T_k + b*u_k + c*T_outk + d]

        cost += weight_input * u_k * C_int
        cost += weight_tracking * cp.square(T_k1 - T_target)
        cost += weight_smoothing * cp.square(u_k)

    # initial temperature    
    constraints += [T[:,0] == T0]

    # input constraints
    constraints += [u >= 0]
    constraints += [u <= 1500]

    problem = cp.Problem(cp.Minimize(cost), constraints)
    problem.solve(solver=cp.CLARABEL, **{"verbose": False})

    # return next input
    return u[0, 0].value
