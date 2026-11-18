# Multi-region full-geometry validation

- unified global phase: `1.1037380417553646`
- unified rot_ang: `8.0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | True | False | full mean point error at radius 2000 is 1.55511%; full mean point error at radius 1500 is 1.64386%; full mean point error at radius 1000 is 1.96114%; full mean point error at radius 800 is 2.65194%; full mean point error at radius 600 is 1.90473%; full mean point error at radius 400 is 3.58118%; full mean point error at radius 300 is 4.37291%; full mean point error at radius 200 is 5.86611%; tip position at full/2000 is 4.60729%; tip position at full/1500 is 4.73939%; tip position at full/1000 is 5.36327%; tip position at full/800 is 7.01235%; tip position at full/600 is 5.07715%; tip position at full/400 is 8.32155%; tip position at full/300 is 8.89025%; tip position at full/200 is 10.4941%; tip tangent at full/200 is 10.8573 deg; tip position at end15cm/100 is 1.73578%; tip position at end15cm/75 is 1.98665%; tip position at end15cm/50 is 1.6174%; tip tangent at end15cm/50 is 26.5514 deg; tip position at end15cm/30 is 3.31746%; tip tangent at end15cm/30 is 37.2408 deg; boundary curvature angle jump is 147.285 deg |
| 120 | False | True | True | False | full mean point error at radius 2000 is 2.05273%; full mean point error at radius 1500 is 1.66807%; full mean point error at radius 1000 is 2.14598%; full mean point error at radius 800 is 2.68121%; full mean point error at radius 600 is 1.65748%; full mean point error at radius 400 is 2.07649%; full mean point error at radius 300 is 3.39743%; full mean point error at radius 200 is 3.07368%; tip position at full/2000 is 5.71506%; tip position at full/1500 is 4.78145%; tip position at full/1000 is 5.70443%; tip position at full/800 is 7.77931%; tip tangent at full/800 is 12.3724 deg; tip position at full/600 is 4.82151%; tip position at full/400 is 5.11789%; tip tangent at full/400 is 17.4263 deg; tip position at full/300 is 8.65188%; tip tangent at full/300 is 21.5151 deg; tip position at full/200 is 6.19667%; tip tangent at full/200 is 26.2805 deg; tip position at end15cm/100 is 4.36799%; tip tangent at end15cm/100 is 13.5736 deg; tip position at end15cm/75 is 4.67215%; tip tangent at end15cm/75 is 23.6855 deg; tip position at end15cm/50 is 3.7799%; tip tangent at end15cm/50 is 28.5509 deg; tip position at end15cm/30 is 1.76855%; tip tangent at end15cm/30 is 22.0606 deg; tip tangent at end5cm/15 is 13.9704 deg; boundary curvature angle jump is 88.0022 deg |
| 240 | False | True | True | False | full mean point error at radius 2000 is 1.70708%; full mean point error at radius 1000 is 3.08698%; full mean point error at radius 800 is 5.89997%; full mean point error at radius 600 is 8.21382%; full mean point error at radius 400 is 8.47241%; full mean point error at radius 300 is 6.17058%; full mean point error at radius 200 is 5.57237%; tip position at full/2000 is 4.74259%; tip position at full/1500 is 1.00372%; tip position at full/1000 is 8.96168%; tip tangent at full/1000 is 13.8308 deg; tip position at full/800 is 16.8561%; tip tangent at full/800 is 22.5133 deg; tip position at full/600 is 25.0106%; tip tangent at full/600 is 36.0511 deg; tip position at full/400 is 22.3112%; tip tangent at full/400 is 25.0267 deg; tip position at full/300 is 16.6989%; tip tangent at full/300 is 30.5613 deg; tip position at full/200 is 12.2438%; tip tangent at full/200 is 38.1873 deg; tip position at end15cm/100 is 6.52552%; tip tangent at end15cm/100 is 29.8194 deg; tip position at end15cm/75 is 8.24242%; tip tangent at end15cm/75 is 46.0733 deg; tip position at end15cm/50 is 9.1448%; tip tangent at end15cm/50 is 105.844 deg; tip position at end15cm/30 is 10.789%; tip tangent at end15cm/30 is 99.1291 deg; tip position at end5cm/30 is 1.13669%; tip position at end5cm/20 is 1.00875%; tip tangent at end5cm/20 is 21.2343 deg; tip tangent at end5cm/15 is 47.2183 deg; boundary curvature angle jump is 141.489 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 0.616 | 30.000 | True | True |
| 0 | end5cm | 9.038 | 30.000 | True | False |
| 120 | end15cm | 13.783 | 30.000 | True | True |
| 120 | end5cm | 113.434 | 30.000 | False | False |
| 240 | end15cm | 10.529 | 30.000 | True | True |
| 240 | end5cm | 177.120 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 1.552 | 1.555 | -0.172 | 38.563 | 4.607 | 5.024 |
| 0 | full | 1500 | 1.638 | 1.644 | -0.378 | 39.669 | 4.739 | 5.160 |
| 0 | full | 1000 | 1.960 | 1.961 | -0.048 | 44.891 | 5.363 | 5.256 |
| 0 | full | 800 | 2.645 | 2.652 | -0.249 | 58.693 | 7.012 | 7.431 |
| 0 | full | 600 | 1.897 | 1.905 | -0.416 | 42.496 | 5.077 | 5.284 |
| 0 | full | 400 | 3.581 | 3.581 | 0.005 | 69.651 | 8.322 | 5.605 |
| 0 | full | 300 | 4.372 | 4.373 | -0.032 | 74.411 | 8.890 | 2.451 |
| 0 | full | 200 | 5.865 | 5.866 | -0.024 | 87.836 | 10.494 | 10.857 |
| 0 | end15cm | 100 | 0.830 | 0.891 | -7.313 | 14.528 | 1.736 | 1.700 |
| 0 | end15cm | 75 | 1.036 | 1.116 | -7.661 | 16.628 | 1.987 | 1.749 |
| 0 | end15cm | 50 | 1.591 | 1.322 | 16.913 | 13.538 | 1.617 | 26.551 |
| 0 | end15cm | 30 | 2.008 | 1.970 | 1.918 | 27.767 | 3.317 | 37.241 |
| 0 | end5cm | 30 | 0.725 | 0.383 | 47.122 | 5.417 | 0.647 | 1.729 |
| 0 | end5cm | 20 | 0.972 | 0.531 | 45.399 | 6.982 | 0.834 | 1.978 |
| 0 | end5cm | 15 | 1.065 | 0.457 | 57.131 | 4.652 | 0.556 | 8.451 |
| 120 | full | 2000 | 2.064 | 2.053 | 0.545 | 47.835 | 5.715 | 4.118 |
| 120 | full | 1500 | 1.686 | 1.668 | 1.078 | 40.021 | 4.781 | 3.229 |
| 120 | full | 1000 | 2.167 | 2.146 | 0.974 | 47.746 | 5.704 | 6.908 |
| 120 | full | 800 | 2.673 | 2.681 | -0.326 | 65.113 | 7.779 | 12.372 |
| 120 | full | 600 | 1.650 | 1.657 | -0.430 | 40.356 | 4.822 | 8.176 |
| 120 | full | 400 | 2.074 | 2.076 | -0.117 | 42.837 | 5.118 | 17.426 |
| 120 | full | 300 | 3.368 | 3.397 | -0.877 | 72.416 | 8.652 | 21.515 |
| 120 | full | 200 | 3.033 | 3.074 | -1.349 | 51.866 | 6.197 | 26.280 |
| 120 | end15cm | 100 | 3.312 | 2.365 | 28.597 | 36.560 | 4.368 | 13.574 |
| 120 | end15cm | 75 | 3.858 | 2.747 | 28.805 | 39.106 | 4.672 | 23.686 |
| 120 | end15cm | 50 | 3.283 | 2.823 | 14.019 | 31.638 | 3.780 | 28.551 |
| 120 | end15cm | 30 | 2.474 | 2.128 | 13.977 | 14.803 | 1.769 | 22.061 |
| 120 | end5cm | 30 | 2.805 | 0.572 | 79.620 | 6.500 | 0.777 | 0.650 |
| 120 | end5cm | 20 | 3.498 | 0.684 | 80.440 | 7.260 | 0.867 | 5.884 |
| 120 | end5cm | 15 | 4.004 | 0.691 | 82.737 | 7.576 | 0.905 | 13.970 |
| 240 | full | 2000 | 1.725 | 1.707 | 1.029 | 39.695 | 4.743 | 2.032 |
| 240 | full | 1500 | 0.268 | 0.274 | -2.437 | 8.401 | 1.004 | 4.126 |
| 240 | full | 1000 | 3.074 | 3.087 | -0.435 | 75.009 | 8.962 | 13.831 |
| 240 | full | 800 | 5.875 | 5.900 | -0.429 | 141.085 | 16.856 | 22.513 |
| 240 | full | 600 | 8.145 | 8.214 | -0.849 | 209.338 | 25.011 | 36.051 |
| 240 | full | 400 | 8.430 | 8.472 | -0.507 | 186.744 | 22.311 | 25.027 |
| 240 | full | 300 | 6.047 | 6.171 | -2.041 | 139.770 | 16.699 | 30.561 |
| 240 | full | 200 | 5.498 | 5.572 | -1.350 | 102.481 | 12.244 | 38.187 |
| 240 | end15cm | 100 | 5.113 | 3.138 | 38.635 | 54.619 | 6.526 | 29.819 |
| 240 | end15cm | 75 | 6.510 | 4.148 | 36.289 | 68.989 | 8.242 | 46.073 |
| 240 | end15cm | 50 | 7.990 | 4.766 | 40.353 | 76.542 | 9.145 | 105.844 |
| 240 | end15cm | 30 | 6.820 | 5.881 | 13.769 | 90.304 | 10.789 | 99.129 |
| 240 | end5cm | 30 | 2.730 | 0.692 | 74.661 | 9.514 | 1.137 | 3.551 |
| 240 | end5cm | 20 | 3.256 | 0.849 | 73.919 | 8.443 | 1.009 | 21.234 |
| 240 | end5cm | 15 | 3.159 | 1.117 | 64.649 | 8.258 | 0.987 | 47.218 |

## Shared score evidence

- source: `./calibration_results/09B8-20261110T152748+0800-direct0-a556de/results.json`
- failures: `[]`
