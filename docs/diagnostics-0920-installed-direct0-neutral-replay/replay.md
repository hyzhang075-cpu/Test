# end5cm groupwise-weight offline replay

## Reference: existing scoring logic

Existing behavior: one spatial-window score/mass field drives both slope and weight selection; legacy packages without weight_score_mode stay on this path.

## Groupwise replay definition

Point 19/20 share the arithmetic mean of their pre-weight base magnitude; points 21 and 22 score independently; slope scoring remains spatial_window.

Integrated curvature is accumulated turning from the reconstructed curvature field, not a ground-truth mechanical angle error.

## Summary

| recording | variant | max scalar tail integral (deg) | max vector tail integral (deg) | max curvature (1/m) | >180° frames | post-peak scalar residual (deg) | post-peak vector residual (deg) |
|---|---|---:|---:|---:|---:|---:|---:|
| 机械臂控制导管末端180度弯折.pkl | original_weights_slopes | 163.960 | 158.482 | 86.891 | 0.000% | 76.647 | 75.978 |
| 机械臂控制导管末端180度弯折.pkl | weights_one | 156.393 | 150.733 | 84.198 | 0.000% | 63.751 | 63.025 |
| 机械臂控制导管末端180度弯折.pkl | slopes_zero | 164.186 | 163.433 | 86.887 | 0.000% | 76.634 | 75.590 |
| 机械臂控制导管末端180度弯折.pkl | virtual_tip_zero | 156.599 | 153.101 | 86.891 | 0.000% | 74.052 | 73.578 |
