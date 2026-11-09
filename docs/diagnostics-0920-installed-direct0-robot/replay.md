# end5cm groupwise-weight offline replay

## Reference: existing scoring logic

Existing behavior: one spatial-window score/mass field drives both slope and weight selection; legacy packages without weight_score_mode stay on this path.

## Groupwise replay definition

Point 19/20 share the arithmetic mean of their pre-weight base magnitude; points 21 and 22 score independently; slope scoring remains spatial_window.

Integrated curvature is accumulated turning from the reconstructed curvature field, not a ground-truth mechanical angle error.

## Summary

| recording | variant | max scalar tail integral (deg) | max vector tail integral (deg) | max curvature (1/m) | >180° frames | post-peak scalar residual (deg) | post-peak vector residual (deg) |
|---|---|---:|---:|---:|---:|---:|---:|
| 机械臂控制导管末端180度弯折.pkl | original_weights_slopes | 618.545 | 617.994 | 406.714 | 25.010% | 153.553 | 152.166 |
| 机械臂控制导管末端180度弯折.pkl | weights_one | 156.393 | 150.733 | 84.198 | 0.000% | 63.751 | 63.025 |
| 机械臂控制导管末端180度弯折.pkl | slopes_zero | 618.708 | 617.633 | 406.898 | 25.006% | 153.544 | 152.150 |
| 机械臂控制导管末端180度弯折.pkl | virtual_tip_zero | 595.057 | 594.302 | 406.714 | 24.858% | 150.225 | 149.310 |
