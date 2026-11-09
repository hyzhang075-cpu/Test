# end5cm groupwise-weight offline replay

## Reference: existing scoring logic

Existing behavior: one spatial-window score/mass field drives both slope and weight selection; legacy packages without weight_score_mode stay on this path.

## Groupwise replay definition

Point 19/20 share the arithmetic mean of their pre-weight base magnitude; points 21 and 22 score independently; slope scoring remains spatial_window.

Integrated curvature is accumulated turning from the reconstructed curvature field, not a ground-truth mechanical angle error.

## Summary

| recording | variant | max scalar tail integral (deg) | max vector tail integral (deg) | max curvature (1/m) | >180° frames | post-peak scalar residual (deg) | post-peak vector residual (deg) |
|---|---|---:|---:|---:|---:|---:|---:|
| 用手弯曲最后5cm.pkl | original_weights_slopes | 481.212 | 473.659 | 319.065 | 20.538% | 161.535 | 158.611 |
| 用手弯曲最后5cm.pkl | weights_one | 168.983 | 165.950 | 88.058 | 0.000% | 64.773 | 63.398 |
| 用手弯曲最后5cm.pkl | slopes_zero | 481.471 | 481.424 | 319.038 | 20.538% | 161.616 | 160.446 |
| 用手弯曲最后5cm.pkl | virtual_tip_zero | 450.790 | 444.899 | 319.065 | 18.789% | 147.471 | 145.180 |
| 机械臂控制导管末端180度弯折.pkl | original_weights_slopes | 436.550 | 418.694 | 282.000 | 16.823% | 128.763 | 126.930 |
| 机械臂控制导管末端180度弯折.pkl | weights_one | 156.393 | 150.733 | 84.198 | 0.000% | 63.751 | 63.025 |
| 机械臂控制导管末端180度弯折.pkl | slopes_zero | 436.737 | 433.052 | 281.974 | 16.798% | 128.713 | 125.192 |
| 机械臂控制导管末端180度弯折.pkl | virtual_tip_zero | 409.024 | 397.338 | 282.000 | 13.008% | 117.405 | 116.133 |
