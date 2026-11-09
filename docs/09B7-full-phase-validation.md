# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `0.0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | True | False | tail improvement at radius 30 is -79.3219%; tail improvement at radius 20 is -79.3527%; tail improvement at radius 15 is -73.6046%; tip position at full/1000 is 1.25065%; tip position at full/800 is 1.91886%; tip position at full/600 is 2.39852%; tip tangent at full/600 is 10.7712 deg; tip position at full/400 is 3.37809%; tip tangent at full/400 is 15.0547 deg; tip position at full/300 is 4.58126%; tip tangent at full/300 is 24.744 deg; tip position at full/200 is 5.54912%; tip tangent at full/200 is 33.0398 deg; tip position at end15cm/100 is 7.20194%; tip tangent at end15cm/100 is 63.9275 deg; tip position at end15cm/75 is 8.57701%; tip tangent at end15cm/75 is 72.1825 deg; tip position at end15cm/50 is 9.14667%; tip tangent at end15cm/50 is 53.1554 deg; tip position at end15cm/30 is 6.55318%; tip position at end5cm/30 is 6.15998%; tip tangent at end5cm/30 is 83.938 deg; tip position at end5cm/20 is 6.15232%; tip tangent at end5cm/20 is 38.6319 deg; tip position at end5cm/15 is 4.55946%; tip tangent at end5cm/15 is 34.9039 deg; boundary curvature angle jump is 62.3209 deg |
| 120 | False | True | False | False | full mean point error at radius 400 is 1.24875%; full regression at radius 400 is 0.266836 percentage points; full mean point error at radius 200 is 1.69128%; full regression at radius 200 is 0.765513 percentage points; tip position at full/800 is 1.04196%; tip position at full/600 is 1.91125%; tip tangent at full/600 is 11.7519 deg; tip position at full/400 is 8.85504%; tip tangent at full/400 is 54.4708 deg; tip position at full/300 is 5.33013%; tip tangent at full/300 is 25.5133 deg; tip position at full/200 is 12.9201%; tip tangent at full/200 is 65.1091 deg; tip position at end15cm/100 is 13.2502%; tip tangent at end15cm/100 is 83.4299 deg; tip position at end15cm/75 is 14.4635%; tip tangent at end15cm/75 is 68.8661 deg; tip position at end15cm/50 is 13.877%; tip tangent at end15cm/50 is 15.2549 deg; tip position at end15cm/30 is 4.67169%; tip tangent at end15cm/30 is 71.6169 deg; tip position at end5cm/30 is 3.31514%; tip tangent at end5cm/30 is 33.8973 deg; tip position at end5cm/20 is 3.58691%; tip tangent at end5cm/20 is 26.022 deg; tip position at end5cm/15 is 2.64634%; tip tangent at end5cm/15 is 44.8325 deg; boundary curvature angle jump is 33.0459 deg; end15cm phase error is 91.5065 deg |
| 240 | False | True | False | False | full mean point error at radius 400 is 1.28675%; full regression at radius 400 is 0.326666 percentage points; full mean point error at radius 300 is 1.92338%; full regression at radius 300 is 0.431504 percentage points; full mean point error at radius 200 is 2.1227%; full regression at radius 200 is 0.536342 percentage points; tail improvement at radius 30 is -4.58323%; tail improvement at radius 20 is -4.72677%; tail improvement at radius 15 is -1.87679%; tip position at full/600 is 1.46171%; tip tangent at full/600 is 12.7483 deg; tip position at full/400 is 8.49075%; tip tangent at full/400 is 39.3784 deg; tip position at full/300 is 9.16049%; tip tangent at full/300 is 29.9528 deg; tip position at full/200 is 10.7357%; tip tangent at full/200 is 53.1143 deg; tip position at end15cm/100 is 16.4406%; tip tangent at end15cm/100 is 104.151 deg; tip position at end15cm/75 is 19.6608%; tip tangent at end15cm/75 is 98.7295 deg; tip position at end15cm/50 is 19.7906%; tip tangent at end15cm/50 is 23.757 deg; tip position at end15cm/30 is 5.67319%; tip tangent at end15cm/30 is 135.827 deg; tip position at end5cm/30 is 2.27511%; tip tangent at end5cm/30 is 15.8436 deg; tip position at end5cm/20 is 2.68491%; tip tangent at end5cm/20 is 19.7392 deg; tip position at end5cm/15 is 2.30756%; tip tangent at end5cm/15 is 27.8451 deg; boundary curvature angle jump is 95.3234 deg; end15cm phase error is 115.892 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 1.892 | 30.000 | True | True |
| 0 | end5cm | 5.977 | 30.000 | True | False |
| 120 | end15cm | 91.507 | 30.000 | False | True |
| 120 | end5cm | 4.507 | 30.000 | True | False |
| 240 | end15cm | 115.892 | 30.000 | False | True |
| 240 | end5cm | 19.592 | 30.000 | True | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.119 | 0.134 | -13.096 | 8.418 | 0.951 | 3.899 |
| 0 | full | 1500 | 0.139 | 0.149 | -6.873 | 8.364 | 0.945 | 4.108 |
| 0 | full | 1000 | 0.219 | 0.233 | -6.316 | 11.068 | 1.251 | 5.641 |
| 0 | full | 800 | 0.283 | 0.305 | -7.964 | 16.982 | 1.919 | 7.819 |
| 0 | full | 600 | 0.504 | 0.545 | -8.224 | 21.227 | 2.399 | 10.771 |
| 0 | full | 400 | 0.447 | 0.516 | -15.346 | 29.896 | 3.378 | 15.055 |
| 0 | full | 300 | 0.595 | 0.714 | -20.095 | 40.544 | 4.581 | 24.744 |
| 0 | full | 200 | 0.695 | 0.872 | -25.532 | 49.110 | 5.549 | 33.040 |
| 0 | end15cm | 100 | 0.805 | 2.100 | -160.950 | 63.737 | 7.202 | 63.927 |
| 0 | end15cm | 75 | 0.922 | 2.585 | -180.259 | 75.907 | 8.577 | 72.182 |
| 0 | end15cm | 50 | 1.082 | 3.162 | -192.222 | 80.948 | 9.147 | 53.155 |
| 0 | end15cm | 30 | 1.458 | 3.072 | -110.658 | 57.996 | 6.553 | 8.217 |
| 0 | end5cm | 30 | 1.727 | 3.097 | -79.322 | 54.516 | 6.160 | 83.938 |
| 0 | end5cm | 20 | 2.024 | 3.630 | -79.353 | 54.448 | 6.152 | 38.632 |
| 0 | end5cm | 15 | 2.020 | 3.507 | -73.605 | 40.351 | 4.559 | 34.904 |
| 120 | full | 2000 | 0.156 | 0.172 | -9.697 | 3.150 | 0.356 | 1.029 |
| 120 | full | 1500 | 0.096 | 0.113 | -18.139 | 3.733 | 0.422 | 2.127 |
| 120 | full | 1000 | 0.218 | 0.223 | -2.093 | 5.300 | 0.599 | 4.135 |
| 120 | full | 800 | 0.330 | 0.343 | -3.955 | 9.221 | 1.042 | 6.893 |
| 120 | full | 600 | 0.142 | 0.237 | -66.581 | 16.915 | 1.911 | 11.752 |
| 120 | full | 400 | 0.982 | 1.249 | -27.175 | 78.367 | 8.855 | 54.471 |
| 120 | full | 300 | 0.704 | 0.866 | -22.919 | 47.172 | 5.330 | 25.513 |
| 120 | full | 200 | 0.926 | 1.691 | -82.689 | 114.343 | 12.920 | 65.109 |
| 120 | end15cm | 100 | 6.727 | 4.704 | 30.070 | 117.264 | 13.250 | 83.430 |
| 120 | end15cm | 75 | 8.196 | 5.513 | 32.736 | 128.002 | 14.463 | 68.866 |
| 120 | end15cm | 50 | 9.656 | 6.412 | 33.600 | 122.812 | 13.877 | 15.255 |
| 120 | end15cm | 30 | 7.628 | 5.028 | 34.088 | 41.344 | 4.672 | 71.617 |
| 120 | end5cm | 30 | 3.315 | 2.016 | 39.185 | 29.339 | 3.315 | 33.897 |
| 120 | end5cm | 20 | 4.111 | 2.470 | 39.905 | 31.744 | 3.587 | 26.022 |
| 120 | end5cm | 15 | 4.058 | 2.434 | 40.011 | 23.420 | 2.646 | 44.832 |
| 240 | full | 2000 | 0.145 | 0.129 | 10.941 | 0.461 | 0.052 | 0.913 |
| 240 | full | 1500 | 0.196 | 0.175 | 10.679 | 1.163 | 0.131 | 1.145 |
| 240 | full | 1000 | 0.381 | 0.354 | 7.086 | 3.737 | 0.422 | 1.522 |
| 240 | full | 800 | 0.337 | 0.323 | 4.218 | 7.748 | 0.876 | 2.853 |
| 240 | full | 600 | 0.834 | 0.821 | 1.646 | 12.936 | 1.462 | 12.748 |
| 240 | full | 400 | 0.960 | 1.287 | -34.025 | 75.143 | 8.491 | 39.378 |
| 240 | full | 300 | 1.492 | 1.923 | -28.924 | 81.070 | 9.160 | 29.953 |
| 240 | full | 200 | 1.586 | 2.123 | -33.810 | 95.011 | 10.736 | 53.114 |
| 240 | end15cm | 100 | 7.467 | 5.986 | 19.835 | 145.499 | 16.441 | 104.151 |
| 240 | end15cm | 75 | 8.954 | 7.600 | 15.118 | 173.998 | 19.661 | 98.730 |
| 240 | end15cm | 50 | 9.972 | 9.308 | 6.653 | 175.147 | 19.791 | 23.757 |
| 240 | end15cm | 30 | 7.120 | 7.366 | -3.466 | 50.208 | 5.673 | 135.827 |
| 240 | end5cm | 30 | 1.435 | 1.500 | -4.583 | 20.135 | 2.275 | 15.844 |
| 240 | end5cm | 20 | 1.881 | 1.970 | -4.727 | 23.761 | 2.685 | 19.739 |
| 240 | end5cm | 15 | 2.076 | 2.115 | -1.877 | 20.422 | 2.308 | 27.845 |

## Shared score evidence

- source: `./calibration_results/09B7-20261023T184012+0800-direct0-d01d33/results.json`
- failures: `[]`
