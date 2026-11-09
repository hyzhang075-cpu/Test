# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | False | False | full regression at radius 400 is 0.244311 percentage points; full mean point error at radius 300 is 1.20777%; full regression at radius 300 is 0.306992 percentage points; full mean point error at radius 200 is 1.6114%; full regression at radius 200 is 0.416059 percentage points; tail improvement at radius 30 is -85.5177%; tail improvement at radius 20 is -70.1714%; tail improvement at radius 15 is -46.6819%; tip position at full/2000 is 1.61547%; tip position at full/1500 is 1.32199%; tip position at full/1000 is 2.11513%; tip position at full/800 is 3.28459%; tip position at full/600 is 3.51894%; tip tangent at full/600 is 10.0834 deg; tip position at full/400 is 5.58385%; tip tangent at full/400 is 25.0073 deg; tip position at full/300 is 6.84338%; tip tangent at full/300 is 32.9775 deg; tip position at full/200 is 8.00661%; tip tangent at full/200 is 41.0237 deg; tip position at end15cm/100 is 7.32832%; tip tangent at end15cm/100 is 54.7107 deg; tip position at end15cm/75 is 8.26497%; tip tangent at end15cm/75 is 54.4899 deg; tip position at end15cm/50 is 8.62147%; tip tangent at end15cm/50 is 40.3728 deg; tip position at end15cm/30 is 2.29138%; tip tangent at end15cm/30 is 14.7765 deg; tip position at end5cm/30 is 5.49895%; tip tangent at end5cm/30 is 75.4828 deg; tip position at end5cm/20 is 4.74575%; tip tangent at end5cm/20 is 31.0517 deg; tip position at end5cm/15 is 3.37138%; tip tangent at end5cm/15 is 34.8843 deg; boundary curvature angle jump is 57.476 deg; end15cm phase error is 30.5615 deg |
| 120 | False | True | True | False | full mean point error at radius 300 is 1.43924%; full regression at radius 300 is 0.300177 percentage points; full mean point error at radius 200 is 1.83504%; full regression at radius 200 is 0.410616 percentage points; tail improvement at radius 30 is 0.459994%; tip position at full/1500 is 1.14329%; tip position at full/1000 is 1.61951%; tip position at full/800 is 2.89898%; tip position at full/600 is 3.14912%; tip position at full/400 is 4.59633%; tip tangent at full/400 is 15.0743 deg; tip position at full/300 is 6.808%; tip tangent at full/300 is 27.6525 deg; tip position at full/200 is 7.09538%; tip tangent at full/200 is 27.5924 deg; tip position at end15cm/100 is 1.02878%; tip position at end15cm/75 is 1.55764%; tip position at end15cm/50 is 1.75099%; tip position at end15cm/30 is 2.94034%; tip position at end5cm/30 is 4.24378%; tip tangent at end5cm/30 is 48.4489 deg; tip position at end5cm/20 is 4.59363%; tip tangent at end5cm/20 is 35.8466 deg; tip position at end5cm/15 is 3.57436%; tip tangent at end5cm/15 is 41.9038 deg; boundary curvature angle jump is 34.5852 deg |
| 240 | False | True | False | False | full mean point error at radius 600 is 1.15879%; full regression at radius 600 is 0.227095 percentage points; full mean point error at radius 400 is 1.55348%; full regression at radius 400 is 0.358999 percentage points; full mean point error at radius 300 is 1.9615%; full regression at radius 300 is 0.443234 percentage points; full mean point error at radius 200 is 2.50625%; full regression at radius 200 is 0.651523 percentage points; tail improvement at radius 30 is -83.8968%; tail improvement at radius 20 is -83.4545%; tail improvement at radius 15 is -77.0866%; tip position at full/2000 is 1.80879%; tip position at full/1500 is 2.3235%; tip position at full/1000 is 3.26719%; tip tangent at full/1000 is 12.289 deg; tip position at full/800 is 4.72311%; tip tangent at full/800 is 16.2739 deg; tip position at full/600 is 5.57942%; tip tangent at full/600 is 23.2285 deg; tip position at full/400 is 7.92016%; tip tangent at full/400 is 24.2182 deg; tip position at full/300 is 9.6956%; tip tangent at full/300 is 37.0854 deg; tip position at full/200 is 10.9914%; tip tangent at full/200 is 49.4267 deg; tip position at end15cm/100 is 14.7197%; tip tangent at end15cm/100 is 97.5221 deg; tip position at end15cm/75 is 16.897%; tip tangent at end15cm/75 is 89.4876 deg; tip position at end15cm/50 is 15.6125%; tip tangent at end15cm/50 is 18.9752 deg; tip position at end15cm/30 is 3.47331%; tip tangent at end15cm/30 is 77.5398 deg; tip position at end5cm/30 is 7.20937%; tip tangent at end5cm/30 is 95.8533 deg; tip position at end5cm/20 is 6.51488%; tip tangent at end5cm/20 is 41.2495 deg; tip position at end5cm/15 is 4.43485%; tip tangent at end5cm/15 is 42.9243 deg; boundary curvature angle jump is 69.6488 deg; end15cm phase error is 50.845 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 30.561 | 30.000 | False | True |
| 0 | end5cm | 8.314 | 30.000 | True | False |
| 120 | end15cm | 15.833 | 30.000 | True | True |
| 120 | end5cm | 39.071 | 30.000 | False | False |
| 240 | end15cm | 50.845 | 30.000 | False | True |
| 240 | end5cm | 36.773 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.238 | 0.299 | -25.871 | 14.297 | 1.615 | 4.497 |
| 0 | full | 1500 | 0.176 | 0.242 | -37.477 | 11.700 | 1.322 | 4.483 |
| 0 | full | 1000 | 0.320 | 0.406 | -27.026 | 18.719 | 2.115 | 5.194 |
| 0 | full | 800 | 0.569 | 0.688 | -20.823 | 29.069 | 3.285 | 7.069 |
| 0 | full | 600 | 0.599 | 0.743 | -24.128 | 31.143 | 3.519 | 10.083 |
| 0 | full | 400 | 0.721 | 0.966 | -33.862 | 49.417 | 5.584 | 25.007 |
| 0 | full | 300 | 0.901 | 1.208 | -34.081 | 60.564 | 6.843 | 32.977 |
| 0 | full | 200 | 1.195 | 1.611 | -34.807 | 70.859 | 8.007 | 41.024 |
| 0 | end15cm | 100 | 1.040 | 2.401 | -130.945 | 64.856 | 7.328 | 54.711 |
| 0 | end15cm | 75 | 1.293 | 2.863 | -121.428 | 73.145 | 8.265 | 54.490 |
| 0 | end15cm | 50 | 1.629 | 3.400 | -108.656 | 76.300 | 8.621 | 40.373 |
| 0 | end15cm | 30 | 1.594 | 2.245 | -40.885 | 20.279 | 2.291 | 14.776 |
| 0 | end5cm | 30 | 1.506 | 2.794 | -85.518 | 48.666 | 5.499 | 75.483 |
| 0 | end5cm | 20 | 1.711 | 2.911 | -70.171 | 42.000 | 4.746 | 31.052 |
| 0 | end5cm | 15 | 1.957 | 2.871 | -46.682 | 29.837 | 3.371 | 34.884 |
| 120 | full | 2000 | 0.222 | 0.246 | -10.688 | 4.779 | 0.540 | 2.393 |
| 120 | full | 1500 | 0.286 | 0.318 | -11.313 | 10.118 | 1.143 | 1.417 |
| 120 | full | 1000 | 0.353 | 0.413 | -16.896 | 14.333 | 1.620 | 5.904 |
| 120 | full | 800 | 0.514 | 0.603 | -17.186 | 25.656 | 2.899 | 8.818 |
| 120 | full | 600 | 0.547 | 0.658 | -20.402 | 27.870 | 3.149 | 9.176 |
| 120 | full | 400 | 0.771 | 0.969 | -25.717 | 40.678 | 4.596 | 15.074 |
| 120 | full | 300 | 1.139 | 1.439 | -26.353 | 60.251 | 6.808 | 27.653 |
| 120 | full | 200 | 1.424 | 1.835 | -28.827 | 62.794 | 7.095 | 27.592 |
| 120 | end15cm | 100 | 2.437 | 0.505 | 79.286 | 9.105 | 1.029 | 8.936 |
| 120 | end15cm | 75 | 2.786 | 0.777 | 72.098 | 13.785 | 1.558 | 9.916 |
| 120 | end15cm | 50 | 2.702 | 1.210 | 55.217 | 15.496 | 1.751 | 4.771 |
| 120 | end15cm | 30 | 2.288 | 1.880 | 17.837 | 26.022 | 2.940 | 4.392 |
| 120 | end5cm | 30 | 2.497 | 2.486 | 0.460 | 37.557 | 4.244 | 48.449 |
| 120 | end5cm | 20 | 3.374 | 3.016 | 10.614 | 40.654 | 4.594 | 35.847 |
| 120 | end5cm | 15 | 3.412 | 3.002 | 12.008 | 31.633 | 3.574 | 41.904 |
| 240 | full | 2000 | 0.218 | 0.296 | -36.103 | 16.008 | 1.809 | 6.750 |
| 240 | full | 1500 | 0.319 | 0.414 | -29.999 | 20.563 | 2.323 | 8.166 |
| 240 | full | 1000 | 0.514 | 0.641 | -24.629 | 28.915 | 3.267 | 12.289 |
| 240 | full | 800 | 0.650 | 0.843 | -29.522 | 41.800 | 4.723 | 16.274 |
| 240 | full | 600 | 0.932 | 1.159 | -24.374 | 49.378 | 5.579 | 23.229 |
| 240 | full | 400 | 1.194 | 1.553 | -30.055 | 70.093 | 7.920 | 24.218 |
| 240 | full | 300 | 1.518 | 1.962 | -29.193 | 85.806 | 9.696 | 37.085 |
| 240 | full | 200 | 1.855 | 2.506 | -35.128 | 97.274 | 10.991 | 49.427 |
| 240 | end15cm | 100 | 0.434 | 5.246 | -1109.007 | 130.269 | 14.720 | 97.522 |
| 240 | end15cm | 75 | 0.630 | 6.409 | -917.940 | 149.539 | 16.897 | 89.488 |
| 240 | end15cm | 50 | 0.819 | 7.331 | -795.124 | 138.170 | 15.612 | 18.975 |
| 240 | end15cm | 30 | 1.248 | 5.037 | -303.495 | 30.739 | 3.473 | 77.540 |
| 240 | end5cm | 30 | 2.008 | 3.694 | -83.897 | 63.803 | 7.209 | 95.853 |
| 240 | end5cm | 20 | 2.115 | 3.881 | -83.455 | 57.657 | 6.515 | 41.250 |
| 240 | end5cm | 15 | 1.986 | 3.518 | -77.087 | 39.248 | 4.435 | 42.924 |

## Shared score evidence

- source: `./calibration_results/09B7-20261105T101412+0800-direct0-d42696/results.json`
- failures: `[]`
