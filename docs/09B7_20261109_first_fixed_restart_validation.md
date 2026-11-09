# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `0`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | True | False | full mean point error at radius 1000 is 2.03043%; full mean point error at radius 800 is 2.29968%; full mean point error at radius 600 is 2.08141%; full mean point error at radius 400 is 2.76286%; full mean point error at radius 300 is 2.7124%; full mean point error at radius 200 is 4.27014%; tail improvement at radius 30 is -14.2541%; tail improvement at radius 20 is -10.3842%; tail improvement at radius 15 is -4.54068%; tip position at full/2000 is 1.93057%; tip position at full/1000 is 6.31649%; tip position at full/800 is 6.75656%; tip position at full/600 is 6.42994%; tip position at full/400 is 8.06616%; tip tangent at full/400 is 10.1545 deg; tip position at full/300 is 7.24108%; tip position at full/200 is 10.5491%; tip tangent at full/200 is 16.3852 deg; tip position at end15cm/100 is 1.64646%; tip position at end15cm/75 is 1.55952%; tip position at end15cm/50 is 1.78535%; tip tangent at end15cm/50 is 13.2995 deg; tip position at end15cm/30 is 2.55508%; tip tangent at end15cm/30 is 20.3295 deg; tip position at end5cm/30 is 2.31036%; tip tangent at end5cm/30 is 14.3321 deg; tip position at end5cm/20 is 2.49998%; tip tangent at end5cm/20 is 21.1852 deg; tip position at end5cm/15 is 2.26692%; tip tangent at end5cm/15 is 32.5036 deg; boundary curvature angle jump is 66.8371 deg |
| 120 | False | True | True | False | full mean point error at radius 2000 is 1.14852%; full mean point error at radius 1000 is 1.80742%; full mean point error at radius 800 is 4.67398%; full mean point error at radius 600 is 1.88859%; full mean point error at radius 400 is 2.77998%; full mean point error at radius 300 is 3.73322%; full mean point error at radius 200 is 4.60843%; tail improvement at radius 30 is -47.8776%; tail improvement at radius 20 is -23.5788%; tail improvement at radius 15 is -12.4088%; tip position at full/2000 is 3.19622%; tip position at full/1000 is 5.47576%; tip position at full/800 is 14.3815%; tip tangent at full/800 is 15.8732 deg; tip position at full/600 is 5.62633%; tip position at full/400 is 7.60788%; tip position at full/300 is 9.00743%; tip position at full/200 is 9.29173%; tip tangent at full/200 is 17.6492 deg; tip position at end15cm/100 is 1.22989%; tip position at end15cm/75 is 1.65922%; tip position at end15cm/50 is 1.86547%; tip tangent at end15cm/50 is 22.3815 deg; tip position at end15cm/30 is 3.23273%; tip tangent at end15cm/30 is 15.9744 deg; tip position at end5cm/30 is 3.00538%; tip tangent at end5cm/30 is 20.0976 deg; tip position at end5cm/20 is 3.1091%; tip tangent at end5cm/20 is 27.1321 deg; tip position at end5cm/15 is 2.49683%; tip tangent at end5cm/15 is 40.018 deg; boundary curvature angle jump is 57.7536 deg |
| 240 | False | True | True | False | full mean point error at radius 2000 is 1.53249%; full mean point error at radius 1000 is 2.09182%; full mean point error at radius 800 is 3.96232%; full mean point error at radius 600 is 5.67455%; full mean point error at radius 400 is 6.4711%; full mean point error at radius 300 is 5.32018%; full mean point error at radius 200 is 6.47981%; tail improvement at radius 15 is -0.761911%; tip position at full/2000 is 4.45213%; tip position at full/1500 is 2.26344%; tip position at full/1000 is 6.48813%; tip position at full/800 is 11.424%; tip position at full/600 is 15.8063%; tip tangent at full/600 is 10.484 deg; tip position at full/400 is 16.3465%; tip tangent at full/400 is 18.6125 deg; tip position at full/300 is 11.7381%; tip tangent at full/300 is 24.7994 deg; tip position at full/200 is 14.4532%; tip tangent at full/200 is 48.9142 deg; tip position at end15cm/100 is 3.52263%; tip position at end15cm/75 is 3.81699%; tip tangent at end15cm/75 is 11.3735 deg; tip position at end15cm/50 is 4.12566%; tip tangent at end15cm/50 is 44.7171 deg; tip position at end15cm/30 is 2.85483%; tip tangent at end15cm/30 is 21.5081 deg; tip position at end5cm/30 is 2.6758%; tip tangent at end5cm/30 is 18.9977 deg; tip position at end5cm/20 is 2.82653%; tip tangent at end5cm/20 is 25.157 deg; tip position at end5cm/15 is 2.48589%; tip tangent at end5cm/15 is 38.6184 deg; boundary curvature angle jump is 94.0164 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 0.973 | 30.000 | True | True |
| 0 | end5cm | 10.730 | 30.000 | True | False |
| 120 | end15cm | 0.288 | 30.000 | True | True |
| 120 | end5cm | 6.935 | 30.000 | True | False |
| 240 | end15cm | 4.020 | 30.000 | True | True |
| 240 | end5cm | 55.834 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.740 | 0.741 | -0.169 | 17.086 | 1.931 | 1.373 |
| 0 | full | 1500 | 0.449 | 0.454 | -1.266 | 8.571 | 0.968 | 0.963 |
| 0 | full | 1000 | 2.036 | 2.030 | 0.293 | 55.901 | 6.316 | 6.002 |
| 0 | full | 800 | 2.307 | 2.300 | 0.326 | 59.796 | 6.757 | 5.338 |
| 0 | full | 600 | 2.089 | 2.081 | 0.373 | 56.905 | 6.430 | 5.356 |
| 0 | full | 400 | 2.760 | 2.763 | -0.120 | 71.386 | 8.066 | 10.154 |
| 0 | full | 300 | 2.711 | 2.712 | -0.046 | 64.084 | 7.241 | 7.936 |
| 0 | full | 200 | 4.263 | 4.270 | -0.173 | 93.360 | 10.549 | 16.385 |
| 0 | end15cm | 100 | 0.314 | 0.758 | -141.189 | 14.571 | 1.646 | 7.210 |
| 0 | end15cm | 75 | 0.371 | 0.825 | -122.364 | 13.802 | 1.560 | 4.296 |
| 0 | end15cm | 50 | 0.787 | 1.173 | -49.080 | 15.800 | 1.785 | 13.299 |
| 0 | end15cm | 30 | 1.117 | 1.565 | -40.120 | 22.612 | 2.555 | 20.329 |
| 0 | end5cm | 30 | 1.429 | 1.632 | -14.254 | 20.447 | 2.310 | 14.332 |
| 0 | end5cm | 20 | 1.775 | 1.960 | -10.384 | 22.125 | 2.500 | 21.185 |
| 0 | end5cm | 15 | 2.168 | 2.266 | -4.541 | 20.062 | 2.267 | 32.504 |
| 120 | full | 2000 | 1.148 | 1.149 | -0.018 | 28.287 | 3.196 | 3.250 |
| 120 | full | 1500 | 0.205 | 0.210 | -2.508 | 4.517 | 0.510 | 1.244 |
| 120 | full | 1000 | 1.815 | 1.807 | 0.441 | 48.460 | 5.476 | 5.054 |
| 120 | full | 800 | 4.681 | 4.674 | 0.142 | 127.276 | 14.381 | 15.873 |
| 120 | full | 600 | 1.885 | 1.889 | -0.179 | 49.793 | 5.626 | 6.102 |
| 120 | full | 400 | 2.797 | 2.780 | 0.604 | 67.330 | 7.608 | 2.881 |
| 120 | full | 300 | 3.753 | 3.733 | 0.517 | 79.716 | 9.007 | 8.290 |
| 120 | full | 200 | 4.627 | 4.608 | 0.402 | 82.232 | 9.292 | 17.649 |
| 120 | end15cm | 100 | 0.826 | 0.686 | 16.916 | 10.885 | 1.230 | 2.736 |
| 120 | end15cm | 75 | 1.186 | 1.005 | 15.275 | 14.684 | 1.659 | 2.065 |
| 120 | end15cm | 50 | 1.922 | 1.305 | 32.107 | 16.509 | 1.865 | 22.382 |
| 120 | end15cm | 30 | 2.201 | 2.011 | 8.655 | 28.610 | 3.233 | 15.974 |
| 120 | end5cm | 30 | 1.451 | 2.145 | -47.878 | 26.598 | 3.005 | 20.098 |
| 120 | end5cm | 20 | 2.000 | 2.471 | -23.579 | 27.516 | 3.109 | 27.132 |
| 120 | end5cm | 15 | 2.211 | 2.486 | -12.409 | 22.097 | 2.497 | 40.018 |
| 240 | full | 2000 | 1.549 | 1.532 | 1.037 | 39.401 | 4.452 | 3.127 |
| 240 | full | 1500 | 0.876 | 0.850 | 2.908 | 20.031 | 2.263 | 1.420 |
| 240 | full | 1000 | 2.119 | 2.092 | 1.271 | 57.420 | 6.488 | 7.720 |
| 240 | full | 800 | 4.001 | 3.962 | 0.959 | 101.103 | 11.424 | 9.949 |
| 240 | full | 600 | 5.725 | 5.675 | 0.881 | 139.886 | 15.806 | 10.484 |
| 240 | full | 400 | 6.536 | 6.471 | 0.987 | 144.666 | 16.346 | 18.612 |
| 240 | full | 300 | 5.377 | 5.320 | 1.053 | 103.882 | 11.738 | 24.799 |
| 240 | full | 200 | 6.486 | 6.480 | 0.090 | 127.911 | 14.453 | 48.914 |
| 240 | end15cm | 100 | 3.413 | 1.765 | 48.290 | 31.175 | 3.523 | 6.833 |
| 240 | end15cm | 75 | 4.188 | 2.120 | 49.368 | 33.780 | 3.817 | 11.374 |
| 240 | end15cm | 50 | 4.569 | 2.738 | 40.064 | 36.512 | 4.126 | 44.717 |
| 240 | end15cm | 30 | 2.851 | 2.266 | 20.529 | 25.265 | 2.855 | 21.508 |
| 240 | end5cm | 30 | 2.237 | 1.814 | 18.907 | 23.681 | 2.676 | 18.998 |
| 240 | end5cm | 20 | 2.474 | 2.143 | 13.361 | 25.015 | 2.827 | 25.157 |
| 240 | end5cm | 15 | 2.309 | 2.327 | -0.762 | 22.000 | 2.486 | 38.618 |

## Shared score evidence

- source: `./calibration_results/09B7-20261109T170754+0800-direct0-d3edb8/results.json`
- failures: `[]`
