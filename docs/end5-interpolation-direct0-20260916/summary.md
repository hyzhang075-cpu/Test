# End5 direct=0 interpolation diagnosis

Coordinates: m in traces, mm in figures; curvature: 1/m; angles displayed in deg.

Local uses the saved end5 optimization phase; merged grafts local mean strain onto full straight replay.

| radius mm | theoretical 1/m | last real 1/m | interpolated tip 1/m | last/theory % | full grid points in last 5 cm | PCHIP knot error 1/m |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 20.000 | 7.689 | 7.689 | 38.45 | 7 | 8.67e-19 |
| 30 | 33.333 | 14.916 | 14.916 | 44.75 | 7 | 8.67e-19 |
| 20 | 50.000 | 17.169 | 17.169 | 34.34 | 7 | 8.67e-19 |
| 15 | 66.667 | 18.053 | 18.053 | 27.08 | 7 | 8.67e-19 |

## Full-to-end15 start phase, direct=0

| full calibration radius mm | predicted phase rad | local phase rad | signed difference deg |
|---:|---:|---:|---:|
| 0 | 0.463689 | -0.201820 | 38.131 |
| 2000 | -0.467400 | -0.201820 | -15.217 |
| 1500 | -0.613153 | -0.201820 | -23.568 |
| 1000 | -0.572095 | -0.201820 | -21.215 |
| 800 | -0.494112 | -0.201820 | -16.747 |
| 600 | -0.505406 | -0.201820 | -17.394 |
| 400 | -0.580339 | -0.201820 | -21.688 |
| 300 | -0.565421 | -0.201820 | -20.833 |
| 200 | -0.579219 | -0.201820 | -21.623 |

## Interpretation

- All replay intermediates are finite. The virtual tip copies the last real magnitude and angle; its curvature is not independently estimated.
- PCHIP preserves the original knots and endpoint. Increasing output-grid density can recover missed peaks between grid samples, but cannot raise the low last real point.
- In the 30/20/15 mm samples, local and merged last-four-point magnitudes agree within 1.5e-14 1/m; their angles differ by a constant -134.191863 deg. This comparison is before final rot_ang/direct coordinate rotation.
- Full-to-end15 phase is a channel twist reference, not the reconstructed curvature direction. Its score-blended value varies across calibration states. A fixed local phase must specify which full reference is used and share the runtime boundary-integration convention.
- A local reference copied from full alone does not guarantee runtime equivalence: merged integration uses the regional slope for the interval from the preceding full point to the first regional point. Freeze/transport the upstream full reference and include this bridge interval when reoptimizing local parameters.
- No production optimizer, reconstructor, or parameter package was changed by this diagnosis. The mean calibration-state replay is not an independent measurement of the reported dynamic 30-degree offset.
