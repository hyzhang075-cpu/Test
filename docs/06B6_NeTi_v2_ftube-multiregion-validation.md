# Multi-region full-geometry validation

- unified global phase: `-0.7058749485849114`
- unified rot_ang: `31.8`
- shared score thresholds verified: `True`

## Direction gates

| direct | deployable | optimization | end15 phase | full geometry | failures |
|---:|---:|---:|---:|---:|---|
| 0 | False | True | True | False | full mean point error at radius 400 is 1.08565%; full mean point error at radius 300 is 1.26725%; full mean point error at radius 200 is 1.63343%; tail improvement at radius 30 is -20.2373%; tail improvement at radius 20 is -10.4131%; tail improvement at radius 15 is -9.14573%; tip position at full/2000 is 1.01161%; tip position at full/800 is 1.31629%; tip position at full/600 is 1.44248%; tip tangent at full/600 is 14.3494 deg; tip position at full/400 is 2.58886%; tip tangent at full/400 is 21.26 deg; tip position at full/300 is 3.59738%; tip tangent at full/300 is 27.7645 deg; tip position at full/200 is 7.06743%; tip tangent at full/200 is 46.0126 deg; tip position at end15cm/100 is 8.38209%; tip tangent at end15cm/100 is 76.2139 deg; tip position at end15cm/75 is 10.3005%; tip tangent at end15cm/75 is 93.2697 deg; tip position at end15cm/50 is 8.85026%; tip tangent at end15cm/50 is 102.014 deg; tip position at end15cm/30 is 10.2331%; tip tangent at end15cm/30 is 102.104 deg; tip position at end5cm/30 is 6.94915%; tip tangent at end5cm/30 is 136.661 deg; tip position at end5cm/20 is 7.60137%; tip tangent at end5cm/20 is 108.558 deg; tip position at end5cm/15 is 7.2539%; tip tangent at end5cm/15 is 62.7851 deg; boundary curvature angle jump is 157.966 deg |
| 120 | False | True | True | False | full mean point error at radius 200 is 1.23243%; tail improvement at radius 30 is -679.334%; tail improvement at radius 20 is -596.465%; tail improvement at radius 15 is -332.674%; tip position at full/800 is 1.15606%; tip tangent at full/800 is 10.6502 deg; tip tangent at full/600 is 12.8956 deg; tip position at full/400 is 1.61356%; tip tangent at full/400 is 18.27 deg; tip position at full/300 is 2.41014%; tip tangent at full/300 is 26.4231 deg; tip position at full/200 is 5.20875%; tip tangent at full/200 is 45.5781 deg; tip position at end15cm/100 is 8.42918%; tip tangent at end15cm/100 is 78.3758 deg; tip position at end15cm/75 is 10.1658%; tip tangent at end15cm/75 is 95.555 deg; tip position at end15cm/50 is 9.25668%; tip tangent at end15cm/50 is 92.1044 deg; tip position at end15cm/30 is 15.0817%; tip tangent at end15cm/30 is 52.4019 deg; tip position at end5cm/30 is 7.2882%; tip tangent at end5cm/30 is 152.812 deg; tip position at end5cm/20 is 9.05055%; tip tangent at end5cm/20 is 91.4406 deg; tip position at end5cm/15 is 8.08091%; tip tangent at end5cm/15 is 41.8019 deg; boundary curvature angle jump is 88.2832 deg |
| 240 | False | False | False | False | optimization stages are not usable; full mean point error at radius 2000 is 1.81264%; full mean point error at radius 1500 is 2.0413%; full mean point error at radius 1000 is 3.1017%; full mean point error at radius 800 is 3.30209%; full mean point error at radius 600 is 4.29562%; full mean point error at radius 400 is 6.32477%; full mean point error at radius 300 is 8.66519%; full mean point error at radius 200 is 13.0231%; tail improvement at radius 20 is -40.884%; tail improvement at radius 15 is -11.4988%; tip position at full/2000 is 2.03809%; tip tangent at full/2000 is 17.0198 deg; tip position at full/1500 is 3.66618%; tip tangent at full/1500 is 19.2983 deg; tip position at full/1000 is 5.58175%; tip tangent at full/1000 is 31.759 deg; tip position at full/800 is 8.96877%; tip tangent at full/800 is 39.4007 deg; tip position at full/600 is 13.491%; tip tangent at full/600 is 51.4281 deg; tip position at full/400 is 23.7376%; tip tangent at full/400 is 77.9884 deg; tip position at full/300 is 36.4369%; tip tangent at full/300 is 109.037 deg; tip position at full/200 is 54.0354%; tip tangent at full/200 is 127.881 deg; tip position at end15cm/100 is 20.4335%; tip tangent at end15cm/100 is 146.184 deg; tip position at end15cm/75 is 23.3962%; tip tangent at end15cm/75 is 148.801 deg; tip position at end15cm/50 is 22.3396%; tip tangent at end15cm/50 is 57.904 deg; tip position at end15cm/30 is 5.36039%; tip tangent at end15cm/30 is 154.684 deg; tip tangent at end5cm/30 is 20.3593 deg; tip position at end5cm/20 is 2.40105%; tip tangent at end5cm/20 is 45.0812 deg; tip position at end5cm/15 is 2.79396%; tip tangent at end5cm/15 is 62.7042 deg; boundary curvature angle jump is 120.367 deg; end15cm phase error is 159.978 deg |

