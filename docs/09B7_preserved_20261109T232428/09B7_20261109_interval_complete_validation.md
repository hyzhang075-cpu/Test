# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | True | False | full mean point error at radius 2000 is 1.05392%; full mean point error at radius 1000 is 1.54358%; full mean point error at radius 800 is 1.23711%; full mean point error at radius 600 is 1.81195%; full mean point error at radius 400 is 1.18868%; full mean point error at radius 300 is 1.33567%; full mean point error at radius 200 is 1.67368%; tail improvement at radius 30 is 2.62836%; tail improvement at radius 20 is 7.28975%; tail improvement at radius 15 is 9.93986%; tip position at full/2000 is 3.13918%; tip position at full/1000 is 4.73742%; tip position at full/800 is 3.43607%; tip position at full/600 is 5.08758%; tip position at full/400 is 3.47628%; tip position at full/300 is 2.78518%; tip position at full/200 is 4.0068%; tip tangent at full/200 is 10.9798 deg; tip position at end15cm/100 is 1.11004%; tip position at end15cm/75 is 1.55834%; tip position at end15cm/50 is 2.17111%; tip position at end15cm/30 is 4.50963%; tip tangent at end15cm/30 is 39.8227 deg; tip position at end5cm/30 is 2.37436%; tip tangent at end5cm/30 is 14.4753 deg; tip position at end5cm/20 is 2.55252%; tip tangent at end5cm/20 is 20.7091 deg; tip position at end5cm/15 is 2.3089%; tip tangent at end5cm/15 is 31.3922 deg; boundary curvature angle jump is 50.6287 deg |
| 120 | False | True | True | False | full mean point error at radius 2000 is 1.43957%; full mean point error at radius 1000 is 1.32353%; full mean point error at radius 800 is 4.17058%; full mean point error at radius 600 is 1.1428%; full mean point error at radius 400 is 1.85817%; full mean point error at radius 300 is 2.48821%; full mean point error at radius 200 is 2.40139%; tail improvement at radius 30 is -39.3063%; tail improvement at radius 20 is -39.9643%; tail improvement at radius 15 is -31.4095%; tip position at full/2000 is 4.08429%; tip position at full/1500 is 1.53731%; tip position at full/1000 is 3.72537%; tip position at full/800 is 12.4468%; tip tangent at full/800 is 15.2884 deg; tip position at full/600 is 3.42924%; tip position at full/400 is 4.29879%; tip position at full/300 is 5.17241%; tip position at full/200 is 3.46353%; tip position at end15cm/50 is 1.43191%; tip position at end15cm/30 is 2.30254%; tip position at end5cm/30 is 2.93145%; tip tangent at end5cm/30 is 19.9712 deg; tip position at end5cm/20 is 3.06311%; tip tangent at end5cm/20 is 27.1206 deg; tip position at end5cm/15 is 2.49182%; tip tangent at end5cm/15 is 40.1698 deg; boundary curvature angle jump is 64.3875 deg |
| 240 | False | True | True | False | full mean point error at radius 2000 is 1.81415%; full mean point error at radius 1000 is 1.73289%; full mean point error at radius 800 is 3.49483%; full mean point error at radius 600 is 5.54077%; full mean point error at radius 400 is 5.48858%; full mean point error at radius 300 is 4.17639%; full mean point error at radius 200 is 4.14213%; tail improvement at radius 30 is -22.1734%; tail improvement at radius 20 is -18.0703%; tail improvement at radius 15 is -17.4359%; tip position at full/2000 is 5.22248%; tip position at full/1500 is 2.78776%; tip position at full/1000 is 4.93721%; tip position at full/800 is 9.71602%; tip position at full/600 is 14.9658%; tip tangent at full/600 is 12.7846 deg; tip position at full/400 is 13.2638%; tip position at full/300 is 8.08397%; tip position at full/200 is 6.88212%; tip tangent at full/200 is 16.0892 deg; tip position at end15cm/75 is 1.19756%; tip tangent at end15cm/75 is 10.8723 deg; tip position at end15cm/50 is 2.29476%; tip tangent at end15cm/50 is 26.6774 deg; tip position at end15cm/30 is 1.91649%; tip tangent at end15cm/30 is 13.3715 deg; tip position at end5cm/30 is 2.66465%; tip tangent at end5cm/30 is 18.6893 deg; tip position at end5cm/20 is 2.82795%; tip tangent at end5cm/20 is 24.6908 deg; tip position at end5cm/15 is 2.5168%; tip tangent at end5cm/15 is 37.888 deg; boundary curvature angle jump is 100.667 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 2.517 | 30.000 | True | True |
| 0 | end5cm | 23.122 | 30.000 | True | False |
| 120 | end15cm | 1.151 | 30.000 | True | True |
| 120 | end5cm | 6.124 | 30.000 | True | False |
| 240 | end15cm | 6.924 | 30.000 | True | True |
| 240 | end5cm | 10.411 | 30.000 | True | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 1.063 | 1.054 | 0.832 | 27.782 | 3.139 | 2.668 |
| 0 | full | 1500 | 0.217 | 0.211 | 3.043 | 4.757 | 0.538 | 1.167 |
| 0 | full | 1000 | 1.535 | 1.544 | -0.588 | 41.926 | 4.737 | 5.710 |
| 0 | full | 800 | 1.227 | 1.237 | -0.830 | 30.409 | 3.436 | 2.986 |
| 0 | full | 600 | 1.800 | 1.812 | -0.682 | 45.025 | 5.088 | 6.044 |
| 0 | full | 400 | 1.184 | 1.189 | -0.362 | 30.765 | 3.476 | 8.129 |
| 0 | full | 300 | 1.360 | 1.336 | 1.823 | 24.649 | 2.785 | 4.302 |
| 0 | full | 200 | 1.671 | 1.674 | -0.155 | 35.460 | 4.007 | 10.980 |
| 0 | end15cm | 100 | 1.452 | 0.687 | 52.690 | 9.824 | 1.110 | 3.457 |
| 0 | end15cm | 75 | 1.916 | 0.955 | 50.179 | 13.791 | 1.558 | 5.504 |
| 0 | end15cm | 50 | 2.486 | 1.335 | 46.299 | 19.214 | 2.171 | 9.324 |
| 0 | end15cm | 30 | 2.178 | 1.965 | 9.791 | 39.910 | 4.510 | 39.823 |
| 0 | end5cm | 30 | 1.747 | 1.701 | 2.628 | 21.013 | 2.374 | 14.475 |
| 0 | end5cm | 20 | 2.185 | 2.025 | 7.290 | 22.590 | 2.553 | 20.709 |
| 0 | end5cm | 15 | 2.578 | 2.322 | 9.940 | 20.434 | 2.309 | 31.392 |
| 120 | full | 2000 | 1.439 | 1.440 | -0.067 | 36.146 | 4.084 | 4.051 |
| 120 | full | 1500 | 0.507 | 0.509 | -0.417 | 13.605 | 1.537 | 1.878 |
| 120 | full | 1000 | 1.324 | 1.324 | 0.021 | 32.970 | 3.725 | 3.854 |
| 120 | full | 800 | 4.165 | 4.171 | -0.129 | 110.154 | 12.447 | 15.288 |
| 120 | full | 600 | 1.128 | 1.143 | -1.340 | 30.349 | 3.429 | 6.332 |
| 120 | full | 400 | 1.868 | 1.858 | 0.534 | 38.044 | 4.299 | 3.410 |
| 120 | full | 300 | 2.503 | 2.488 | 0.589 | 45.776 | 5.172 | 3.264 |
| 120 | full | 200 | 2.415 | 2.401 | 0.570 | 30.652 | 3.464 | 2.296 |
| 120 | end15cm | 100 | 0.676 | 0.365 | 45.924 | 3.279 | 0.371 | 4.819 |
| 120 | end15cm | 75 | 0.866 | 0.508 | 41.361 | 6.980 | 0.789 | 6.994 |
| 120 | end15cm | 50 | 1.292 | 0.913 | 29.316 | 12.672 | 1.432 | 0.764 |
| 120 | end15cm | 30 | 1.685 | 1.364 | 19.051 | 20.377 | 2.303 | 3.361 |
| 120 | end5cm | 30 | 1.477 | 2.058 | -39.306 | 25.943 | 2.931 | 19.971 |
| 120 | end5cm | 20 | 1.711 | 2.395 | -39.964 | 27.109 | 3.063 | 27.121 |
| 120 | end5cm | 15 | 1.847 | 2.427 | -31.410 | 22.053 | 2.492 | 40.170 |
| 240 | full | 2000 | 1.819 | 1.814 | 0.268 | 46.219 | 5.222 | 4.734 |
| 240 | full | 1500 | 0.998 | 0.993 | 0.451 | 24.672 | 2.788 | 1.788 |
| 240 | full | 1000 | 1.746 | 1.733 | 0.738 | 43.694 | 4.937 | 4.375 |
| 240 | full | 800 | 3.507 | 3.495 | 0.359 | 85.987 | 9.716 | 8.650 |
| 240 | full | 600 | 5.550 | 5.541 | 0.175 | 132.448 | 14.966 | 12.785 |
| 240 | full | 400 | 5.512 | 5.489 | 0.421 | 117.385 | 13.264 | 5.384 |
| 240 | full | 300 | 4.205 | 4.176 | 0.679 | 71.543 | 8.084 | 9.728 |
| 240 | full | 200 | 4.166 | 4.142 | 0.582 | 60.907 | 6.882 | 16.089 |
| 240 | end15cm | 100 | 0.533 | 0.514 | 3.621 | 7.973 | 0.901 | 8.943 |
| 240 | end15cm | 75 | 0.751 | 0.721 | 4.086 | 10.598 | 1.198 | 10.872 |
| 240 | end15cm | 50 | 0.865 | 1.189 | -37.478 | 20.309 | 2.295 | 26.677 |
| 240 | end15cm | 30 | 1.170 | 1.330 | -13.658 | 16.961 | 1.916 | 13.372 |
| 240 | end5cm | 30 | 1.473 | 1.799 | -22.173 | 23.582 | 2.665 | 18.689 |
| 240 | end5cm | 20 | 1.807 | 2.133 | -18.070 | 25.027 | 2.828 | 24.691 |
| 240 | end5cm | 15 | 1.982 | 2.327 | -17.436 | 22.274 | 2.517 | 37.888 |

## Shared score evidence

- source: `./calibration_results/09B7-20261109T180749+0800-direct0-d73f6c/results.json`
- failures: `[]`
