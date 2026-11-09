# Multi-region Direction Deployment Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate a multi-region sensor package from calibration replay, record deployability per direction, and allow demo to use one validated reference direction.

**Architecture:** `tools/calibration_validation.py` computes shared score evidence, full-to-local phase transport, full-only versus multi-region replay metrics, and per-direction decisions. `tools/sensor_parameter_package.py` applies that evidence immutably and computes runtime-aware package readiness. `main.py` passes multi-region packages into both recon and demo, while `demonstrator.py` supplies the selected direction to reconstruction.

**Tech Stack:** Python 3, NumPy, argparse, JSON, pytest

**Spec:** `docs/superpowers/specs/2026-09-15-multiregion-direction-deployment-validation-design.md`

## Global Constraints

- End15cm transported-phase error blocks its direction at more than 30 degrees.
- End5cm transported-phase error is always diagnostic and never blocks deployment.
- The direct-0 score result is shared threshold evidence for all directions.
- Full-geometry verification uses calibration replay only; independent validation data is not required.
- All position percentages use the full 0.877 m sensor length.
- Single-direction demo readiness follows `direction_reference_direct`; three-anchor blending requires every participating direction.
- Preserve the user's existing `main.py` and `.gitignore` changes and commit only intentional hunks.

---

### Task 1: Direction-aware package gate schema

**Files:**
- Modify: `tools/sensor_parameter_package.py:134-286`
- Modify: `tools/sensor_parameter_package.py:418-449`
- Test: `tests/test_sensor_parameter_package.py`

**Interfaces:**
- Produces: `direction_optimization_status(reports: list[dict]) -> dict[str, dict]`
- Produces: `apply_validation_results(package: dict, validation: dict) -> dict`
- Produces: `package_deployment_ready(package: dict) -> bool`
- Consumes: validation report fields defined in Task 3.

- [ ] **Step 1: Write failing schema tests**

Add tests asserting that a 240-degree `no_improvement` result makes only
`direction_deployment["240"].quality_gates.optimization_usable` false, while
0 and 120 remain true. Add one single-direction test with
`direction_blend_enabled=False`, `direction_reference_direct=0`, and only
direction 0 fully passing. Add one blended test requiring all three directions.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
python -m pytest tests/test_sensor_parameter_package.py -q
```

Expected: failures because `direction_deployment` and
`shared_quality_gates` do not exist.

- [ ] **Step 3: Implement candidate direction gates**

Build this stable candidate shape for all `0`, `120`, and `240` keys:

```python
direction_deployment[str(direct)] = {
    'deployment_ready': False,
    'quality_gates': {
        'optimization_usable': not failures_for_direct,
        'end15cm_phase_verified': False,
        'full_geometry_verified': False,
    },
    'failures': failures_for_direct,
}
```

Replace the old package-wide optimization gate with
`shared_quality_gates.score_thresholds_verified=False`. Preserve legacy gate
fields only when loading older format-version packages; new packages use the
direction schema.

- [ ] **Step 4: Implement immutable evidence application and aggregation**

`apply_validation_results` must copy the package, validate that evidence
contains every configured direction, copy shared score and per-direction
evidence, recompute each direction's `deployment_ready`, populate
`available_deployment_directions`, and compute package readiness as:

```python
if direction_blend_enabled:
    ready = all(direction_ready[d] for d in directions)
else:
    ready = direction_ready[str(direction_reference_direct)]
