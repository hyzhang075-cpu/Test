# Multi-region measured score analysis (2026-09-14)

This report uses the production `Reconstructor._get_base()`, `_get_scores()` and
`_alloc_mass()` path. `score_magnitude` is the strain-estimated base curvature
before weight compensation with `magnitude_ratio=1.0`; theoretical radius is
recorded only as experiment metadata.

## Source runs

| direct | result |
|---:|---|
| 0 | `calibration_results/06B6_NeTi_v2_centraltube-20260914T071556Z-3d1474/results.json` |
| 120 | `calibration_results/06B6_NeTi_v2_centraltube-20260914T071736Z-8cb097/results.json` |
| 240 | `calibration_results/06B6_NeTi_v2_centraltube-20260914T071907Z-19c68e/results.json` |

All three runs completed `full`, `end15cm`, and `end5cm`. The configured
sigmoid sharpness was 4.8, giving a 10–90% transition width of
0.9155 m^-1. The spatial score window was 3 points with constant boundaries.

## End-5-cm high-curvature measurements

Values are measured base-curvature p10 / median / p90 in m^-1. “Dominant” is
the level with the largest mean probability mass under the current thresholds
`[0.8, 1.2, 2, 3, 4, 8, 20, 35]`.

| direct | radius | p10 | median | p90 | dominant level |
|---:|---:|---:|---:|---:|---:|
| 0 | 30 mm | 14.01 | 25.78 | 29.81 | 7 |
| 0 | 20 mm | 16.12 | 31.92 | 39.61 | 8 |
| 0 | 15 mm | 17.25 | 34.35 | 47.34 | 8 |
| 120 | 30 mm | 18.03 | 29.63 | 33.88 | 7 |
| 120 | 20 mm | 22.26 | 39.26 | 45.69 | 8 |
| 120 | 15 mm | 22.43 | 41.16 | 55.51 | 8 |
| 240 | 30 mm | 14.50 | 25.04 | 29.32 | 7 |
| 240 | 20 mm | 17.91 | 33.16 | 41.93 | 8 |
| 240 | 15 mm | 18.61 | 35.61 | 52.81 | 8 |

The current final class saturates for both 20 and 15 mm in every direction.
Their medians differ by only 1.90–2.45 m^-1 and their point distributions
overlap strongly. Narrowing the sigmoid cannot remove that overlap: its current
0.9155 m^-1 transition width is already smaller than the median gaps.

For the next end5cm optimization, use thresholds
`[0.8, 1.2, 2, 3, 4, 8, 20, 35, 45]` and retain sharpness 4.8. The added
45 m^-1 transition can distinguish the high-curvature points present mainly in
the 15 mm experiments while preserving the existing 35 m^-1 split between
30 and 20 mm. The new threshold count requires 10 weights and a `10 x 2` slope
matrix for each direction.

This is a re-optimization configuration. The current candidate package contains
the old eight thresholds, nine weights, and `9 x 2` slopes, so its
`score_verified` gate remains false. Those coefficients must not be loaded with
the nine-threshold parser profile. Deployment also remains blocked by the
independent 240-degree optimization failures and full-geometry/phase gates.
