# Multi-region full-geometry validation

- unified global phase: `-0.7058749485849114`
- unified rot_ang: `0.0`
- full geometry verified: `False`

| direct | region | radius (mm) | region point (mm) | isolated point (mm) | delta (mm) | tip position (mm) | tip tangent (deg) |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | full | 2000 | 4.507 | nan | nan | 15.544 | 8.308 |
| 0 | full | 1500 | 4.646 | nan | nan | 19.122 | 9.331 |
| 0 | full | 1000 | 6.279 | nan | nan | 19.092 | 9.345 |
| 0 | full | 800 | 6.835 | nan | nan | 23.788 | 8.933 |
| 0 | full | 600 | 8.401 | nan | nan | 26.103 | 9.930 |
| 0 | full | 400 | 11.067 | nan | nan | 34.283 | 13.437 |
| 0 | full | 300 | 12.842 | nan | nan | 35.156 | 13.939 |
| 0 | full | 200 | 14.570 | nan | nan | 30.135 | 12.112 |
| 0 | end15cm | 100 | 8.349 | 15.293 | -6.945 | 17.350 | 26.678 |
| 0 | end15cm | 75 | 9.177 | 17.281 | -8.105 | 18.313 | 38.367 |
| 0 | end15cm | 50 | 14.104 | 16.235 | -2.131 | 25.302 | 61.846 |
| 0 | end15cm | 30 | 13.538 | 37.148 | -23.610 | 50.049 | 91.406 |
| 0 | end5cm | 30 | 9.741 | 43.297 | -33.556 | 16.874 | 25.354 |
| 0 | end5cm | 20 | 13.428 | 90.139 | -76.711 | 20.183 | 33.796 |
| 0 | end5cm | 15 | 13.022 | 90.627 | -77.605 | 19.367 | 68.649 |
| 120 | full | 2000 | 2.758 | nan | nan | 4.082 | 1.361 |
| 120 | full | 1500 | 1.823 | nan | nan | 6.268 | 2.306 |
| 120 | full | 1000 | 2.380 | nan | nan | 3.736 | 2.599 |
| 120 | full | 800 | 3.240 | nan | nan | 7.828 | 3.184 |
| 120 | full | 600 | 6.653 | nan | nan | 16.427 | 4.300 |
| 120 | full | 400 | 6.901 | nan | nan | 15.661 | 8.483 |
| 120 | full | 300 | 8.610 | nan | nan | 12.470 | 9.997 |
| 120 | full | 200 | 8.515 | nan | nan | 8.037 | 12.805 |
| 120 | end15cm | 100 | 13.180 | 6.354 | 6.826 | 26.406 | 15.448 |
| 120 | end15cm | 75 | 17.054 | 10.363 | 6.691 | 31.860 | 25.678 |
| 120 | end15cm | 50 | 47.704 | 290.083 | -242.379 | 92.346 | 139.855 |
| 120 | end15cm | 30 | 64.922 | 443.623 | -378.701 | 104.025 | 119.735 |
| 120 | end5cm | 30 | 20.153 | 105.726 | -85.573 | 44.638 | 91.724 |
| 120 | end5cm | 20 | 25.740 | 173.551 | -147.811 | 50.763 | 76.984 |
| 120 | end5cm | 15 | 25.724 | 185.627 | -159.903 | 46.807 | 58.298 |
| 240 | full | 2000 | 27.981 | nan | nan | 113.875 | 20.926 |
| 240 | full | 1500 | 36.108 | nan | nan | 155.134 | 32.013 |
| 240 | full | 1000 | 55.737 | nan | nan | 230.022 | 45.696 |
| 240 | full | 800 | 70.373 | nan | nan | 293.259 | 58.492 |
| 240 | full | 600 | 94.819 | nan | nan | 382.749 | 78.245 |
| 240 | full | 400 | 133.646 | nan | nan | 514.572 | 106.007 |
| 240 | full | 300 | 163.430 | nan | nan | 591.796 | 108.997 |
| 240 | full | 200 | 187.314 | nan | nan | 576.310 | 68.024 |
| 240 | end15cm | 100 | 60.132 | 25.802 | 34.329 | 159.333 | 117.457 |
| 240 | end15cm | 75 | 75.023 | 40.349 | 34.674 | 188.313 | 113.890 |
| 240 | end15cm | 50 | 81.533 | 51.245 | 30.288 | 156.744 | 45.668 |
| 240 | end15cm | 30 | 68.631 | 106.703 | -38.072 | 72.494 | 127.167 |
| 240 | end5cm | 30 | 33.112 | 69.149 | -36.037 | 69.993 | 141.643 |
| 240 | end5cm | 20 | 41.271 | 156.612 | -115.341 | 77.746 | 96.031 |
| 240 | end5cm | 15 | 42.214 | 172.347 | -130.133 | 70.656 | 58.918 |

## Gate result

max full mean point error=187.314 mm; max local-test tip tangent error=141.643 deg; max region-boundary phase jump=0.906 rad; source optimization gates include divergence and independent pose ground truth is unavailable

A negative delta means the merged full-length reconstruction reduced the point error relative to the isolated regional reconstruction. It does not override the tip-orientation and boundary-continuity failures.
