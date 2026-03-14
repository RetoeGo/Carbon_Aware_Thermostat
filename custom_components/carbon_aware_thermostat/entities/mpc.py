import cvxpy as cp
import numpy as np
from dataclasses import dataclass

@dataclass
class RLS:
    a: float
    b: float
    c: float
    d: float

def mpc_control(RLS_model, N, T0, T_target, T_out):
    weight_input = 0.1
    weight_tracking = 1000
    
    cost = 0.0
    constraints = []

    # cp.Variable((dim_1, dim_2))
    T = cp.Variable((1, N + 1)) 
    u = cp.Variable((1, N))

    a = RLS_model.a
    b = RLS_model.b
    c = RLS_model.c
    d = RLS_model.d

    # to add constraint:    constraints += [expression]
    # to add cost:          cost += value

    for k in range(N):   
        T_k = T[:,k]
        T_k1 = T[:,k+1]
        u_k = u[:,k]

        constraints += [T_k1 == a*T_k + b*u_k + c*T_out + d]

        cost += weight_input * u_k
        cost += weight_tracking * cp.abs(T_k1 - T_target)

    # initial temperature    
    constraints += [T[:,0] == T0]

    # input constraints
    constraints += [u >= 100]
    constraints += [u <= 5000]

    problem = cp.Problem(cp.Minimize(cost), constraints)
    problem.solve(solver=cp.OSQP)

    # return next input
    return u[:, 0].value