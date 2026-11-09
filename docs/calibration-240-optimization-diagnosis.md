# 240° optimization diagnosis (2026-09-15)

## Evidence from the existing run

Source: `calibration_results/06B6_NeTi_v2_centraltube-20260913T152029Z-8a1a2a/results.json`.

| region | slopes stage | weights stage | weight bound hits | slope evidence |
|---|---|---|---:|---|
| full | reported `diverge`, loss stayed 0.216652 | reported `diverge`, loss stayed 0.206479 | 0 at 0.6; 0 at 5.0 | initial/final max magnitude 134.945; 6 values exceed configured 50 |
| end15cm | 0.089855 -> 0.024176 | reported `diverge`, loss stayed 0.029006 | 0 at 0.6; 0 at 5.0 | effective search scale became 57.591; 5 values at that scale |
| end5cm | 0.088115 -> 0.034499 | 0.072969 -> 0.045082 | 2 at 0.6; 0 at 5.0 | 12 values at ±50 |

The old `diverge` label did not prove numerical divergence. The optimizer used it
whenever one finite Powell result was worse than the previous loss, then rolled
the parameters back. New runs distinguish finite `no_improvement` from a true
non-finite `diverge` result.

## Root-cause checks

### The configured slope upper bound was not a hard upper bound

Each optimization iteration used
`max(max(abs(current_slopes)), slope_upper_bound)` as its normalization and
search scale. Full/240 entered Powell with an initial slope magnitude of
134.945 rad/m, so the actual search range was ±134.945 rather than ±50.
End15cm similarly used ±57.591. Increasing `slope_upper_bound` from 50 cannot
repair this initialization and would only enlarge the search range once it
exceeds 134.945.

### The large full/240 slopes existed before Powell

The full segmentation ends in two two-point segments with only 11 mm between
their points. Individual fits in the penultimate segment ranged from about
-9.3 to +247.4 rad/m across radii; the last segment ranged from about -192.0 to
+163.0 rad/m. Pooling the inconsistent angles produced initial values of
-134.945 and -28.538 rad/m. Short two-point baselines amplify small curvature
direction errors into very large slopes.

Clipping those initial slopes to ±50 barely changed the full/240 loss
(normal loss 0.206479 -> 0.206488). The bad bound is therefore a symptom and a
conditioning problem, but it is not the main explanation for the 240° error.

### `rot_ang=0` left a common plane-angle error for slopes to absorb

The `optim` task optimizes slopes and then weights; it does not optimize
`rot_ang`. A read-only scan using the same initial parameters found the lowest
tested loss near +30° for all three full calibration directions. For 240°, only
changing `rot_ang` from 0° to +30° reduced normal loss from 0.206479 to
0.110473. Reconstructed 240° curves at `rot_ang=0` retained a large out-of-plane
z component. A common full-sensor rotation reference should therefore be fixed
before the three direction-specific coefficient runs.

### Weight bounds did not cause the failed full/end15cm stages

All full and end15cm weights remained exactly 1.0 and touched neither bound.
Their weight stages inherited unresolved direction/shape errors that scalar
curvature weights cannot correct. End5cm did touch the lower weight bound and
the slope bounds, so that region needs a controlled bounds experiment after the
new 45 m^-1 class is re-optimized; it does not justify changing global defaults
from this run alone.

## Recommended next calibration sequence

1. Determine one common full-sensor `rot_ang` from all 0/120/240 full datasets.
   The current default `ang_range=1` is too narrow for the observed approximate
   +30° offset; scan a wider range and then refine near the minimum.
2. Re-run `task score` after fixing the reference and retain measured regional
   thresholds, including the new 45 m^-1 end5cm threshold.
3. Re-run the three optimization directions with the same verified `rot_ang`.
4. Treat any two-point segment slope estimate as low-confidence. Compare a
   regularized/robust initialization or a local-region seed for the distal
   segments before changing the slope range.
5. Use the saved boundary diagnostics to decide bounds from validation data.
   Test one variable at a time. For end5cm, compare lower weight bounds below
   0.6 only if the new high-curvature levels again hit 0.6; compare slope bounds
   only if validation improves rather than merely allowing larger coefficients.

New result directories use
`<sensor>-<local timestamp with UTC offset>-direct<angle>-<collision suffix>`, for example
`06B6_NeTi_v2_centraltube-20260915T170000+0800-direct240-a1b2c3`.
Each new `results.json` also records weight and slope boundary diagnostics under
`regions.<region>.optimization.parameter_bounds`.
