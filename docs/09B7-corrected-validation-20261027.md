# Multi-region full-geometry validation

- unified global phase: `-2.2794405900872987`
- unified rot_ang: `-31.4`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | False | False | full regression at radius 600 is 0.229252 percentage points; full regression at radius 400 is 0.391378 percentage points; full mean point error at radius 300 is 1.11514%; full regression at radius 300 is 0.499367 percentage points; full mean point error at radius 200 is 1.33876%; full regression at radius 200 is 0.741478 percentage points; tip position at full/2000 is 2.28628%; tip position at full/1500 is 2.78075%; tip position at full/1000 is 2.78876%; tip tangent at full/1000 is 11.178 deg; tip position at full/800 is 4.00666%; tip tangent at full/800 is 13.4776 deg; tip position at full/600 is 4.30353%; tip tangent at full/600 is 17.6645 deg; tip position at full/400 is 8.10175%; tip tangent at full/400 is 38.6659 deg; tip position at full/300 is 9.43232%; tip tangent at full/300 is 46.3707 deg; tip position at full/200 is 13.0161%; tip tangent at full/200 is 80.1952 deg; tip position at end15cm/100 is 16.7028%; tip tangent at end15cm/100 is 108.933 deg; tip position at end15cm/75 is 18.5409%; tip tangent at end15cm/75 is 88.057 deg; tip position at end15cm/50 is 17.4681%; tip tangent at end15cm/50 is 13.7303 deg; tip position at end15cm/30 is 4.83179%; tip tangent at end15cm/30 is 109.618 deg; tip position at end5cm/30 is 7.09487%; tip tangent at end5cm/30 is 95.4771 deg; tip position at end5cm/20 is 7.36376%; tip tangent at end5cm/20 is 40.2304 deg; tip position at end5cm/15 is 5.10556%; tip tangent at end5cm/15 is 60.8059 deg; boundary curvature angle jump is 117.61 deg; end15cm phase error is 174.229 deg |
| 120 | False | True | False | False | full mean point error at radius 400 is 1.14693%; full regression at radius 300 is 0.269843 percentage points; full mean point error at radius 200 is 1.65495%; full regression at radius 200 is 0.855341 percentage points; tail improvement at radius 30 is 5.15406%; tail improvement at radius 20 is 6.40851%; tail improvement at radius 15 is 8.33131%; tip position at full/800 is 1.32011%; tip position at full/400 is 7.3298%; tip tangent at full/400 is 44.1213 deg; tip position at full/300 is 7.09485%; tip tangent at full/300 is 43.019 deg; tip position at full/200 is 14.0556%; tip tangent at full/200 is 81.7658 deg; tip position at end15cm/100 is 10.3511%; tip tangent at end15cm/100 is 70.529 deg; tip position at end15cm/75 is 10.6062%; tip tangent at end15cm/75 is 60.928 deg; tip position at end15cm/50 is 9.78363%; tip tangent at end15cm/50 is 31.3404 deg; tip position at end15cm/30 is 3.73128%; tip tangent at end15cm/30 is 30.6105 deg; tip position at end5cm/30 is 8.37926%; tip tangent at end5cm/30 is 134.095 deg; tip position at end5cm/20 is 8.24104%; tip tangent at end5cm/20 is 45.9098 deg; tip position at end5cm/15 is 5.98463%; tip tangent at end5cm/15 is 48.181 deg; boundary curvature angle jump is 138.686 deg; end15cm phase error is 45.147 deg |
| 240 | False | True | False | False | full regression at radius 800 is 0.211716 percentage points; full mean point error at radius 600 is 1.10521%; full regression at radius 600 is 0.235754 percentage points; full mean point error at radius 400 is 1.40262%; full regression at radius 400 is 0.420428 percentage points; full mean point error at radius 300 is 1.69713%; full regression at radius 300 is 0.520544 percentage points; full mean point error at radius 200 is 2.33215%; full regression at radius 200 is 0.781987 percentage points; tip position at full/2000 is 2.2328%; tip position at full/1500 is 2.84817%; tip position at full/1000 is 3.55204%; tip tangent at full/1000 is 12.5328 deg; tip position at full/800 is 5.16608%; tip tangent at full/800 is 16.1742 deg; tip position at full/600 is 5.68425%; tip tangent at full/600 is 23.0824 deg; tip position at full/400 is 8.69049%; tip tangent at full/400 is 31.9367 deg; tip position at full/300 is 10.741%; tip tangent at full/300 is 49.1864 deg; tip position at full/200 is 13.3313%; tip tangent at full/200 is 64.7511 deg; tip position at end15cm/100 is 15.3524%; tip tangent at end15cm/100 is 91.3904 deg; tip position at end15cm/75 is 17.7421%; tip tangent at end15cm/75 is 81.4938 deg; tip position at end15cm/50 is 17.675%; tip tangent at end15cm/50 is 16.9594 deg; tip position at end15cm/30 is 4.72342%; tip tangent at end15cm/30 is 115.721 deg; tip position at end5cm/30 is 4.79396%; tip tangent at end5cm/30 is 57.5067 deg; tip position at end5cm/20 is 5.55941%; tip tangent at end5cm/20 is 35.4134 deg; tip position at end5cm/15 is 4.51722%; tip tangent at end5cm/15 is 32.948 deg; boundary curvature angle jump is 122.491 deg; end15cm phase error is 152.579 deg |

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
| 0 | full | 2000 | 0.226 | 0.326 | -43.873 | 20.234 | 2.286 | 8.214 |
| 0 | full | 1500 | 0.421 | 0.519 | -23.380 | 24.610 | 2.781 | 9.673 |
| 0 | full | 1000 | 0.200 | 0.343 | -71.240 | 24.681 | 2.789 | 11.178 |
| 0 | full | 800 | 0.306 | 0.504 | -64.979 | 35.459 | 4.007 | 13.478 |
| 0 | full | 600 | 0.416 | 0.645 | -55.156 | 38.086 | 4.304 | 17.664 |
| 0 | full | 400 | 0.594 | 0.985 | -65.936 | 71.701 | 8.102 | 38.666 |
| 0 | full | 300 | 0.616 | 1.115 | -81.096 | 83.476 | 9.432 | 46.371 |
| 0 | full | 200 | 0.597 | 1.339 | -124.142 | 115.193 | 13.016 | 80.195 |
| 0 | end15cm | 100 | 5.855 | 5.970 | -1.964 | 147.820 | 16.703 | 108.933 |
| 0 | end15cm | 75 | 7.414 | 7.149 | 3.584 | 164.087 | 18.541 | 88.057 |
| 0 | end15cm | 50 | 8.732 | 8.333 | 4.568 | 154.593 | 17.468 | 13.730 |
| 0 | end15cm | 30 | 6.804 | 6.399 | 5.965 | 42.761 | 4.832 | 109.618 |
| 0 | end5cm | 30 | 4.179 | 3.654 | 12.549 | 62.790 | 7.095 | 95.477 |
| 0 | end5cm | 20 | 5.000 | 4.400 | 11.997 | 65.169 | 7.364 | 40.230 |
| 0 | end5cm | 15 | 4.929 | 4.191 | 14.989 | 45.184 | 5.106 | 60.806 |
| 120 | full | 2000 | 0.162 | 0.153 | 5.087 | 1.060 | 0.120 | 0.630 |
| 120 | full | 1500 | 0.152 | 0.141 | 7.338 | 2.229 | 0.252 | 1.368 |
| 120 | full | 1000 | 0.151 | 0.170 | -12.996 | 4.657 | 0.526 | 3.834 |
| 120 | full | 800 | 0.389 | 0.418 | -7.521 | 11.683 | 1.320 | 5.722 |
| 120 | full | 600 | 0.110 | 0.114 | -3.564 | 4.827 | 0.545 | 7.871 |
| 120 | full | 400 | 0.961 | 1.147 | -19.328 | 64.869 | 7.330 | 44.121 |
| 120 | full | 300 | 0.635 | 0.905 | -42.470 | 62.789 | 7.095 | 43.019 |
| 120 | full | 200 | 0.800 | 1.655 | -106.970 | 124.392 | 14.056 | 81.766 |
| 120 | end15cm | 100 | 2.611 | 3.527 | -35.086 | 91.607 | 10.351 | 70.529 |
| 120 | end15cm | 75 | 3.774 | 3.833 | -1.561 | 93.865 | 10.606 | 60.928 |
| 120 | end15cm | 50 | 5.238 | 4.110 | 21.536 | 86.585 | 9.784 | 31.340 |
| 120 | end15cm | 30 | 4.169 | 3.405 | 18.326 | 33.022 | 3.731 | 30.610 |
| 120 | end5cm | 30 | 4.270 | 4.050 | 5.154 | 74.156 | 8.379 | 134.095 |
| 120 | end5cm | 20 | 5.001 | 4.680 | 6.409 | 72.933 | 8.241 | 45.910 |
| 120 | end5cm | 15 | 4.904 | 4.496 | 8.331 | 52.964 | 5.985 | 48.181 |
| 240 | full | 2000 | 0.246 | 0.341 | -38.634 | 19.760 | 2.233 | 8.549 |
| 240 | full | 1500 | 0.347 | 0.460 | -32.664 | 25.206 | 2.848 | 9.940 |
| 240 | full | 1000 | 0.491 | 0.630 | -28.408 | 31.436 | 3.552 | 12.533 |
| 240 | full | 800 | 0.693 | 0.905 | -30.538 | 45.720 | 5.166 | 16.174 |
| 240 | full | 600 | 0.869 | 1.105 | -27.115 | 50.306 | 5.684 | 23.082 |
| 240 | full | 400 | 0.982 | 1.403 | -42.805 | 76.911 | 8.690 | 31.937 |
| 240 | full | 300 | 1.177 | 1.697 | -44.242 | 95.057 | 10.741 | 49.186 |
| 240 | full | 200 | 1.550 | 2.332 | -50.445 | 117.982 | 13.331 | 64.751 |
| 240 | end15cm | 100 | 6.796 | 5.640 | 17.007 | 135.869 | 15.352 | 91.390 |
| 240 | end15cm | 75 | 8.358 | 6.960 | 16.733 | 157.018 | 17.742 | 81.494 |
| 240 | end15cm | 50 | 9.591 | 8.342 | 13.025 | 156.424 | 17.675 | 16.959 |
| 240 | end15cm | 30 | 7.083 | 6.486 | 8.422 | 41.802 | 4.723 | 115.721 |
| 240 | end5cm | 30 | 4.320 | 2.587 | 40.119 | 42.427 | 4.794 | 57.507 |
| 240 | end5cm | 20 | 5.092 | 3.388 | 33.469 | 49.201 | 5.559 | 35.413 |
| 240 | end5cm | 15 | 5.006 | 3.482 | 30.438 | 39.977 | 4.517 | 32.948 |

## Shared score evidence

- source: `./calibration_results/09B7_corrected/09B7-20261026T163721+0800-direct0-8de714/results.json`
- failures: `[]`
