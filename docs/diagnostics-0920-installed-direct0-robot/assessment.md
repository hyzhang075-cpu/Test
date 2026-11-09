# Installed direct-0 end5cm dynamic replay assessment

## Scope

This is an offline replay of `机械臂控制导管末端180度弯折.pkl` with
`params/06B6_NeTi_v2_ftube_nophase_installed_endweights_direct0_demo.json`.
The integrated curvature angle is a reconstruction diagnostic; the recording
does not contain mechanical ground truth.

## Replay result

| Variant | Peak scalar tail integral | Frames over 180 deg | Post-peak mean |
|---|---:|---:|---:|
| Current weights and slopes | 618.545 deg | 25.010% | 153.553 deg |
| All end5 weights = 1 | 156.393 deg | 0% | 63.751 deg |
| Slopes = 0 | 618.708 deg | 25.006% | 153.544 deg |
| Virtual tip curvature = 0 | 595.057 deg | 24.858% | 150.225 deg |
| Uncovered weight levels fixed to 1 | 163.960 deg | 0% | 76.647 deg |
| Internal uncovered runs interpolated; uncovered edge fixed to 1 | 162.483 deg | 0% | 78.304 deg |

The large over-bend is caused by weight amplification. Slope compensation has
negligible influence on its magnitude, and copying curvature to the virtual tip
is a secondary contribution.

## Unidentified and weakly identified parameters

The following levels have no static calibration sample with meaningful mass and
were fixed to one in the diagnostic candidate:

- group 0 (points 19-20): levels 3, 4, 9
- group 1 (point 21): levels 2, 3, 4, 8
- group 2 (point 22): levels 7, 8

At the overall dynamic peak, group 0 used level 9 at approximately weight 5,
point 21 used group 1 level 8 at approximately weight 5, and point 22 used
group 2 level 7 at weight 3.961. All three levels lacked static identification.

Group 2 levels 2 and 3 are a separate case. They are weakly or singly covered,
and the R50 sample requires a gain of about 8.90, outside the configured upper
bound of 5. Their boundary values are driven by conflicting data rather than a
completely empty score interval.

## Recommended optimizer changes

1. Compute score-mass coverage before optimization for every group and level.
2. Remove completely uncovered weights from the optimization vector and hold
   them at the neutral value 1.0.
3. Apply a neutral prior and adjacent-level smoothness penalty to weakly covered
   levels. Do not solve lack of identification by increasing the global upper
   bound.
4. Reject or flag an optimization result when an upper-bound weight has less
   than one effective calibration sample.
5. Reduce or relocate group-specific thresholds so every free parameter has a
   minimum amount of calibration support. With fourteen static states, ten free
   levels per group are excessive unless interpolation/regularization ties the
   levels together.
6. Add a data-consistency gate. The installed data are not monotonic in radius;
   for example point 22 has base magnitude 8.882 at R1500 but 2.246 at R50.
   A memoryless weight curve cannot map these observations to both theoretical
   curvatures. Use a robust loss with a curvature denominator floor, and report
   incompatible samples instead of forcing coefficients to their bounds.

The JSON candidate in this directory is diagnostic only and is marked as not
for deployment.

## Interpolation alternative

Interpolation is reasonable for internal gaps when both surrounding levels are
identified. Consecutive missing levels must be filled together between the
nearest supported levels; repeated pairwise averaging would depend on fill
order. An uncovered end level has no two-sided interpolation and retains the
neutral value 1.0 in the diagnostic candidate. The replay result is essentially
the same as the all-neutral uncovered policy: 162.483 versus 163.960 degrees,
with no frame above 180 degrees. Because weights are multiplicative gains and
threshold spacing is unequal, a production implementation should interpolate
log(weight) by actual threshold coordinate, not take an unqualified arithmetic
mean by level index.
