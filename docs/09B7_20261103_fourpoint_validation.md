# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `-60.0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | False | False | False | optimization stages are not usable; full mean point error at radius 800 is 1.05352%; full mean point error at radius 600 is 1.06137%; full mean point error at radius 400 is 1.63504%; full regression at radius 400 is 0.23274 percentage points; full mean point error at radius 300 is 2.10697%; full regression at radius 300 is 0.266393 percentage points; full mean point error at radius 200 is 3.17611%; full regression at radius 200 is 0.305209 percentage points; tail improvement at radius 30 is -296.258%; tail improvement at radius 20 is -349.492%; tail improvement at radius 15 is -327.839%; tip position at full/2000 is 2.5783%; tip position at full/1500 is 2.81672%; tip tangent at full/1500 is 11.2799 deg; tip position at full/1000 is 3.12995%; tip tangent at full/1000 is 15.6774 deg; tip position at full/800 is 5.06057%; tip tangent at full/800 is 20.6072 deg; tip position at full/600 is 4.55792%; tip tangent at full/600 is 26.2065 deg; tip position at full/400 is 7.33911%; tip tangent at full/400 is 36.4343 deg; tip position at full/300 is 8.4307%; tip tangent at full/300 is 44.3563 deg; tip position at full/200 is 9.47785%; tip tangent at full/200 is 60.7242 deg; tip position at end15cm/100 is 14.7482%; tip tangent at end15cm/100 is 104.812 deg; tip position at end15cm/75 is 16.8924%; tip tangent at end15cm/75 is 100.518 deg; tip position at end15cm/50 is 16.6248%; tip tangent at end15cm/50 is 45.2483 deg; tip position at end15cm/30 is 6.40348%; tip tangent at end15cm/30 is 56.9303 deg; tip position at end5cm/30 is 6.86659%; tip tangent at end5cm/30 is 127.314 deg; tip position at end5cm/20 is 7.27956%; tip tangent at end5cm/20 is 68.3776 deg; tip position at end5cm/15 is 5.60835%; tip tangent at end5cm/15 is 20.1909 deg; boundary curvature angle jump is 125.347 deg; end15cm phase error is 112.666 deg |
| 120 | False | True | False | False | full mean point error at radius 800 is 1.09871%; full mean point error at radius 600 is 1.15764%; full mean point error at radius 400 is 1.6276%; full regression at radius 400 is 0.25253 percentage points; full mean point error at radius 300 is 2.37282%; full regression at radius 300 is 0.321102 percentage points; full mean point error at radius 200 is 3.20854%; full regression at radius 200 is 0.390449 percentage points; tail improvement at radius 30 is -259.796%; tail improvement at radius 20 is -167.545%; tail improvement at radius 15 is -159.505%; tip position at full/1500 is 1.63049%; tip position at full/1000 is 2.4242%; tip tangent at full/1000 is 13.1663 deg; tip position at full/800 is 5.16201%; tip tangent at full/800 is 17.7804 deg; tip position at full/600 is 5.30156%; tip tangent at full/600 is 23.4324 deg; tip position at full/400 is 6.91397%; tip tangent at full/400 is 34.6824 deg; tip position at full/300 is 8.92293%; tip tangent at full/300 is 46.2969 deg; tip position at full/200 is 9.75008%; tip tangent at full/200 is 60.032 deg; tip position at end15cm/100 is 12.7254%; tip tangent at end15cm/100 is 89.7177 deg; tip position at end15cm/75 is 15.075%; tip tangent at end15cm/75 is 89.6517 deg; tip position at end15cm/50 is 15.2719%; tip tangent at end15cm/50 is 37.1517 deg; tip position at end15cm/30 is 5.78173%; tip tangent at end15cm/30 is 58.8873 deg; tip position at end5cm/30 is 5.89695%; tip tangent at end5cm/30 is 101.687 deg; tip position at end5cm/20 is 6.8537%; tip tangent at end5cm/20 is 62.6422 deg; tip position at end5cm/15 is 5.57101%; tip tangent at end5cm/15 is 19.7265 deg; boundary curvature angle jump is 156.529 deg; end15cm phase error is 105.592 deg |
| 240 | False | True | False | False | full mean point error at radius 400 is 1.36965%; full regression at radius 400 is 0.20462 percentage points; full mean point error at radius 300 is 2.3953%; full regression at radius 300 is 0.357219 percentage points; full mean point error at radius 200 is 2.81975%; full regression at radius 200 is 0.376832 percentage points; tip position at full/600 is 1.40859%; tip position at full/400 is 6.94264%; tip tangent at full/400 is 36.2033 deg; tip position at full/300 is 8.9742%; tip tangent at full/300 is 28.9617 deg; tip position at full/200 is 9.04176%; tip tangent at full/200 is 50.7361 deg; tip position at end15cm/100 is 13.7419%; tip tangent at end15cm/100 is 74.9442 deg; tip position at end15cm/75 is 15.5289%; tip tangent at end15cm/75 is 66.0729 deg; tip position at end15cm/50 is 15.0889%; tip tangent at end15cm/50 is 25.6574 deg; tip position at end15cm/30 is 4.72389%; tip tangent at end15cm/30 is 115.624 deg; tip position at end5cm/30 is 1.96059%; tip tangent at end5cm/30 is 27.3344 deg; tip position at end5cm/20 is 2.64335%; tip tangent at end5cm/20 is 22.5683 deg; tip position at end5cm/15 is 2.52236%; boundary curvature angle jump is 165.758 deg; end15cm phase error is 44.2612 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 112.666 | 30.000 | False | True |
| 0 | end5cm | 65.087 | 30.000 | False | False |
| 120 | end15cm | 105.592 | 30.000 | False | True |
| 120 | end5cm | 60.839 | 30.000 | False | False |
| 240 | end15cm | 44.261 | 30.000 | False | True |
| 240 | end5cm | 170.751 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.425 | 0.492 | -15.717 | 22.895 | 2.578 | 9.687 |
| 0 | full | 1500 | 0.445 | 0.500 | -12.486 | 25.012 | 2.817 | 11.280 |
| 0 | full | 1000 | 0.496 | 0.601 | -21.137 | 27.794 | 3.130 | 15.677 |
| 0 | full | 800 | 0.901 | 1.054 | -16.948 | 44.938 | 5.061 | 20.607 |
| 0 | full | 600 | 0.891 | 1.061 | -19.066 | 40.474 | 4.558 | 26.206 |
| 0 | full | 400 | 1.402 | 1.635 | -16.597 | 65.171 | 7.339 | 36.434 |
| 0 | full | 300 | 1.841 | 2.107 | -14.473 | 74.865 | 8.431 | 44.356 |
| 0 | full | 200 | 2.871 | 3.176 | -10.631 | 84.163 | 9.478 | 60.724 |
| 0 | end15cm | 100 | 0.371 | 5.136 | -1284.612 | 130.964 | 14.748 | 104.812 |
| 0 | end15cm | 75 | 0.549 | 6.242 | -1037.365 | 150.004 | 16.892 | 100.518 |
| 0 | end15cm | 50 | 0.848 | 7.215 | -750.884 | 147.629 | 16.625 | 45.248 |
| 0 | end15cm | 30 | 1.349 | 5.812 | -330.944 | 56.863 | 6.403 | 56.930 |
| 0 | end5cm | 30 | 0.745 | 2.953 | -296.258 | 60.975 | 6.867 | 127.314 |
| 0 | end5cm | 20 | 0.787 | 3.538 | -349.492 | 64.642 | 7.280 | 68.378 |
| 0 | end5cm | 15 | 0.812 | 3.475 | -327.839 | 49.802 | 5.608 | 20.191 |
| 120 | full | 2000 | 0.472 | 0.464 | 1.596 | 5.499 | 0.619 | 5.890 |
| 120 | full | 1500 | 0.432 | 0.491 | -13.525 | 14.479 | 1.630 | 7.542 |
| 120 | full | 1000 | 0.571 | 0.659 | -15.401 | 21.527 | 2.424 | 13.166 |
| 120 | full | 800 | 0.960 | 1.099 | -14.432 | 45.839 | 5.162 | 17.780 |
| 120 | full | 600 | 0.970 | 1.158 | -19.403 | 47.078 | 5.302 | 23.432 |
| 120 | full | 400 | 1.375 | 1.628 | -18.365 | 61.396 | 6.914 | 34.682 |
| 120 | full | 300 | 2.052 | 2.373 | -15.650 | 79.236 | 8.923 | 46.297 |
| 120 | full | 200 | 2.818 | 3.209 | -13.855 | 86.581 | 9.750 | 60.032 |
| 120 | end15cm | 100 | 0.961 | 4.335 | -350.868 | 113.001 | 12.725 | 89.718 |
| 120 | end15cm | 75 | 1.008 | 5.460 | -441.616 | 133.866 | 15.075 | 89.652 |
| 120 | end15cm | 50 | 0.694 | 6.659 | -859.938 | 135.614 | 15.272 | 37.152 |
| 120 | end15cm | 30 | 0.730 | 5.502 | -653.268 | 51.342 | 5.782 | 58.887 |
| 120 | end5cm | 30 | 0.697 | 2.508 | -259.796 | 52.365 | 5.897 | 101.687 |
| 120 | end5cm | 20 | 1.236 | 3.307 | -167.545 | 60.861 | 6.854 | 62.642 |
| 120 | end5cm | 15 | 1.307 | 3.392 | -159.505 | 49.471 | 5.571 | 19.726 |
| 240 | full | 2000 | 0.210 | 0.221 | -5.204 | 2.497 | 0.281 | 1.433 |
| 240 | full | 1500 | 0.324 | 0.325 | -0.290 | 1.968 | 0.222 | 1.735 |
| 240 | full | 1000 | 0.475 | 0.517 | -8.707 | 8.084 | 0.910 | 2.880 |
| 240 | full | 800 | 0.717 | 0.656 | 8.456 | 7.110 | 0.801 | 0.515 |
| 240 | full | 600 | 0.818 | 0.825 | -0.895 | 12.508 | 1.409 | 9.674 |
| 240 | full | 400 | 1.165 | 1.370 | -17.564 | 61.651 | 6.943 | 36.203 |
| 240 | full | 300 | 2.038 | 2.395 | -17.527 | 79.691 | 8.974 | 28.962 |
| 240 | full | 200 | 2.443 | 2.820 | -15.425 | 80.291 | 9.042 | 50.736 |
| 240 | end15cm | 100 | 7.617 | 5.187 | 31.911 | 122.028 | 13.742 | 74.944 |
| 240 | end15cm | 75 | 9.137 | 6.241 | 31.696 | 137.896 | 15.529 | 66.073 |
| 240 | end15cm | 50 | 10.346 | 7.460 | 27.901 | 133.989 | 15.089 | 25.657 |
| 240 | end15cm | 30 | 7.381 | 6.030 | 18.315 | 41.948 | 4.724 | 115.624 |
| 240 | end5cm | 30 | 3.081 | 0.945 | 69.317 | 17.410 | 1.961 | 27.334 |
| 240 | end5cm | 20 | 3.456 | 1.377 | 60.145 | 23.473 | 2.643 | 22.568 |
| 240 | end5cm | 15 | 3.057 | 1.594 | 47.853 | 22.399 | 2.522 | 4.694 |

## Shared score evidence

- source: `./calibration_results/09B7-20261103T170330+0800-direct0-52cf8c/results.json`
- failures: `[]`
