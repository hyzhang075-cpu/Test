# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `-31.4`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | False | True | False | optimization stages are not usable; tail improvement at radius 15 is -2.86052%; tip position at full/2000 is 1.02172%; tip position at full/1500 is 1.23969%; tip position at full/1000 is 1.73854%; tip tangent at full/1000 is 11.6917 deg; tip position at full/800 is 2.22067%; tip tangent at full/800 is 14.7119 deg; tip position at full/600 is 1.82313%; tip tangent at full/600 is 12.8747 deg; tip position at full/300 is 1.61589%; tip position at full/200 is 2.32287%; tip position at end15cm/100 is 4.71223%; tip tangent at end15cm/100 is 16.7821 deg; tip position at end15cm/75 is 5.75531%; tip tangent at end15cm/75 is 19.443 deg; tip position at end15cm/50 is 4.13196%; tip tangent at end15cm/50 is 35.9575 deg; tip position at end15cm/30 is 2.95884%; tip tangent at end15cm/30 is 59.5297 deg; tip position at end5cm/30 is 1.05127%; tip tangent at end5cm/30 is 15.4444 deg; tip tangent at end5cm/20 is 128.832 deg; tip position at end5cm/15 is 1.06462%; tip tangent at end5cm/15 is 110.756 deg; boundary curvature angle jump is 175.924 deg |
| 120 | False | False | True | False | optimization stages are not usable; full mean point error at radius 400 is 1.01586%; full mean point error at radius 200 is 1.26433%; tip position at full/400 is 2.41123%; tip tangent at full/400 is 18.2395 deg; tip position at full/300 is 2.00866%; tip tangent at full/300 is 13.2473 deg; tip position at full/200 is 4.51526%; tip tangent at full/200 is 26.3239 deg; tip position at end15cm/100 is 2.32673%; tip tangent at end15cm/100 is 17.1376 deg; tip position at end15cm/75 is 2.25162%; tip tangent at end15cm/75 is 16.5508 deg; tip position at end15cm/50 is 3.11176%; tip tangent at end15cm/50 is 26.8478 deg; tip position at end15cm/30 is 1.86838%; tip tangent at end15cm/30 is 18.6401 deg; tip position at end5cm/20 is 1.16896%; tip tangent at end5cm/20 is 11.7057 deg; tip tangent at end5cm/15 is 49.3206 deg; boundary curvature angle jump is 66.8158 deg |
| 240 | False | False | True | False | optimization stages are not usable; full mean point error at radius 200 is 1.28674%; tip position at full/400 is 1.12568%; tip position at full/300 is 1.4267%; tip tangent at full/300 is 10.3205 deg; tip position at full/200 is 1.24405%; tip position at end15cm/100 is 8.49853%; tip tangent at end15cm/100 is 39.6676 deg; tip position at end15cm/75 is 9.83663%; tip tangent at end15cm/75 is 39.9343 deg; tip position at end15cm/50 is 9.39833%; tip tangent at end15cm/50 is 33.5887 deg; tip position at end15cm/30 is 4.35414%; tip tangent at end15cm/30 is 112.988 deg; tip position at end5cm/30 is 1.37801%; tip tangent at end5cm/30 is 20.6586 deg; tip tangent at end5cm/20 is 13.8037 deg; boundary curvature angle jump is 115.794 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 28.210 | 30.000 | True | True |
| 0 | end5cm | 27.066 | 30.000 | True | False |
| 120 | end15cm | 24.016 | 30.000 | True | True |
| 120 | end5cm | 27.466 | 30.000 | True | False |
| 240 | end15cm | 26.449 | 30.000 | True | True |
| 240 | end5cm | 25.255 | 30.000 | True | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.112 | 0.124 | -11.262 | 9.039 | 1.022 | 6.487 |
| 0 | full | 1500 | 0.381 | 0.366 | 3.998 | 10.968 | 1.240 | 7.896 |
| 0 | full | 1000 | 0.521 | 0.450 | 13.690 | 15.381 | 1.739 | 11.692 |
| 0 | full | 800 | 0.244 | 0.329 | -34.656 | 19.646 | 2.221 | 14.712 |
| 0 | full | 600 | 0.614 | 0.590 | 3.840 | 16.129 | 1.823 | 12.875 |
| 0 | full | 400 | 0.301 | 0.284 | 5.455 | 2.180 | 0.246 | 1.513 |
| 0 | full | 300 | 0.325 | 0.378 | -16.459 | 14.296 | 1.616 | 4.508 |
| 0 | full | 200 | 0.408 | 0.562 | -37.598 | 20.550 | 2.323 | 8.340 |
| 0 | end15cm | 100 | 1.750 | 1.972 | -12.690 | 41.689 | 4.712 | 16.782 |
| 0 | end15cm | 75 | 2.229 | 2.542 | -14.068 | 50.917 | 5.755 | 19.443 |
| 0 | end15cm | 50 | 2.755 | 2.715 | 1.436 | 36.555 | 4.132 | 35.957 |
| 0 | end15cm | 30 | 2.840 | 2.334 | 17.798 | 26.177 | 2.959 | 59.530 |
| 0 | end5cm | 30 | 1.485 | 0.746 | 49.731 | 9.301 | 1.051 | 15.444 |
| 0 | end5cm | 20 | 1.680 | 1.187 | 29.312 | 7.542 | 0.853 | 128.832 |
| 0 | end5cm | 15 | 1.865 | 1.918 | -2.861 | 9.419 | 1.065 | 110.756 |
| 120 | full | 2000 | 0.208 | 0.211 | -1.041 | 1.080 | 0.122 | 1.482 |
| 120 | full | 1500 | 0.193 | 0.220 | -14.139 | 3.842 | 0.434 | 1.683 |
| 120 | full | 1000 | 0.361 | 0.325 | 10.179 | 4.152 | 0.469 | 4.579 |
| 120 | full | 800 | 0.520 | 0.504 | 3.011 | 8.094 | 0.915 | 6.031 |
| 120 | full | 600 | 0.429 | 0.406 | 5.359 | 3.525 | 0.398 | 0.638 |
| 120 | full | 400 | 1.007 | 1.016 | -0.907 | 21.332 | 2.411 | 18.240 |
| 120 | full | 300 | 0.780 | 0.788 | -0.988 | 17.771 | 2.009 | 13.247 |
| 120 | full | 200 | 1.091 | 1.264 | -15.907 | 39.946 | 4.515 | 26.324 |
| 120 | end15cm | 100 | 5.191 | 0.946 | 81.779 | 20.585 | 2.327 | 17.138 |
| 120 | end15cm | 75 | 6.220 | 1.009 | 83.778 | 19.920 | 2.252 | 16.551 |
| 120 | end15cm | 50 | 6.911 | 1.272 | 81.593 | 27.530 | 3.112 | 26.848 |
| 120 | end15cm | 30 | 5.370 | 1.379 | 74.316 | 16.530 | 1.868 | 18.640 |
| 120 | end5cm | 30 | 2.015 | 0.559 | 72.234 | 6.126 | 0.692 | 5.740 |
| 120 | end5cm | 20 | 3.009 | 0.977 | 67.530 | 10.342 | 1.169 | 11.706 |
| 120 | end5cm | 15 | 3.310 | 1.139 | 65.603 | 5.400 | 0.610 | 49.321 |
| 240 | full | 2000 | 0.236 | 0.205 | 12.956 | 3.339 | 0.377 | 1.071 |
| 240 | full | 1500 | 0.189 | 0.219 | -15.925 | 5.888 | 0.666 | 2.928 |
| 240 | full | 1000 | 0.415 | 0.419 | -1.068 | 7.417 | 0.838 | 3.359 |
| 240 | full | 800 | 0.345 | 0.349 | -0.986 | 8.716 | 0.985 | 2.845 |
| 240 | full | 600 | 0.937 | 0.883 | 5.852 | 8.561 | 0.968 | 2.444 |
| 240 | full | 400 | 0.624 | 0.646 | -3.562 | 9.959 | 1.126 | 6.673 |
| 240 | full | 300 | 0.733 | 0.806 | -9.975 | 12.622 | 1.427 | 10.321 |
| 240 | full | 200 | 1.223 | 1.287 | -5.177 | 11.006 | 1.244 | 9.462 |
| 240 | end15cm | 100 | 3.158 | 3.276 | -3.736 | 75.186 | 8.499 | 39.668 |
| 240 | end15cm | 75 | 3.798 | 4.009 | -5.546 | 87.025 | 9.837 | 39.934 |
| 240 | end15cm | 50 | 4.590 | 4.705 | -2.517 | 83.147 | 9.398 | 33.589 |
| 240 | end15cm | 30 | 3.870 | 4.016 | -3.795 | 38.521 | 4.354 | 112.988 |
| 240 | end5cm | 30 | 1.458 | 0.792 | 45.688 | 12.191 | 1.378 | 20.659 |
| 240 | end5cm | 20 | 1.855 | 0.815 | 56.049 | 8.833 | 0.998 | 13.804 |
| 240 | end5cm | 15 | 2.122 | 0.955 | 54.973 | 8.212 | 0.928 | 4.144 |

## Shared score evidence

- source: `./calibration_results/09B7-20261102T172615+0800-direct0-1f0a15/results.json`
- failures: `[]`
