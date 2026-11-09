# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | False | False | full regression at radius 800 is 0.202586 percentage points; full regression at radius 600 is 0.235807 percentage points; full regression at radius 400 is 0.383998 percentage points; full mean point error at radius 300 is 1.10682%; full regression at radius 300 is 0.512093 percentage points; full mean point error at radius 200 is 1.43301%; full regression at radius 200 is 0.738426 percentage points; tail improvement at radius 30 is -138.92%; tail improvement at radius 20 is -139.101%; tail improvement at radius 15 is -129.441%; tip position at full/2000 is 1.98306%; tip position at full/1500 is 2.15892%; tip position at full/1000 is 2.85453%; tip tangent at full/1000 is 12.4354 deg; tip position at full/800 is 4.20888%; tip tangent at full/800 is 17.1832 deg; tip position at full/600 is 5.07994%; tip tangent at full/600 is 23.8408 deg; tip position at full/400 is 7.48144%; tip tangent at full/400 is 33.5272 deg; tip position at full/300 is 9.96714%; tip tangent at full/300 is 54.2907 deg; tip position at full/200 is 13.1002%; tip tangent at full/200 is 74.3316 deg; tip position at end15cm/100 is 17.9631%; tip tangent at end15cm/100 is 134.158 deg; tip position at end15cm/75 is 20.7562%; tip tangent at end15cm/75 is 120.635 deg; tip position at end15cm/50 is 18.8219%; tip tangent at end15cm/50 is 20.5292 deg; tip position at end15cm/30 is 5.1299%; tip tangent at end15cm/30 is 106.098 deg; tip position at end5cm/30 is 8.54329%; tip tangent at end5cm/30 is 141.163 deg; tip position at end5cm/20 is 8.52025%; tip tangent at end5cm/20 is 48.2893 deg; tip position at end5cm/15 is 6.17636%; tip tangent at end5cm/15 is 49.0575 deg; boundary curvature angle jump is 120.048 deg; end15cm phase error is 32.9749 deg |
| 120 | False | True | False | False | full mean point error at radius 400 is 1.18166%; full regression at radius 300 is 0.26807 percentage points; full mean point error at radius 200 is 1.7908%; full regression at radius 200 is 0.865028 percentage points; tip position at full/400 is 7.99308%; tip tangent at full/400 is 50.9249 deg; tip position at full/300 is 6.89366%; tip tangent at full/300 is 33.5633 deg; tip position at full/200 is 14.7292%; tip tangent at full/200 is 83.38 deg; tip position at end15cm/100 is 6.68264%; tip tangent at end15cm/100 is 35.0188 deg; tip position at end15cm/75 is 6.75575%; tip tangent at end15cm/75 is 22.9361 deg; tip position at end15cm/50 is 6.67397%; tip position at end15cm/30 is 3.15491%; tip tangent at end15cm/30 is 40.2709 deg; tip position at end5cm/30 is 5.25727%; tip tangent at end5cm/30 is 64.9421 deg; tip position at end5cm/20 is 5.08948%; tip tangent at end5cm/20 is 33.1499 deg; tip position at end5cm/15 is 3.60412%; tip tangent at end5cm/15 is 51.3638 deg; boundary curvature angle jump is 73.8398 deg; end15cm phase error is 104.951 deg |
| 240 | False | True | False | False | full mean point error at radius 400 is 1.36085%; full regression at radius 400 is 0.40076 percentage points; full mean point error at radius 300 is 2.04401%; full regression at radius 300 is 0.552132 percentage points; full mean point error at radius 200 is 2.28524%; full regression at radius 200 is 0.698883 percentage points; tail improvement at radius 30 is -9.58887%; tail improvement at radius 20 is -1.87941%; tail improvement at radius 15 is 1.17324%; tip position at full/1000 is 1.09575%; tip position at full/800 is 1.1609%; tip position at full/400 is 9.53249%; tip tangent at full/400 is 46.2314 deg; tip position at full/300 is 10.9267%; tip tangent at full/300 is 41.6427 deg; tip position at full/200 is 13.1684%; tip tangent at full/200 is 71.4843 deg; tip position at end15cm/100 is 12.1676%; tip tangent at end15cm/100 is 65.4224 deg; tip position at end15cm/75 is 15.0157%; tip tangent at end15cm/75 is 63.1743 deg; tip position at end15cm/50 is 14.7416%; tip tangent at end15cm/50 is 23.218 deg; tip position at end15cm/30 is 4.07255%; tip tangent at end15cm/30 is 104.173 deg; tip position at end5cm/30 is 2.52526%; tip tangent at end5cm/30 is 22.2789 deg; tip position at end5cm/20 is 2.63037%; tip tangent at end5cm/20 is 23.3003 deg; tip position at end5cm/15 is 2.28304%; tip tangent at end5cm/15 is 28.8528 deg; boundary curvature angle jump is 83.5558 deg; end15cm phase error is 137.736 deg |

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
| 0 | full | 2000 | 0.119 | 0.212 | -79.020 | 17.550 | 1.983 | 8.375 |
| 0 | full | 1500 | 0.139 | 0.239 | -71.736 | 19.106 | 2.159 | 9.520 |
| 0 | full | 1000 | 0.219 | 0.356 | -62.600 | 25.263 | 2.855 | 12.435 |
| 0 | full | 800 | 0.283 | 0.485 | -71.607 | 37.249 | 4.209 | 17.183 |
| 0 | full | 600 | 0.504 | 0.739 | -46.821 | 44.957 | 5.080 | 23.841 |
| 0 | full | 400 | 0.447 | 0.831 | -85.857 | 66.211 | 7.481 | 33.527 |
| 0 | full | 300 | 0.595 | 1.107 | -86.105 | 88.209 | 9.967 | 54.291 |
| 0 | full | 200 | 0.695 | 1.433 | -106.312 | 115.936 | 13.100 | 74.332 |
| 0 | end15cm | 100 | 0.805 | 6.326 | -686.264 | 158.973 | 17.963 | 134.158 |
| 0 | end15cm | 75 | 0.922 | 7.817 | -747.601 | 183.693 | 20.756 | 120.635 |
| 0 | end15cm | 50 | 1.082 | 8.796 | -712.791 | 166.574 | 18.822 | 20.529 |
| 0 | end15cm | 30 | 1.458 | 6.728 | -361.388 | 45.400 | 5.130 | 106.098 |
| 0 | end5cm | 30 | 1.727 | 4.126 | -138.920 | 75.608 | 8.543 | 141.163 |
| 0 | end5cm | 20 | 2.024 | 4.839 | -139.101 | 75.404 | 8.520 | 48.289 |
| 0 | end5cm | 15 | 2.020 | 4.635 | -129.441 | 54.661 | 6.176 | 49.058 |
| 120 | full | 2000 | 0.156 | 0.167 | -6.760 | 2.794 | 0.316 | 0.711 |
| 120 | full | 1500 | 0.096 | 0.104 | -8.171 | 2.238 | 0.253 | 0.546 |
| 120 | full | 1000 | 0.218 | 0.229 | -5.236 | 2.847 | 0.322 | 2.261 |
| 120 | full | 800 | 0.330 | 0.339 | -2.625 | 6.596 | 0.745 | 5.533 |
| 120 | full | 600 | 0.142 | 0.164 | -15.469 | 8.632 | 0.975 | 9.465 |
| 120 | full | 400 | 0.982 | 1.182 | -20.342 | 70.739 | 7.993 | 50.925 |
| 120 | full | 300 | 0.704 | 0.972 | -38.064 | 61.009 | 6.894 | 33.563 |
| 120 | full | 200 | 0.926 | 1.791 | -93.439 | 130.354 | 14.729 | 83.380 |
| 120 | end15cm | 100 | 6.727 | 2.529 | 62.413 | 59.141 | 6.683 | 35.019 |
| 120 | end15cm | 75 | 8.196 | 2.813 | 65.683 | 59.788 | 6.756 | 22.936 |
| 120 | end15cm | 50 | 9.656 | 3.420 | 64.581 | 59.065 | 6.674 | 6.120 |
| 120 | end15cm | 30 | 7.628 | 2.999 | 60.691 | 27.921 | 3.155 | 40.271 |
| 120 | end5cm | 30 | 3.315 | 2.765 | 16.582 | 46.527 | 5.257 | 64.942 |
| 120 | end5cm | 20 | 4.111 | 3.165 | 23.008 | 45.042 | 5.089 | 33.150 |
| 120 | end5cm | 15 | 4.058 | 3.033 | 25.265 | 31.896 | 3.604 | 51.364 |
| 240 | full | 2000 | 0.145 | 0.152 | -4.972 | 2.750 | 0.311 | 0.203 |
| 240 | full | 1500 | 0.196 | 0.211 | -7.373 | 5.071 | 0.573 | 0.862 |
| 240 | full | 1000 | 0.381 | 0.405 | -6.239 | 9.697 | 1.096 | 2.497 |
| 240 | full | 800 | 0.337 | 0.339 | -0.770 | 10.274 | 1.161 | 4.707 |
| 240 | full | 600 | 0.834 | 0.828 | 0.706 | 6.503 | 0.735 | 4.944 |
| 240 | full | 400 | 0.960 | 1.361 | -41.742 | 84.363 | 9.532 | 46.231 |
| 240 | full | 300 | 1.492 | 2.044 | -37.009 | 96.701 | 10.927 | 41.643 |
| 240 | full | 200 | 1.586 | 2.285 | -44.056 | 116.540 | 13.168 | 71.484 |
| 240 | end15cm | 100 | 7.467 | 4.582 | 38.640 | 107.683 | 12.168 | 65.422 |
| 240 | end15cm | 75 | 8.954 | 5.999 | 33.007 | 132.889 | 15.016 | 63.174 |
| 240 | end15cm | 50 | 9.972 | 7.319 | 26.599 | 130.463 | 14.742 | 23.218 |
| 240 | end15cm | 30 | 7.120 | 5.660 | 20.504 | 36.042 | 4.073 | 104.173 |
| 240 | end5cm | 30 | 1.435 | 1.572 | -9.589 | 22.349 | 2.525 | 22.279 |
| 240 | end5cm | 20 | 1.881 | 1.916 | -1.879 | 23.279 | 2.630 | 23.300 |
| 240 | end5cm | 15 | 2.076 | 2.052 | 1.173 | 20.205 | 2.283 | 28.853 |

## Shared score evidence

- source: `./calibration_results/09B7-20261023T184012+0800-direct0-d01d33/results.json`
- failures: `[]`
