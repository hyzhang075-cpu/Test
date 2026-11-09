# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | False | False | full regression at radius 800 is 0.203455 percentage points; full regression at radius 600 is 0.234962 percentage points; full regression at radius 400 is 0.38361 percentage points; full mean point error at radius 300 is 1.10732%; full regression at radius 300 is 0.512587 percentage points; full mean point error at radius 200 is 1.43267%; full regression at radius 200 is 0.738089 percentage points; tail improvement at radius 30 is -138.91%; tail improvement at radius 20 is -139.096%; tail improvement at radius 15 is -129.439%; tip position at full/2000 is 1.97476%; tip position at full/1500 is 2.11615%; tip position at full/1000 is 2.84436%; tip tangent at full/1000 is 12.383 deg; tip position at full/800 is 4.2233%; tip tangent at full/800 is 17.261 deg; tip position at full/600 is 5.0703%; tip tangent at full/600 is 23.8125 deg; tip position at full/400 is 7.47476%; tip tangent at full/400 is 33.4891 deg; tip position at full/300 is 9.975%; tip tangent at full/300 is 54.3324 deg; tip position at full/200 is 13.0947%; tip tangent at full/200 is 74.2999 deg; tip position at end15cm/100 is 17.963%; tip tangent at end15cm/100 is 134.158 deg; tip position at end15cm/75 is 20.7562%; tip tangent at end15cm/75 is 120.635 deg; tip position at end15cm/50 is 18.8219%; tip tangent at end15cm/50 is 20.5295 deg; tip position at end15cm/30 is 5.12991%; tip tangent at end15cm/30 is 106.098 deg; tip position at end5cm/30 is 8.54309%; tip tangent at end5cm/30 is 141.164 deg; tip position at end5cm/20 is 8.52014%; tip tangent at end5cm/20 is 48.2904 deg; tip position at end5cm/15 is 6.17629%; tip tangent at end5cm/15 is 49.0569 deg; boundary curvature angle jump is 120.048 deg; end15cm phase error is 32.9749 deg |
| 120 | False | True | False | False | full mean point error at radius 400 is 1.18171%; full regression at radius 300 is 0.271063 percentage points; full mean point error at radius 200 is 1.79074%; full regression at radius 200 is 0.864968 percentage points; tip position at full/400 is 7.99911%; tip tangent at full/400 is 50.9471 deg; tip position at full/300 is 6.94181%; tip tangent at full/300 is 33.8155 deg; tip position at full/200 is 14.7244%; tip tangent at full/200 is 83.3278 deg; tip position at end15cm/100 is 6.68324%; tip tangent at end15cm/100 is 35.0191 deg; tip position at end15cm/75 is 6.75608%; tip tangent at end15cm/75 is 22.9318 deg; tip position at end15cm/50 is 6.67371%; tip position at end15cm/30 is 3.15472%; tip tangent at end15cm/30 is 40.2703 deg; tip position at end5cm/30 is 5.25726%; tip tangent at end5cm/30 is 64.9426 deg; tip position at end5cm/20 is 5.08947%; tip tangent at end5cm/20 is 33.151 deg; tip position at end5cm/15 is 3.60408%; tip tangent at end5cm/15 is 51.3645 deg; boundary curvature angle jump is 73.8398 deg; end15cm phase error is 104.951 deg |
| 240 | False | True | False | False | full mean point error at radius 400 is 1.35814%; full regression at radius 400 is 0.39805 percentage points; full mean point error at radius 300 is 2.04427%; full regression at radius 300 is 0.552396 percentage points; full mean point error at radius 200 is 2.28467%; full regression at radius 200 is 0.698308 percentage points; tail improvement at radius 30 is -9.56352%; tail improvement at radius 20 is -1.85875%; tail improvement at radius 15 is 1.1883%; tip position at full/1000 is 1.08949%; tip position at full/800 is 1.15441%; tip position at full/400 is 9.49117%; tip tangent at full/400 is 46.0277 deg; tip position at full/300 is 10.9326%; tip tangent at full/300 is 41.6813 deg; tip position at full/200 is 13.1604%; tip tangent at full/200 is 71.4503 deg; tip position at end15cm/100 is 12.1667%; tip tangent at end15cm/100 is 65.4219 deg; tip position at end15cm/75 is 15.015%; tip tangent at end15cm/75 is 63.1782 deg; tip position at end15cm/50 is 14.7416%; tip tangent at end15cm/50 is 23.2203 deg; tip position at end15cm/30 is 4.07271%; tip tangent at end15cm/30 is 104.173 deg; tip position at end5cm/30 is 2.52498%; tip tangent at end5cm/30 is 22.2768 deg; tip position at end5cm/20 is 2.63012%; tip tangent at end5cm/20 is 23.2975 deg; tip position at end5cm/15 is 2.28298%; tip tangent at end5cm/15 is 28.8502 deg; boundary curvature angle jump is 83.5558 deg; end15cm phase error is 137.736 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 32.975 | 30.000 | False | True |
| 0 | end5cm | 9.908 | 30.000 | True | False |
| 120 | end15cm | 104.951 | 30.000 | False | True |
| 120 | end5cm | 29.732 | 30.000 | True | False |
| 240 | end15cm | 137.736 | 30.000 | False | True |
| 240 | end5cm | 9.370 | 30.000 | True | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.119 | 0.212 | -78.589 | 17.477 | 1.975 | 8.331 |
| 0 | full | 1500 | 0.139 | 0.236 | -69.695 | 18.728 | 2.116 | 9.316 |
| 0 | full | 1000 | 0.219 | 0.356 | -62.311 | 25.173 | 2.844 | 12.383 |
| 0 | full | 800 | 0.283 | 0.486 | -71.914 | 37.376 | 4.223 | 17.261 |
| 0 | full | 600 | 0.504 | 0.739 | -46.653 | 44.872 | 5.070 | 23.812 |
| 0 | full | 400 | 0.447 | 0.831 | -85.770 | 66.152 | 7.475 | 33.489 |
| 0 | full | 300 | 0.595 | 1.107 | -86.188 | 88.279 | 9.975 | 54.332 |
| 0 | full | 200 | 0.695 | 1.433 | -106.264 | 115.888 | 13.095 | 74.300 |
| 0 | end15cm | 100 | 0.805 | 6.326 | -686.259 | 158.973 | 17.963 | 134.158 |
| 0 | end15cm | 75 | 0.922 | 7.817 | -747.597 | 183.692 | 20.756 | 120.635 |
| 0 | end15cm | 50 | 1.082 | 8.796 | -712.790 | 166.574 | 18.822 | 20.529 |
| 0 | end15cm | 30 | 1.458 | 6.728 | -361.388 | 45.400 | 5.130 | 106.098 |
| 0 | end5cm | 30 | 1.727 | 4.126 | -138.910 | 75.606 | 8.543 | 141.164 |
| 0 | end5cm | 20 | 2.024 | 4.839 | -139.096 | 75.403 | 8.520 | 48.290 |
| 0 | end5cm | 15 | 2.020 | 4.635 | -129.439 | 54.660 | 6.176 | 49.057 |
| 120 | full | 2000 | 0.156 | 0.168 | -7.086 | 2.856 | 0.323 | 0.723 |
| 120 | full | 1500 | 0.096 | 0.101 | -5.998 | 1.876 | 0.212 | 0.759 |
| 120 | full | 1000 | 0.218 | 0.229 | -5.175 | 2.810 | 0.317 | 2.296 |
| 120 | full | 800 | 0.330 | 0.336 | -1.929 | 6.098 | 0.689 | 5.193 |
| 120 | full | 600 | 0.142 | 0.164 | -15.244 | 8.614 | 0.973 | 9.411 |
| 120 | full | 400 | 0.982 | 1.182 | -20.348 | 70.792 | 7.999 | 50.947 |
| 120 | full | 300 | 0.704 | 0.975 | -38.489 | 61.435 | 6.942 | 33.816 |
| 120 | full | 200 | 0.926 | 1.791 | -93.432 | 130.311 | 14.724 | 83.328 |
| 120 | end15cm | 100 | 6.727 | 2.529 | 62.410 | 59.147 | 6.683 | 35.019 |
| 120 | end15cm | 75 | 8.196 | 2.813 | 65.683 | 59.791 | 6.756 | 22.932 |
| 120 | end15cm | 50 | 9.656 | 3.420 | 64.582 | 59.062 | 6.674 | 6.115 |
| 120 | end15cm | 30 | 7.628 | 2.998 | 60.693 | 27.919 | 3.155 | 40.270 |
| 120 | end5cm | 30 | 3.315 | 2.765 | 16.581 | 46.527 | 5.257 | 64.943 |
| 120 | end5cm | 20 | 4.111 | 3.165 | 23.006 | 45.042 | 5.089 | 33.151 |
| 120 | end5cm | 15 | 4.058 | 3.033 | 25.264 | 31.896 | 3.604 | 51.365 |
| 240 | full | 2000 | 0.145 | 0.152 | -4.993 | 2.757 | 0.312 | 0.189 |
| 240 | full | 1500 | 0.196 | 0.210 | -7.191 | 5.019 | 0.567 | 0.892 |
| 240 | full | 1000 | 0.381 | 0.405 | -6.140 | 9.642 | 1.089 | 2.487 |
| 240 | full | 800 | 0.337 | 0.339 | -0.623 | 10.216 | 1.154 | 4.680 |
| 240 | full | 600 | 0.834 | 0.828 | 0.708 | 6.462 | 0.730 | 4.860 |
| 240 | full | 400 | 0.960 | 1.358 | -41.460 | 83.997 | 9.491 | 46.028 |
| 240 | full | 300 | 1.492 | 2.044 | -37.027 | 96.753 | 10.933 | 41.681 |
| 240 | full | 200 | 1.586 | 2.285 | -44.020 | 116.469 | 13.160 | 71.450 |
| 240 | end15cm | 100 | 7.467 | 4.582 | 38.646 | 107.676 | 12.167 | 65.422 |
| 240 | end15cm | 75 | 8.954 | 5.998 | 33.012 | 132.883 | 15.015 | 63.178 |
| 240 | end15cm | 50 | 9.972 | 7.319 | 26.600 | 130.463 | 14.742 | 23.220 |
| 240 | end15cm | 30 | 7.120 | 5.660 | 20.503 | 36.043 | 4.073 | 104.173 |
| 240 | end5cm | 30 | 1.435 | 1.572 | -9.564 | 22.346 | 2.525 | 22.277 |
| 240 | end5cm | 20 | 1.881 | 1.916 | -1.859 | 23.277 | 2.630 | 23.298 |
| 240 | end5cm | 15 | 2.076 | 2.052 | 1.188 | 20.204 | 2.283 | 28.850 |

## Shared score evidence

- source: `./calibration_results/09B7-20261023T184012+0800-direct0-d01d33/results.json`
- failures: `[]`
