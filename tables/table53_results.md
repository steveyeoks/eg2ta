**Table 5.3. Results for the rows of Table 5.2, one row per model and one run per cell: verdict, witness length in fire actions where a trace exists, wall time, states explored. ORDERING is asked at n = 2.**

| problem, model | $n = 1$ | $n = 2$ | $n = 3$ |
|---|---|---|---|
| ACCESSIBILITY (a) | SAT, 13 fires, 0.07 s, 38 states | SAT, 15 fires, 0.05 s, 98 states | SAT, 23 fires, 0.07 s, 464 states |
| ORDERING (d), $\succ_1$, $P_1$ |  | SAT, 6 fires, 0.05 s, 13 states |  |
| ORDERING (d), $\succ_1$, $P_2$ |  | UNSAT, 0.05 s, 41 states |  |
| ORDERING (d), $\succ_2$, $P_1$ |  | UNSAT, 0.06 s, 41 states |  |
| ORDERING (d), $\succ_2$, $P_2$ |  | SAT, 6 fires, 0.05 s, 13 states |  |
| NONINTERCHANGEABILITY (b) | SAT, 0.05 s, 35 states | SAT, 0.05 s, 97 states | SAT, 0.05 s, 184 states |
| NONINTERCHANGEABILITY (c) | UNSAT, 7 fires, 0.05 s, 27 states | UNSAT, 11 fires, 0.05 s, 58 states | UNSAT, 15 fires, 0.05 s, 71 states |
| STALLING (b) | UNSAT, 0.05 s, 27 states | UNSAT, 0.05 s, 83 states | UNSAT, 0.05 s, 168 states |
| STALLING (c) | SAT, 7 fires, 0.05 s, 19 states | SAT, 11 fires, 0.06 s, 61 states | SAT, 15 fires, 0.05 s, 140 states |
