# Direction-only spatial smoothing

Branch: `dev-entrylimit-reducefilter`

The vector reconstruction path uses the input magnitude (or ideal magnitude during
calibration), not the Kalman output. A moving average of curvature components now
provides only a candidate direction. Original sensor magnitudes are restored before
component PCHIP/linear interpolation. No previous-frame state is required.

`_smooth_curvature_direction` uses resultant length divided by mean magnitude as
direction coherence. Smoothstep transitions from the original direction to the
candidate between coherence 0.25 and 0.75. Corrections taper back to the original
direction between 150 and 180 degrees to protect the antipodal branch. These are
initial tunable constants, not experimentally calibrated thresholds. Numerically
zero resultants fall back to the original direction. This retains ambiguity rather
than inventing a direction when neighbors conflict.

Validation:

- `python -m pytest tests -q`: 70 passed.
- New tests cover node magnitude preservation, no curvature spreading into zero
  nodes, low-curvature direction correction, cancellation, antipodal fallback,
  repeatable single-frame evaluation, no-window behavior, angular branch handling,
  continuous gating, and unchanged ideal magnitudes/inputs.
- Both September 3 recordings were replayed from saved magnitude/angle using the
  production numerical methods and 60-point PCHIP. All 13,240 + 20,227 frames
  produced finite curvature and angle outputs. Maximum sensor magnitude recovery
  errors were respectively 7.11e-15 and 3.55e-15 inverse meters.

Limits: sensor magnitude preservation is not a guarantee of pointwise interpolated
magnitude preservation, nor of physical radius accuracy. Component interpolation,
finite integration resolution, input strain anomalies, and calibration errors remain.
Static optimization uses the same stateless helper; the calibration optimizer itself
has not been rerun. Historical recordings and their diagnostic reports are unchanged.
