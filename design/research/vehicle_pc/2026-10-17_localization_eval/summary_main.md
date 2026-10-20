| run | kind | poses | span s | rate Hz | err med m | err p95 m | err max m | converged at s | p95 after conv | max after conv | yaw med deg | poses err>0.5 | flagged among them | flagged while err<=0.5 | max gap s | proc med/p95 ms | CPU % med (A3: NDT) | RSS MB max (A3: NDT) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_full | A | 6610 | 686 | 9.64 | 0.060 | 0.124 | 0.286 | 0.0 | 0.124 | 0.286 | 0.21 | 0 | 0 | 39 | 4.20 | 55/84 | 141 | 1374 |
| a3_full | A3 | 6748 | 681 | 9.90 | 0.068 | 0.209 | 0.546 | 0.0 | 0.209 | 0.546 | 0.27 | 1 | 0 | 15 | 4.20 | 33/55 | 57 | 205 |
| a_rt | A | 993 | 120 | 8.29 | 0.059 | 0.127 | 0.230 | 0.0 | 0.127 | 0.230 | 0.19 | 0 | 0 | 12 | 1.00 | 53/100 | 170 | 1163 |
| a3_rt | A3 | 1091 | 110 | 9.89 | 0.062 | 0.220 | 0.334 | 0.0 | 0.220 | 0.334 | 0.17 | 0 | 0 | 11 | 0.60 | 22/75 | 118 | 192 |
| a_p1 | A | 581 | 60 | 9.72 | 0.063 | 0.127 | 1.009 | 1.3 | 0.125 | 0.201 | 0.34 | 2 | 2 | 5 | 1.00 | 52/63 | 82 | 950 |
| a_p2 | A | 571 | 60 | 9.55 | 0.068 | 3.403 | 4.004 | 11.2 | 0.131 | 0.201 | 0.45 | 92 | 6 | 4 | 1.00 | 52/80 | 96 | 927 |
| a3_p1 | A3 | 583 | 58 | 10.02 | 0.069 | 0.248 | 0.331 | 0.0 | 0.248 | 0.331 | 0.31 | 0 | 0 | 2 | 0.10 | 39/56 | 39 | 192 |
| a3_p2 | A3 | 0 | no pose output | | | | | | | | | | | | | | | |
| a3_p2a | A3 | 0 | no pose output | | | | | | | | | | | | | | | |

a_full {'healthy': 6589, 'overload': 60, 'stale_prediction': 1}
a3_full {'healthy': 6800, 'iteration_limit': 2, 'iteration_limit+oscillation': 3, 'latency': 1, 'no_initial_pose': 2, 'not_activated': 12, 'out_of_map': 4, 'slow': 4, 'slow+iteration_limit': 4, 'slow+iteration_limit+low_score': 24, 'slow+iteration_limit+oscillation': 2}
a_rt {'healthy': 987, 'overload': 8}
a3_rt {'healthy': 1086, 'iteration_limit': 3, 'no_initial_pose': 1, 'not_activated': 12, 'out_of_map': 4, 'slow': 8, 'slow+iteration_limit': 4, 'slow+iteration_limit+low_score': 34}
a_p1 {'healthy': 575, 'overload': 5}
a_p2 {'healthy': 558, 'overload': 12}
a3_p1 {'healthy': 583, 'no_initial_pose': 1, 'not_activated': 12, 'out_of_map': 4}