```

- [ ] **Step 5: Run tests and commit**

Run the focused tests, then:

```powershell
git add tools/sensor_parameter_package.py tests/test_sensor_parameter_package.py
git commit -m "feat: track deployment readiness by direction"
```

### Task 2: Shared score and phase-transport evidence

**Files:**
- Modify: `tools/calibration_validation.py:1-105`
- Test: `tests/test_calibration_validation.py`

**Interfaces:**
- Produces: `circular_angle_error_deg(actual: float, expected: float) -> float`
- Produces: `integrate_phase_to_point(global_phase: float, distances, slope_map, point_index: int) -> float`
- Produces: `validate_score_evidence(package: dict, score_report: dict, source_path: str) -> dict`
- Produces: `phase_transport_evidence(full, frame, direct: int, local_phases: dict) -> dict`

- [ ] **Step 1: Write failing pure-function tests**

Cover wrapping across `-pi/pi`, exact discrete integration using the receiving
point's slope, an end15cm error of 29.9 degrees passing, an error of 30.1
degrees failing, and end5cm returning `blocking=False` in both cases.

- [ ] **Step 2: Write failing score-evidence tests**

Build a small score report whose sensor ID, task, three region statuses, and
threshold arrays match the package. Assert success with finite distributions
that cross every threshold. Assert clear failures for a mismatched threshold,
missing region, non-finite magnitude, and an uncrossed 45 m^-1 threshold.

- [ ] **Step 3: Run focused tests and verify failure**

```powershell
python -m pytest tests/test_calibration_validation.py -q
```

- [ ] **Step 4: Implement the pure validators**

Use `atan2(sin(delta), cos(delta))` for circular differences. Reuse the exact
distance convention from `_calculate_dynamic_angles`: point zero has zero
increment and interval `i-1 -> i` uses `slope_map[i]`. Score evidence stores
only native JSON values: source path, thresholds, sigmoid width, per-sample
quantiles, and failures.

- [ ] **Step 5: Run tests and commit**

```powershell
git add tools/calibration_validation.py tests/test_calibration_validation.py
git commit -m "feat: validate score and transported phase evidence"
```

### Task 3: Full-only versus multi-region replay and direction decisions

**Files:**
- Modify: `tools/calibration_validation.py:15-202`
- Test: `tests/test_calibration_validation.py`

**Interfaces:**
- Produces: `DEFAULT_VALIDATION_POLICY: dict`
- Produces: `compute_curve_metrics(..., full_length_m: float) -> dict`
- Produces: `compare_reconstructions(baseline: dict, candidate: dict) -> dict`
- Produces: `evaluate_direction_gates(direction_report: dict, optimization_usable: bool, score_verified: bool, policy: dict) -> dict`
- Produces: `validate_multiregion_package(package_path, score_results, policy=None) -> dict`

- [ ] **Step 1: Add failing normalized-metric and gate tests**

For a 0.877 m ideal length and 8.77 mm error, assert `1.0%`. Add fixtures where
large-radius regression is 0.19 percentage points and 30/20/15 mm improvement
is exactly 10%, then assert pass. Change each value just beyond its limit and
assert the named failure appears only for that direction.

- [ ] **Step 2: Add failing boundary-output tests**

Assert reports include curvature-vector jump, wrapped curvature-angle jump in
degrees, and tangent-increment jump in degrees for `15->16` and `18->19`.

- [ ] **Step 3: Run focused tests and verify failure**

```powershell
python -m pytest tests/test_calibration_validation.py -q
```

- [ ] **Step 4: Implement paired reconstruction replay**

Create one full-only and one multi-region `Optimiser` per direction source.
For each sample, reconstruct identical 22-point frames with both parameter
sets. For local samples, insert local processed strain at its global point IDs
into the direction-matched full straight frame. Record both metric sets and
candidate-minus-baseline deltas.

- [ ] **Step 5: Implement per-direction gate evaluation**

Apply the policy stored in the spec. Use all full radii for absolute accuracy
and regression, the 30/20/15 mm set for tail improvement, and all samples for
tip and boundary limits. Combine those results with the blocking end15cm phase
gate, shared score gate, and candidate optimization status. Store end5cm phase
under diagnostics only.

- [ ] **Step 6: Run tests and commit**

```powershell
git add tools/calibration_validation.py tests/test_calibration_validation.py
git commit -m "feat: gate directions from full geometry replay"
```

### Task 4: Validation CLI, reports, and validated package output

**Files:**
- Modify: `tools/calibration_validation.py:204-245`
- Modify: `tools/sensor_parameter_package.py:402-414`
- Test: `tests/test_calibration_validation.py`
- Test: `tests/test_sensor_parameter_package.py`

**Interfaces:**
- CLI consumes: `--sensor-params`, `--score-results`, `--json-output`,
  `--markdown-output`, `--package-output`, plus explicit policy overrides.
- Produces: JSON evidence report, Markdown comparison, and atomically written
  validated package.

- [ ] **Step 1: Write failing CLI/output tests**

Patch replay computation with deterministic evidence and invoke `main(argv)`.
Assert all three artifacts are written, the source package is unchanged, the
validated package embeds evidence, and failed output is still written with
the correct false direction state.

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
python -m pytest tests/test_calibration_validation.py tests/test_sensor_parameter_package.py -q
```

- [ ] **Step 3: Implement CLI and Markdown tables**