## Phase transport

| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |
|---:|---|---:|---:|---:|---:|
| 0 | end15cm | 19.075 | 30.000 | True | True |
| 0 | end5cm | 53.470 | 30.000 | False | False |
| 120 | end15cm | 12.334 | 30.000 | True | True |
| 120 | end5cm | 58.513 | 30.000 | False | False |
| 240 | end15cm | 159.978 | 30.000 | False | True |
| 240 | end5cm | 63.946 | 30.000 | False | False |

## Reconstruction replay

| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 0.569 | 0.559 | 1.760 | 8.872 | 1.012 | 0.102 |
| 0 | full | 1500 | 0.524 | 0.504 | 3.824 | 8.064 | 0.919 | 2.097 |
| 0 | full | 1000 | 0.707 | 0.668 | 5.533 | 6.242 | 0.712 | 6.539 |
| 0 | full | 800 | 0.854 | 0.791 | 7.392 | 11.544 | 1.316 | 9.762 |
| 0 | full | 600 | 0.901 | 0.832 | 7.620 | 12.651 | 1.442 | 14.349 |
| 0 | full | 400 | 1.129 | 1.086 | 3.803 | 22.704 | 2.589 | 21.260 |
| 0 | full | 300 | 1.275 | 1.267 | 0.608 | 31.549 | 3.597 | 27.764 |
| 0 | full | 200 | 1.472 | 1.633 | -10.989 | 61.981 | 7.067 | 46.013 |
| 0 | end15cm | 100 | 1.014 | 2.459 | -142.527 | 73.511 | 8.382 | 76.214 |
| 0 | end15cm | 75 | 1.119 | 3.182 | -184.318 | 90.336 | 10.301 | 93.270 |
| 0 | end15cm | 50 | 1.185 | 2.329 | -96.596 | 77.617 | 8.850 | 102.014 |
| 0 | end15cm | 30 | 1.365 | 3.471 | -154.325 | 89.744 | 10.233 | 102.104 |
| 0 | end5cm | 30 | 2.677 | 3.219 | -20.237 | 60.944 | 6.949 | 136.661 |
| 0 | end5cm | 20 | 3.453 | 3.812 | -10.413 | 66.664 | 7.601 | 108.558 |
| 0 | end5cm | 15 | 3.786 | 4.132 | -9.146 | 63.617 | 7.254 | 62.785 |
| 120 | full | 2000 | 0.419 | 0.395 | 5.832 | 5.771 | 0.658 | 4.382 |
| 120 | full | 1500 | 0.121 | 0.122 | -1.446 | 6.489 | 0.740 | 6.099 |
| 120 | full | 1000 | 0.394 | 0.360 | 8.543 | 6.463 | 0.737 | 8.723 |
| 120 | full | 800 | 0.232 | 0.205 | 11.644 | 10.139 | 1.156 | 10.650 |
| 120 | full | 600 | 0.483 | 0.395 | 18.154 | 7.781 | 0.887 | 12.896 |
| 120 | full | 400 | 0.476 | 0.449 | 5.699 | 14.151 | 1.614 | 18.270 |
| 120 | full | 300 | 0.707 | 0.666 | 5.838 | 21.137 | 2.410 | 26.423 |
| 120 | full | 200 | 1.076 | 1.232 | -14.564 | 45.681 | 5.209 | 45.578 |
| 120 | end15cm | 100 | 1.257 | 2.356 | -87.488 | 73.924 | 8.429 | 78.376 |
| 120 | end15cm | 75 | 1.609 | 2.849 | -77.002 | 89.154 | 10.166 | 95.555 |
| 120 | end15cm | 50 | 2.456 | 2.413 | 1.764 | 81.181 | 9.257 | 92.104 |
| 120 | end15cm | 30 | 8.666 | 8.710 | -0.504 | 132.267 | 15.082 | 52.402 |
| 120 | end5cm | 30 | 0.421 | 3.282 | -679.334 | 63.917 | 7.288 | 152.812 |
| 120 | end5cm | 20 | 0.697 | 4.854 | -596.465 | 79.373 | 9.051 | 91.441 |
| 120 | end5cm | 15 | 1.103 | 4.774 | -332.674 | 70.870 | 8.081 | 41.802 |
| 240 | full | 2000 | 1.830 | 1.813 | 0.955 | 17.874 | 2.038 | 17.020 |
| 240 | full | 1500 | 2.061 | 2.041 | 0.963 | 32.152 | 3.666 | 19.298 |
| 240 | full | 1000 | 3.140 | 3.102 | 1.208 | 48.952 | 5.582 | 31.759 |
| 240 | full | 800 | 3.358 | 3.302 | 1.667 | 78.656 | 8.969 | 39.401 |
| 240 | full | 600 | 4.369 | 4.296 | 1.679 | 118.316 | 13.491 | 51.428 |
| 240 | full | 400 | 6.418 | 6.325 | 1.447 | 208.179 | 23.738 | 77.988 |
| 240 | full | 300 | 8.720 | 8.665 | 0.631 | 319.551 | 36.437 | 109.037 |
| 240 | full | 200 | 13.023 | 13.023 | -0.002 | 473.890 | 54.035 | 127.881 |
| 240 | end15cm | 100 | 7.661 | 7.637 | 0.312 | 179.202 | 20.434 | 146.184 |
| 240 | end15cm | 75 | 9.405 | 9.274 | 1.394 | 205.185 | 23.396 | 148.801 |
| 240 | end15cm | 50 | 11.079 | 10.455 | 5.631 | 195.919 | 22.340 | 57.904 |
| 240 | end15cm | 30 | 9.029 | 7.815 | 13.454 | 47.011 | 5.360 | 154.684 |
| 240 | end5cm | 30 | 0.702 | 0.606 | 13.668 | 5.915 | 0.674 | 20.359 |
| 240 | end5cm | 20 | 0.949 | 1.337 | -40.884 | 21.057 | 2.401 | 45.081 |
| 240 | end5cm | 15 | 1.423 | 1.587 | -11.499 | 24.503 | 2.794 | 62.704 |

## Shared score evidence

- source: `E:\shape_exp\支气管镜代码\calibration_results\06B6_NeTi_v2_ftube-20260915T171510+0800-direct0-ff2631\results.json`
- failures: `[]`
