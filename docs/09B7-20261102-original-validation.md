# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `-31.4`
- shared score thresholds verified: `False`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | False | False | False | shared score thresholds are not verified; optimization stages are not usable; tail improvement at radius 15 is -4.5541%; tip position at full/1000 is 1.07758%; tip tangent at full/1000 is 11.2191 deg; tip position at full/800 is 1.64876%; tip tangent at full/800 is 14.0932 deg; tip position at full/600 is 1.35551%; tip tangent at full/600 is 11.9016 deg; tip position at end15cm/100 is 1.35726%; tip position at end15cm/75 is 1.68527%; tip tangent at end15cm/75 is 12.295 deg; tip position at end15cm/50 is 2.01988%; tip tangent at end15cm/50 is 29.5525 deg; tip position at end15cm/30 is 1.63024%; tip position at end5cm/30 is 1.48577%; tip tangent at end5cm/30 is 18.1451 deg; tip tangent at end5cm/20 is 128.563 deg; tip position at end5cm/15 is 1.07415%; tip tangent at end5cm/15 is 110.709 deg; boundary curvature angle jump is 171.168 deg; end15cm phase error is 177.283 deg |
| 120 | False | False | False | False | shared score thresholds are not verified; optimization stages are not usable; full mean point error at radius 400 is 1.00102%; full mean point error at radius 200 is 1.23059%; tip position at full/800 is 1.10401%; tip position at full/400 is 2.58484%; tip tangent at full/400 is 18.089 deg; tip position at full/300 is 2.04717%; tip tangent at full/300 is 13.0577 deg; tip position at full/200 is 4.43583%; tip tangent at full/200 is 26.2449 deg; tip position at end15cm/100 is 1.74487%; tip tangent at end15cm/100 is 14.7826 deg; tip position at end15cm/75 is 1.73558%; tip tangent at end15cm/75 is 14.9172 deg; tip position at end15cm/50 is 2.26744%; tip tangent at end15cm/50 is 25.9012 deg; tip position at end15cm/30 is 1.80904%; tip tangent at end15cm/30 is 18.3275 deg; tip position at end5cm/20 is 1.20785%; tip tangent at end5cm/20 is 11.9468 deg; tip tangent at end5cm/15 is 49.3534 deg; boundary curvature angle jump is 68.3422 deg; end15cm phase error is 84.9114 deg |
| 240 | False | False | False | False | shared score thresholds are not verified; optimization stages are not usable; full mean point error at radius 200 is 1.24169%; tip position at full/300 is 1.1407%; tip position at full/200 is 1.09108%; tip position at end15cm/100 is 1.79485%; tip position at end15cm/75 is 2.39509%; tip tangent at end15cm/75 is 14.4367 deg; tip position at end15cm/50 is 2.06344%; tip tangent at end15cm/50 is 22.7915 deg; tip position at end15cm/30 is 1.53192%; tip tangent at end15cm/30 is 34.4595 deg; tip position at end5cm/30 is 1.03743%; tip position at end5cm/20 is 1.06506%; tip tangent at end5cm/20 is 13.3306 deg; boundary curvature angle jump is 85.4582 deg; end15cm phase error is 150.611 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 177.283 | 30.000 | False | True |
| 0 | end5cm | 162.705 | 30.000 | False | False |
| 120 | end15cm | 84.911 | 30.000 | False | True |
| 120 | end5cm | 129.440 | 30.000 | False | False |
| 240 | end15cm | 150.611 | 30.000 | False | True |
| 240 | end5cm | 164.208 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.177 | 0.174 | 1.439 | 6.100 | 0.690 | 5.918 |
| 0 | full | 1500 | 0.425 | 0.373 | 12.150 | 7.899 | 0.893 | 7.711 |
| 0 | full | 1000 | 0.649 | 0.539 | 16.919 | 9.533 | 1.078 | 11.219 |
| 0 | full | 800 | 0.384 | 0.387 | -0.765 | 14.587 | 1.649 | 14.093 |
| 0 | full | 600 | 0.834 | 0.756 | 9.340 | 11.992 | 1.356 | 11.902 |
| 0 | full | 400 | 0.231 | 0.242 | -5.185 | 5.064 | 0.572 | 1.572 |
| 0 | full | 300 | 0.369 | 0.405 | -9.727 | 7.101 | 0.803 | 1.478 |
| 0 | full | 200 | 0.462 | 0.418 | 9.652 | 3.321 | 0.375 | 4.129 |
| 0 | end15cm | 100 | 1.121 | 0.581 | 48.143 | 12.008 | 1.357 | 9.617 |
| 0 | end15cm | 75 | 1.261 | 0.745 | 40.918 | 14.910 | 1.685 | 12.295 |
| 0 | end15cm | 50 | 1.494 | 1.551 | -3.837 | 17.870 | 2.020 | 29.552 |
| 0 | end15cm | 30 | 1.741 | 1.157 | 33.519 | 14.423 | 1.630 | 5.112 |
| 0 | end5cm | 30 | 1.320 | 0.936 | 29.072 | 13.145 | 1.486 | 18.145 |
| 0 | end5cm | 20 | 1.538 | 1.200 | 22.027 | 7.973 | 0.901 | 128.563 |
| 0 | end5cm | 15 | 1.841 | 1.925 | -4.554 | 9.503 | 1.074 | 110.709 |
| 120 | full | 2000 | 0.168 | 0.162 | 3.389 | 1.527 | 0.173 | 1.263 |
| 120 | full | 1500 | 0.117 | 0.120 | -2.707 | 1.368 | 0.155 | 1.618 |
| 120 | full | 1000 | 0.358 | 0.339 | 5.396 | 5.765 | 0.652 | 4.188 |
| 120 | full | 800 | 0.217 | 0.259 | -19.282 | 9.767 | 1.104 | 6.981 |
| 120 | full | 600 | 0.317 | 0.267 | 16.017 | 7.979 | 0.902 | 0.845 |
| 120 | full | 400 | 0.980 | 1.001 | -2.193 | 22.868 | 2.585 | 18.089 |
| 120 | full | 300 | 0.795 | 0.810 | -1.854 | 18.111 | 2.047 | 13.058 |
| 120 | full | 200 | 1.083 | 1.231 | -13.679 | 39.244 | 4.436 | 26.245 |
| 120 | end15cm | 100 | 5.247 | 0.746 | 85.783 | 15.437 | 1.745 | 14.783 |
| 120 | end15cm | 75 | 6.300 | 0.840 | 86.670 | 15.355 | 1.736 | 14.917 |
| 120 | end15cm | 50 | 7.052 | 1.058 | 84.992 | 20.060 | 2.267 | 25.901 |
| 120 | end15cm | 30 | 5.746 | 1.383 | 75.936 | 16.005 | 1.809 | 18.328 |
| 120 | end5cm | 30 | 3.397 | 0.605 | 82.192 | 7.525 | 0.851 | 9.353 |
| 120 | end5cm | 20 | 4.501 | 0.996 | 77.862 | 10.686 | 1.208 | 11.947 |
| 120 | end5cm | 15 | 4.572 | 1.147 | 74.922 | 5.525 | 0.624 | 49.353 |
| 240 | full | 2000 | 0.162 | 0.136 | 16.247 | 0.937 | 0.106 | 1.261 |
| 240 | full | 1500 | 0.199 | 0.210 | -5.473 | 4.420 | 0.500 | 2.707 |
| 240 | full | 1000 | 0.441 | 0.429 | 2.621 | 6.164 | 0.697 | 3.191 |
| 240 | full | 800 | 0.348 | 0.351 | -0.832 | 8.781 | 0.993 | 3.064 |
| 240 | full | 600 | 0.831 | 0.786 | 5.465 | 7.093 | 0.802 | 2.734 |
| 240 | full | 400 | 0.697 | 0.665 | 4.574 | 8.114 | 0.917 | 6.781 |
| 240 | full | 300 | 0.740 | 0.747 | -0.890 | 10.092 | 1.141 | 9.880 |
| 240 | full | 200 | 1.224 | 1.242 | -1.475 | 9.653 | 1.091 | 9.444 |
| 240 | end15cm | 100 | 2.423 | 0.824 | 65.997 | 15.879 | 1.795 | 4.313 |
| 240 | end15cm | 75 | 2.912 | 1.109 | 61.900 | 21.189 | 2.395 | 14.437 |
| 240 | end15cm | 50 | 3.556 | 1.008 | 71.652 | 18.255 | 2.063 | 22.792 |
| 240 | end15cm | 30 | 3.084 | 1.118 | 63.740 | 13.553 | 1.532 | 34.459 |
| 240 | end5cm | 30 | 1.461 | 0.719 | 50.802 | 9.178 | 1.037 | 9.953 |
| 240 | end5cm | 20 | 1.850 | 0.843 | 54.424 | 9.423 | 1.065 | 13.331 |
| 240 | end5cm | 15 | 2.111 | 0.864 | 59.062 | 7.139 | 0.807 | 4.110 |

## Shared score evidence

- source: `./calibration_results/09B7-20261029T172512+0800-direct240-716937/results.json`
- failures: `["score 缺少区域 end15cm", "score 缺少区域 end5cm"]`
