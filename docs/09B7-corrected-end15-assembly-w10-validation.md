# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `-31.4`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | False | False | full regression at radius 600 is 0.205796 percentage points; full regression at radius 400 is 0.335323 percentage points; full regression at radius 300 is 0.244641 percentage points; full regression at radius 200 is 0.296614 percentage points; tail improvement at radius 30 is 3.57272%; tail improvement at radius 20 is 6.02367%; tail improvement at radius 15 is 9.52495%; tip position at full/2000 is 2.27306%; tip position at full/1500 is 2.76774%; tip position at full/1000 is 2.71226%; tip tangent at full/1000 is 10.4472 deg; tip position at full/800 is 3.79542%; tip tangent at full/800 is 11.7541 deg; tip position at full/600 is 3.78593%; tip tangent at full/600 is 13.3137 deg; tip position at full/400 is 6.86942%; tip tangent at full/400 is 27.2028 deg; tip position at full/300 is 4.46757%; tip position at full/200 is 4.83394%; tip tangent at full/200 is 12.4823 deg; tip position at end15cm/100 is 18.6711%; tip tangent at end15cm/100 is 133.552 deg; tip position at end15cm/75 is 20.1565%; tip tangent at end15cm/75 is 99.9617 deg; tip position at end15cm/50 is 18.0692%; tip tangent at end15cm/50 is 15.0898 deg; tip position at end15cm/30 is 4.87209%; tip tangent at end15cm/30 is 111.243 deg; tip position at end5cm/30 is 7.98336%; tip tangent at end5cm/30 is 114.64 deg; tip position at end5cm/20 is 7.98059%; tip tangent at end5cm/20 is 42.815 deg; tip position at end5cm/15 is 5.50508%; tip tangent at end5cm/15 is 63.1101 deg; boundary curvature angle jump is 139.12 deg; end15cm phase error is 174.229 deg |
| 120 | False | True | False | False | full mean point error at radius 400 is 1.09765%; full mean point error at radius 200 is 1.13252%; full regression at radius 200 is 0.332907 percentage points; tip position at full/800 is 1.24714%; tip position at full/400 is 6.4519%; tip tangent at full/400 is 37.8484 deg; tip position at full/300 is 2.56528%; tip position at full/200 is 4.72873%; tip position at end15cm/100 is 7.09714%; tip tangent at end15cm/100 is 49.8442 deg; tip position at end15cm/75 is 6.89513%; tip tangent at end15cm/75 is 42.944 deg; tip position at end15cm/50 is 8.66314%; tip tangent at end15cm/50 is 30.5111 deg; tip position at end15cm/30 is 3.67381%; tip tangent at end15cm/30 is 28.4641 deg; tip position at end5cm/30 is 7.82135%; tip tangent at end5cm/30 is 118.567 deg; tip position at end5cm/20 is 7.85757%; tip tangent at end5cm/20 is 45.5216 deg; tip position at end5cm/15 is 5.80879%; tip tangent at end5cm/15 is 45.9996 deg; boundary curvature angle jump is 125.072 deg; end15cm phase error is 45.147 deg |
| 240 | False | True | False | False | full mean point error at radius 600 is 1.06927%; full mean point error at radius 400 is 1.22844%; full regression at radius 400 is 0.246246 percentage points; full mean point error at radius 300 is 1.40303%; full regression at radius 300 is 0.226438 percentage points; full mean point error at radius 200 is 1.81471%; full regression at radius 200 is 0.264537 percentage points; tail improvement at radius 30 is 2.07292%; tail improvement at radius 20 is 1.92592%; tail improvement at radius 15 is 2.66848%; tip position at full/2000 is 2.00623%; tip position at full/1500 is 2.6958%; tip position at full/1000 is 3.38879%; tip tangent at full/1000 is 11.3678 deg; tip position at full/800 is 4.79799%; tip tangent at full/800 is 13.8772 deg; tip position at full/600 is 5.02077%; tip tangent at full/600 is 17.6887 deg; tip position at full/400 is 5.81976%; tip tangent at full/400 is 13.5953 deg; tip position at full/300 is 5.74645%; tip tangent at full/300 is 11.4947 deg; tip position at full/200 is 4.81894%; tip position at end15cm/100 is 17.3057%; tip tangent at end15cm/100 is 110.196 deg; tip position at end15cm/75 is 19.9614%; tip tangent at end15cm/75 is 97.1342 deg; tip position at end15cm/50 is 18.3247%; tip tangent at end15cm/50 is 17.5719 deg; tip position at end15cm/30 is 4.76342%; tip tangent at end15cm/30 is 117.812 deg; tip position at end5cm/30 is 8.49631%; tip tangent at end5cm/30 is 131.683 deg; tip position at end5cm/20 is 8.62971%; tip tangent at end5cm/20 is 48.867 deg; tip position at end5cm/15 is 6.48052%; tip tangent at end5cm/15 is 46.9835 deg; boundary curvature angle jump is 85.2818 deg; end15cm phase error is 152.579 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 174.229 | 30.000 | False | True |
| 0 | end5cm | 132.886 | 30.000 | False | False |
| 120 | end15cm | 45.147 | 30.000 | False | True |
| 120 | end5cm | 179.125 | 30.000 | False | False |
| 240 | end15cm | 152.579 | 30.000 | False | True |
| 240 | end5cm | 175.156 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.226 | 0.325 | -43.662 | 20.117 | 2.273 | 8.074 |
| 0 | full | 1500 | 0.421 | 0.519 | -23.342 | 24.494 | 2.768 | 9.486 |
| 0 | full | 1000 | 0.200 | 0.340 | -69.839 | 24.004 | 2.712 | 10.447 |
| 0 | full | 800 | 0.306 | 0.494 | -61.841 | 33.589 | 3.795 | 11.754 |
| 0 | full | 600 | 0.416 | 0.621 | -49.513 | 33.505 | 3.786 | 13.314 |
| 0 | full | 400 | 0.594 | 0.929 | -56.492 | 60.794 | 6.869 | 27.203 |
| 0 | full | 300 | 0.616 | 0.860 | -39.729 | 39.538 | 4.468 | 6.224 |
| 0 | full | 200 | 0.597 | 0.894 | -49.661 | 42.780 | 4.834 | 12.482 |
| 0 | end15cm | 100 | 5.855 | 6.644 | -13.484 | 165.239 | 18.671 | 133.552 |
| 0 | end15cm | 75 | 7.414 | 7.751 | -4.538 | 178.385 | 20.157 | 99.962 |
| 0 | end15cm | 50 | 8.732 | 8.601 | 1.491 | 159.912 | 18.069 | 15.090 |
| 0 | end15cm | 30 | 6.804 | 6.466 | 4.975 | 43.118 | 4.872 | 111.243 |
| 0 | end5cm | 30 | 4.179 | 4.029 | 3.573 | 70.653 | 7.983 | 114.640 |
| 0 | end5cm | 20 | 5.000 | 4.699 | 6.024 | 70.628 | 7.981 | 42.815 |
| 0 | end5cm | 15 | 4.929 | 4.460 | 9.525 | 48.720 | 5.505 | 63.110 |
| 120 | full | 2000 | 0.162 | 0.154 | 4.938 | 1.082 | 0.122 | 0.620 |
| 120 | full | 1500 | 0.152 | 0.141 | 7.325 | 2.221 | 0.251 | 1.350 |
| 120 | full | 1000 | 0.151 | 0.167 | -10.595 | 4.133 | 0.467 | 3.485 |
| 120 | full | 800 | 0.389 | 0.414 | -6.462 | 11.037 | 1.247 | 5.227 |
| 120 | full | 600 | 0.110 | 0.113 | -2.376 | 4.300 | 0.486 | 7.513 |
| 120 | full | 400 | 0.961 | 1.098 | -14.201 | 57.099 | 6.452 | 37.848 |
| 120 | full | 300 | 0.635 | 0.656 | -3.201 | 22.703 | 2.565 | 8.590 |
| 120 | full | 200 | 0.800 | 1.133 | -41.634 | 41.849 | 4.729 | 6.662 |
| 120 | end15cm | 100 | 2.611 | 2.364 | 9.457 | 62.810 | 7.097 | 49.844 |
| 120 | end15cm | 75 | 3.774 | 2.428 | 35.676 | 61.022 | 6.895 | 42.944 |
| 120 | end15cm | 50 | 5.238 | 3.584 | 31.580 | 76.669 | 8.663 | 30.511 |
| 120 | end15cm | 30 | 4.169 | 3.285 | 21.208 | 32.513 | 3.674 | 28.464 |
| 120 | end5cm | 30 | 4.270 | 3.783 | 11.412 | 69.219 | 7.821 | 118.567 |
| 120 | end5cm | 20 | 5.001 | 4.464 | 10.747 | 69.540 | 7.858 | 45.522 |
| 120 | end5cm | 15 | 4.904 | 4.344 | 11.427 | 51.408 | 5.809 | 46.000 |
| 240 | full | 2000 | 0.246 | 0.326 | -32.557 | 17.755 | 2.006 | 7.045 |
| 240 | full | 1500 | 0.347 | 0.450 | -29.782 | 23.858 | 2.696 | 8.906 |
| 240 | full | 1000 | 0.491 | 0.620 | -26.374 | 29.991 | 3.389 | 11.368 |
| 240 | full | 800 | 0.693 | 0.881 | -27.100 | 42.462 | 4.798 | 13.877 |
| 240 | full | 600 | 0.869 | 1.069 | -22.982 | 44.434 | 5.021 | 17.689 |
| 240 | full | 400 | 0.982 | 1.228 | -25.071 | 51.505 | 5.820 | 13.595 |
| 240 | full | 300 | 1.177 | 1.403 | -19.245 | 50.856 | 5.746 | 11.495 |
| 240 | full | 200 | 1.550 | 1.815 | -17.065 | 42.648 | 4.819 | 4.337 |
| 240 | end15cm | 100 | 6.796 | 6.318 | 7.029 | 153.156 | 17.306 | 110.196 |
| 240 | end15cm | 75 | 8.358 | 7.788 | 6.826 | 176.658 | 19.961 | 97.134 |
| 240 | end15cm | 50 | 9.591 | 8.653 | 9.784 | 162.174 | 18.325 | 17.572 |
| 240 | end15cm | 30 | 7.083 | 6.557 | 7.420 | 42.156 | 4.763 | 117.812 |
| 240 | end5cm | 30 | 4.320 | 4.231 | 2.073 | 75.192 | 8.496 | 131.683 |
| 240 | end5cm | 20 | 5.092 | 4.994 | 1.926 | 76.373 | 8.630 | 48.867 |
| 240 | end5cm | 15 | 5.006 | 4.873 | 2.668 | 57.353 | 6.481 | 46.983 |

## Shared score evidence

- source: `./calibration_results/09B7_corrected/09B7-20261026T163721+0800-direct0-8de714/results.json`
- failures: `[]`
