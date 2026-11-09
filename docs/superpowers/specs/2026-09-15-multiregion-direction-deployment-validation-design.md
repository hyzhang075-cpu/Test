# Multi-region direction deployment validation design

## Goal

Replace the package-wide provisional deployment gate with evidence-based,
per-direction gates. The validation must respect the physical twist of the
fibre, use the existing calibration replay data, and allow single-direction
demo reconstruction when that direction is deployable.

The validated sensor package remains self-contained: it records the shared
score evidence, phase-transport evidence, full-geometry replay metrics, the
decision for every direction, and the policy that produced those decisions.

## Phase-reference model

The independently initialized `full`, `end15cm`, and `end5cm`
`global_phases_set` values are local coordinate references. They are not
expected to be numerically equal because the fibre twists along the sensor.

For each direction and replay sample, validation will reproduce the full
region score calculation and obtain the full region's pointwise, mass-blended
`slope_map`. It will then use the same discrete integration convention as
`Initialiser._calculate_dynamic_angles` to transport the full phase from the
first global sensing point to each regional start point:

```
predicted_phase(s_b) = wrap(full_global_phase + integral(full_slope_map, s_0, s_b))
phase_error = abs(wrap(predicted_phase(s_b) - local_global_phase))
```

The comparison is made before `rot_ang` because it concerns fibre-channel
azimuth, not the external reconstruction frame. Circular differences are
reported in degrees.

The end15cm start is global point 16 at 0.755 m. Its worst replay-sample phase
error must be at most 30 degrees for `end15cm_phase_verified` to pass for that
direction. The end5cm start is global point 19 at 0.834 m. Its error is
computed and reported with `within_30_deg`, but it is informational and never
blocks deployment because the final 5 cm twist is not mechanically stable.

## Shared score-threshold gate

The score result
`calibration_results/06B6_NeTi_v2_ftube-20260915T171510+0800-direct0-ff2631`
is shared evidence for all directions because thresholds are shared by the
directions within each region.

The score gate passes only when:

- the result is for the same sensor and has `task=score`;
- all `full`, `end15cm`, and `end5cm` score regions are complete;
- each region's thresholds exactly match the candidate package;
- score magnitudes and sigmoid widths are finite;
- the observed distribution crosses every configured threshold, so every
  boundary has empirical support.

The package records the source path, its thresholds, distribution summaries,
sigmoid width, and the resulting shared gate. It does not require separate
score runs for 120 and 240 degrees.

## Calibration replay

Independent validation data is not required. Full-geometry validation replays
the existing calibration measurements through one 22-point reconstruction.

For local experiments, the validator starts with the direction-matched full
straight frame and replaces the local global point IDs with the corresponding
end15cm or end5cm measurement. It uses the candidate package's global point
mapping and one consistent zero-reference treatment.

Each direction is evaluated with both configurations:

- full-only parameters, as the baseline;
- multi-region pointwise parameter assembly, as the candidate.

The replay matrix is:

- full: 2000, 1500, 1000, 800, 600, 400, 300, and 200 mm;
- end15cm: 100, 75, 50, and 30 mm;
- end5cm: 30, 20, and 15 mm.

Position errors are reported in millimetres and as a percentage of the full
0.877 m sensor length. Local-region errors do not use 0.15 m or 0.05 m as the
normalization denominator.

For every sample, the report contains:

- mean and maximum point-position error;
- evaluated-tail mean point error;
- tip-position error;
- tip-tangent error;
- multi-region change relative to full-only;
- curvature-vector and curvature-angle changes across points 15 to 16 and
  points 18 to 19;
- tangent-increment change at both boundaries.

The default validation policy is stored in the report and package rather than
being hidden in code:

- full mean point error at most 1.0% of full sensor length;
- multi-region full replay regression at most 0.2 percentage points compared
  with full-only;
- 30/20/15 mm tail mean error improves by at least 10% compared with
  full-only;
- tip-position error at most 1.0% of full sensor length;
- tip-tangent error at most 10 degrees;
- boundary curvature-angle jump at most 30 degrees;
- end15cm transported-phase error at most 30 degrees.

The CLI exposes these policy values so a changed acceptance policy is explicit
and recorded. A failed metric keeps only the affected direction unavailable.

## Direction-level deployment state

The package gains this structure:

```json
{
  "multi_region": {
    "shared_quality_gates": {
      "score_thresholds_verified": true
    },
    "direction_deployment": {
      "0": {
        "deployment_ready": true,
        "quality_gates": {
          "optimization_usable": true,
          "end15cm_phase_verified": true,
          "full_geometry_verified": true
        },
        "phase_transport": {
          "end15cm": {},
          "end5cm": {"blocking": false}
        }
      }
    },
    "available_deployment_directions": [0],
    "deployment_ready": true
  }
}
```

`optimization_usable` is evaluated per direction. A `no_improvement` stage
therefore does not affect other directions. It remains a blocking optimization
condition for that direction unless the policy is changed explicitly.

When `direction_blend_enabled` is false, package-level `deployment_ready`
equals the status of `direction_reference_direct`. When blending is enabled,
all directions used by the current three-anchor blend must be deployable.
Runtime loading reports the precise failed direction and gate.

## Commands and artifacts

The candidate package is first generated as it is today. Validation is then
run with:

```powershell
python tools/calibration_validation.py `
  --sensor-params params/06B6_NeTi_v2_ftube_multi_region.json `
  --score-results calibration_results/06B6_NeTi_v2_ftube-20260915T171510+0800-direct0-ff2631 `
  --json-output docs/06B6_NeTi_v2_ftube-multiregion-validation.json `
  --markdown-output docs/06B6_NeTi_v2_ftube-multiregion-validation.md `
  --package-output params/06B6_NeTi_v2_ftube_multi_region_validated.json
```

The source candidate is preserved. The final argument writes a separate,
atomically generated validated package. Demo deployment then uses the validated
file. If validation fails, the file is still written with the full evidence
and `deployment_ready=false` for the affected directions.

## Implementation boundaries

`tools/calibration_validation.py` owns score-evidence validation, phase transport,
replay metrics, gate decisions, and report generation.
`tools/sensor_parameter_package.py` owns package schema validation and immutable
application of validation evidence. `main.py` and `demonstrator.py` consume the
per-direction deployment state and enforce the selected runtime mode.

Unit tests cover circular phase differences, exact slope integration,
non-blocking end5cm diagnostics, shared score validation, per-direction gate
aggregation, and package-level single/blended direction rules. Integration
tests replay small synthetic region fixtures and verify that one failed
direction does not block an independently deployable direction.
