| run | kind | poses | span s | rate Hz | err med m | err p95 m | err max m | converged at s | p95 after conv | max after conv | yaw med deg | poses err>0.5 | flagged among them | flagged while err<=0.5 | max gap s | proc med/p95 ms | CPU % med (A3: NDT) | RSS MB max (A3: NDT) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_p1s | A | 539 | 60 | 9.01 | 0.039 | 0.108 | 1.000 | 1.0 | 0.108 | 0.134 | 0.14 | 1 | 1 | 4 | 4.20 | 52/63 | 65 | 811 |
| a3_p1s | A3 | 541 | 58 | 9.30 | 0.067 | 0.118 | 0.222 | 0.0 | 0.118 | 0.222 | 0.23 | 0 | 0 | 4 | 4.20 | 16/48 | 6 | 186 |
| a_p2s | A | 537 | 60 | 8.98 | 0.040 | 0.111 | 2.828 | 1.7 | 0.109 | 0.134 | 0.14 | 3 | 3 | 5 | 4.20 | 52/68 | 69 | 725 |
| a3_p2s | A3 | 0 | no pose output | | | | | | | | | | | | | | | |
| a3_p2as | A3 | 522 | 56 | 9.27 | 0.066 | 0.117 | 0.221 | 0.0 | 0.117 | 0.221 | 0.24 | 0 | 0 | 7 | 4.20 | 17/47 | 37 | 188 |
| a_p3s | A | 524 | 60 | 8.76 | 6.800 | 9.165 | 9.716 | never | nan | nan | 4.50 | 524 | 16 | 0 | 4.20 | 43/175 | 76 | 777 |
| a3_p3as | A3 | 521 | 56 | 9.24 | 0.066 | 0.120 | 0.220 | 0.0 | 0.120 | 0.220 | 0.24 | 0 | 0 | 12 | 4.20 | 16/56 | 38 | 188 |

a_p1s {'healthy': 534, 'overload': 4, 'stale_prediction': 1}
a3_p1s {'healthy': 540, 'iteration_limit+oscillation': 1, 'latency': 1, 'no_initial_pose': 2, 'not_activated': 11, 'out_of_map': 4}
a_p2s {'healthy': 530, 'overload': 6, 'stale_prediction': 1}
a3_p2as {'healthy': 518, 'iteration_limit+oscillation': 3, 'latency': 1, 'no_initial_pose': 1, 'not_activated': 13, 'oscillation': 1}
a_p3s {'bad_match': 1, 'healthy': 510, 'overload': 13, 'stale_prediction': 1}
a3_p3as {'healthy': 509, 'iteration_limit+oscillation': 3, 'latency': 1, 'no_initial_pose': 2, 'not_activated': 13, 'slow': 9}