Accept a score directory or `results.json`, resolve it the same way as optim
result inputs, expose the seven numeric policy values from the spec, and write
files via sibling `.tmp` followed by `Path.replace`. Markdown must include a
direction gate table, phase table, score summary, and paired reconstruction
metrics.

- [ ] **Step 4: Run tests and commit**

```powershell
git add tools/calibration_validation.py tools/sensor_parameter_package.py tests/test_calibration_validation.py tests/test_sensor_parameter_package.py
git commit -m "feat: export validated multi-region packages"
```

### Task 5: Recon and demo runtime enforcement

**Files:**
- Modify: `main.py:1-100`
- Modify: `main.py` task dispatch near `main()`
- Modify: `demonstrator.py:1030-1180`
- Test: `tests/test_calibration_regions.py`
- Test: `tests/test_vector_filter_configuration.py`
- Test: `tests/test_multiregion_reconstruction.py`

**Interfaces:**
- Consumes: `package_deployment_ready(package)` and
  `multi_region.direction_deployment` from Task 1.
- Produces: demo calls `_reconstruct_frame(..., direct=selected_direct)` and
  accepts differing regional threshold/weight/slope shapes.

- [ ] **Step 1: Add failing recon/demo configuration tests**

Assert both `task=recon` and `task=demo` attach `multi_region_parameters` when
`multi_region_calib=True`. Assert single-direction demo accepts a validated
reference direction even when 240 fails. Assert blending rejects a package
unless all anchor directions pass. Assert the selected literal angle is passed
as `direct`, never converted to 0/1/2.

- [ ] **Step 2: Run focused tests and verify failure**

```powershell
python -m pytest tests/test_calibration_regions.py tests/test_vector_filter_configuration.py tests/test_multiregion_reconstruction.py -q
```

- [ ] **Step 3: Implement runtime configuration and demo reconstruction**

Load the regional package for both tasks. In single-direction mode bypass
cross-direction array blending and pass `direction_reference_direct` directly
to multi-region reconstruction, which performs each region's own threshold and
mass calculation. In blended mode reject unavailable directions until
region-wise direction blending is supported safely.

- [ ] **Step 4: Run tests and commit intentional hunks only**

Because `main.py` contains user changes, inspect `git diff main.py` and stage
only the runtime hunks with `git add -p main.py`. Then stage the remaining
files and commit:

```powershell
git add demonstrator.py tests/test_calibration_regions.py tests/test_vector_filter_configuration.py tests/test_multiregion_reconstruction.py
git commit -m "feat: use validated multi-region parameters in demo"
```

### Task 6: Real calibration replay and regression verification

**Files:**
- Generate: `docs/06B6_NeTi_v2_ftube-multiregion-validation.json`
- Generate: `docs/06B6_NeTi_v2_ftube-multiregion-validation.md`
- Generate: `params/06B6_NeTi_v2_ftube_multi_region_validated.json`

**Interfaces:**
- Consumes the candidate package and direct-0 score result named in the spec.
- Produces final evidence and the exact list of deployable directions.

- [ ] **Step 1: Run focused regression tests**

```powershell
python -m pytest tests/test_sensor_parameter_package.py tests/test_calibration_validation.py tests/test_calibration_batch.py tests/test_calibration_regions.py tests/test_multiregion_reconstruction.py tests/test_vector_filter_configuration.py -q
```

- [ ] **Step 2: Run the real replay command**

```powershell
python tools/calibration_validation.py --sensor-params params/06B6_NeTi_v2_ftube_multi_region.json --score-results calibration_results/06B6_NeTi_v2_ftube-20260915T171510+0800-direct0-ff2631 --json-output docs/06B6_NeTi_v2_ftube-multiregion-validation.json --markdown-output docs/06B6_NeTi_v2_ftube-multiregion-validation.md --package-output params/06B6_NeTi_v2_ftube_multi_region_validated.json
```

- [ ] **Step 3: Inspect evidence without weakening policy**

Confirm JSON contains finite metrics for every planned direction/region/radius,
end5cm is non-blocking, score evidence is shared, and package readiness matches
the selected direction. If data fails a gate, report the measured failure; do
not change policy merely to obtain `deployment_ready=true`.

- [ ] **Step 4: Run broad relevant tests and inspect the diff**

```powershell
python -m pytest -q
git diff --check
git status --short
```

Document unrelated pre-existing failures separately. Commit only source,
tests, and intentionally versioned validation artifacts.
