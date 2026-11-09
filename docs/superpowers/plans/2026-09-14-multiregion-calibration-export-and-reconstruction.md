# Multi-Region Calibration Export and Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Merge the three direction-specific calibration runs into one ordered sensor package, load it through `main.py`, and reconstruct either one selected calibration region or the complete sensor with region-specific thresholds, weights, and slopes.

**Architecture:** Keep each existing `Optimiser.optim_coeff()` invocation unchanged and add three focused units: a package exporter/loader, a region-aware parameter assembler in `Reconstructor`, and an offline full-geometry validator. The merged runtime uses one global phase and one rot_ang, computes masses within each region's calibration support, copies only owned points into full-length `final_weight` and `slope_map`, and rejects deployment when phase or optimization quality is unverified.

**Tech Stack:** Python 3, argparse, JSON, NumPy, SciPy, pytest, existing Sensor/Initialiser/Reconstructor/Optimiser classes.

**Spec:** `docs/superpowers/specs/2026-09-14-multiregion-calibration-export-and-reconstruction-design.md`

## Global Constraints

- Work only on branch `dev-entrylimit-reducefilter-multiregion` based on commit `ec0c184f223cb0308dbbf61f7347637a94149e4f` and preserve unrelated user changes.
- Preserve the existing per-region two-stage optimization: slopes with ideal reconstruction magnitude, then weights with measured magnitude.
- Direction identifiers are exactly `0`, `120`, and `240`.
- A full-sensor runtime has exactly one `global_phases_set` and one `rot_ang`; local phases remain provenance until verified.
- Threshold selection uses measured base-curvature score distributions, never theoretical-radius thresholds alone.
- Every parser parameter has one editable authoritative location in the package; `sensor_id` is the first JSON key.
- CLI values explicitly supplied by the user override package defaults; `task` remains required on the CLI.
- Existing single-region reconstruction and legacy weights/slopes remain supported.

---

### Task 1: Calibration result comparison and ordered package exporter

**Files:**
- Create: `tools/sensor_parameter_package.py`
- Create: `tests/test_sensor_parameter_package.py`
- Create: `docs/calibration-results-20260913-comparison.md`
- Modify: `.gitignore` only if the generated candidate package needs an explicit inclusion rule

**Interfaces:**
- Consumes: `build_argument_parser()` and three `results.json` paths.
- Produces: `load_calibration_results(paths: Sequence[Path]) -> dict`, `build_sensor_package(parser, reports: Sequence[dict]) -> dict`, `write_sensor_package(package: dict, path: Path) -> None`, and `load_sensor_package(path: Path, expected_sensor_id: str | None = None) -> dict`.

- [x] **Step 1: Write failing exporter tests**

Create compact result fixtures with full/end15cm/end5cm entries and assert:

```python
def test_package_merges_literal_direction_angles_in_stable_order(tmp_path):
    package = build_sensor_package(parser(), reports_for(0, 120, 240))
    assert list(package)[:3] == ['sensor_id', 'format_version', 'shared_parameters']
    assert package['multi_region']['directions'] == [0, 120, 240]
    assert list(package['regions']['end5cm']['weights']) == ['0', '120', '240']

def test_package_rejects_direction_indices():
    with pytest.raises(ValueError, match='0、120、240'):
        build_sensor_package(parser(), reports_for(0, 1, 2))

def test_current_parser_destinations_have_one_authoritative_package_location():
    package = build_sensor_package(parser(), reports_for(0, 120, 240))
    assert packaged_parser_destinations(package) == parser_destinations(parser())
```

Add tests for mismatched sensor IDs, mismatched region contexts, missing regions, non-finite values, weights length, slopes shape, and duplicate directions.

- [x] **Step 2: Run exporter tests and confirm failure**

Run: `python -m pytest tests/test_sensor_parameter_package.py -q`

Expected: import failure because `tools/sensor_parameter_package.py` does not exist.

- [x] **Step 3: Implement parser grouping and strict report validation**

Define ordered group membership using parser destination names. Keep each name in exactly one group and verify at export time that the union matches every parser action except `help`:

```python
PARSER_GROUPS = {
    'hardware_parameters': (
        'start_value', 'end_value', 'R', 'ideal_len', 'samp_dist_preset',
        'samp_dist_preset_sub', 'centre_fibre', 'interlaced_grating',
        'interlaced_offset',
    ),
    'calibration_experiment_parameters': (
        'interrogator', 'active_channels', 'channel_change', 'channel_layout',
        'active_angles', 'rot_dir', 'exp_directs', 'end_len', 'ss',
    ),
    'optimization_hyperparameters': (
        'freeze', 'weight_bounds', 'slope_upper_bound', 'max_iter', 'k_point',
        'k_end', 'k_pitch', 'k_radius', 'method', 'hyper_params', 'min_loss_diff',
    ),
    'dynamic_display_parameters': (
        'IP', 'PORT', 'maxsize', 'data_freq', 'use_stored_zero',
        'zero_reference_path', 'total_scale', 'imu', 'imu_com', 'imu_maxlen',
        'demo_recorder', 'unwrap_threshold', 'align_threshold',
        'direction_blend_enabled', 'direction_reference_direct',
        'direction_min_curvature', 'direction_min_consecutive',
        'direction_consistency_threshold', 'direction_smooth_alpha',
        'demo_kalman_enabled', 'demo_kalman_Rk', 'demo_kalman_Bk',
        'anchor_translation_enabled', 'anchor_rotation_enabled',
        'anchor_constraint_enabled', 'anchor_offset_m',
    ),
    'reconstruction_parameters': (
        'soft', 'reverse', 'discont', 'frame_rule', 'straight_threshold',
        'rot_threshold', 'min_consecutive', 'move_filter',
        'move_filter_for_vector', 'kalman_params', 'smoothing_params',
        'interp_num', 'curvature_interp', 'nonnegative_curvature', 'sharpness',
        'end_weights', 'end_start', 'TNB_threshold',
    ),
    'initialization_parameters': (
        'connect', 'turn_threshold', 'sensing_ranges',
    ),
    'angle_optimization_parameters': ('ang_step', 'ang_range'),
    'runtime_control_parameters': (
        'multi_region_calib', 'optimization_region', 'optimization_regions',
        'full_segmentation', 'calibration_data_root', 'calibration_output_dir',
        'folder_path', 'radii', 'direct', 'thresholds', 'straight_trim',
        'segmentation', 'weights', 'slopes', 'task',
    ),
}

SPECIAL_PARAMETER_LOCATIONS = {
    'sensor_id': ('sensor_id',),
    'calibration_regions': ('regions',),
    'global_phases_set': ('multi_region', 'global_phases_set'),
    'rot_ang': ('multi_region', 'rot_ang'),
}
```

Move region-specific `folder_path`, `radii`, `thresholds`, `straight_trim`, `segmentation`, `weights`, and `slopes` into region blocks. Move the unified phase and rot_ang into `multi_region`. Record the original ordered parser destinations under provenance without duplicating their values.

- [x] **Step 4: Implement candidate/deployable quality gates**

Return machine-readable gates such as:

```python
{
    'optimization_complete': False,
    'phase_reference_verified': False,
    'score_verified': False,
    'full_geometry_verified': False,
    'failures': [
        '240/full slopes diverged',
        '240/full weights diverged',
        '240/end15cm weights diverged',
        'global phase reference is unverified',
    ],
}
```

Always permit candidate export. Set `deployment_ready=True` only if every required gate is true. A request for strict deployment export raises `ValueError` listing failed gates.

- [x] **Step 5: Export and compare the three supplied results**

Generate `docs/calibration-results-20260913-comparison.md` with weights, slope shapes and values, per-radius point/end errors, stage statuses, boundary hits, phases, and rot_ang. Generate the ordered candidate package at `params/06B6_NeTi_v2_centraltube_multi_region.json`; it must have `deployment_ready=false` for the supplied runs.

- [x] **Step 6: Run tests and commit**

Run: `python -m pytest tests/test_sensor_parameter_package.py tests/test_calibration_batch.py tests/test_calibration_regions.py -q`

Commit only Task 1 files:

```powershell
git add tools/sensor_parameter_package.py tests/test_sensor_parameter_package.py docs/calibration-results-20260913-comparison.md params/06B6_NeTi_v2_centraltube_multi_region.json
git commit -m "feat: export ordered multiregion sensor packages"
```

### Task 2: Package bootstrap loading and single-region recon semantics

**Files:**
- Modify: `main.py`
- Modify: `calibration_regions.py`
- Modify: `calibration_batch.py`
- Modify: `tests/test_calibration_regions.py`
- Modify: `tests/test_calibration_batch.py`
- Modify: `tests/test_sensor_parameter_package.py`

**Interfaces:**
- Consumes: `load_sensor_package()` from Task 1.
- Produces: `parse_main_args(argv: Sequence[str] | None = None) -> argparse.Namespace`, revised `configure_calibration_args(args)`, and package-derived region seeds.

- [x] **Step 1: Write failing parser and local recon tests**

Add tests equivalent to:

```python
@pytest.mark.parametrize('region', ['full', 'end15cm', 'end5cm'])
def test_false_mode_allows_selected_single_region_recon(monkeypatch, region):
    args = parse_main_args(['--task', 'recon', '--multi_region_calib', 'False',
                            '--optimization_region', region])
    context = configure_calibration_args(args)
    assert context['optimization_region'] == region

def test_cli_explicit_value_overrides_package_default(tmp_path):
    args = parse_main_args(['--task', 'recon', '--sensor_params', str(package_path),
                            '--move_filter', '5'])
    assert args.move_filter == 5
```

Also assert that task is still required, sensor ID conflicts fail, package values survive JSON list/tuple conversion, and unknown format versions fail before Optimiser creation.

- [x] **Step 2: Run focused tests and confirm failures**

Run: `python -m pytest tests/test_calibration_regions.py tests/test_sensor_parameter_package.py -q`

Expected: local region rejection and missing `parse_main_args`/`--sensor_params` behavior.

- [x] **Step 3: Implement two-phase CLI parsing**

Add a bootstrap parser for `--sensor_params` and `--sensor_id`, load the package, build the full parser, apply package defaults, then parse the complete CLI. Preserve explicit CLI precedence and prevent a packaged task from satisfying the required `--task` argument.

- [x] **Step 4: Revise regional selection semantics**

Remove the resolver rule that false mode permits only full. In `prepare_calibration_jobs`, keep false mode as `[optimization_region]` and true mode as `optimization_regions`. For recon, false mode selects one region; true mode requires a complete multi-region package and full geometry.

- [x] **Step 5: Load selected region parameters for local recon**

Convert JSON direction keys back to integer angles and NumPy arrays, populate the selected region's thresholds/segmentation/weights/slopes, and pass them through existing `validate_calibration_parameters()`.

- [x] **Step 6: Run regression tests and commit**

Run:

```powershell
python -m pytest tests/test_vector_filter_configuration.py tests/test_calibration_batch.py tests/test_calibration_regions.py tests/test_sensor_parameter_package.py -q
```

Commit:

```powershell
git add main.py calibration_regions.py calibration_batch.py tests/test_calibration_regions.py tests/test_calibration_batch.py tests/test_sensor_parameter_package.py
git commit -m "feat: load sensor packages and select recon regions"
```

### Task 3: Region-aware point parameter assembly

**Files:**
- Modify: `reconstructor.py`
- Create: `tests/test_multiregion_reconstruction.py`
- Modify: `tests/test_vector_filter_configuration.py`

**Interfaces:**
- Consumes: validated `multi_region_parameters` package block from Task 2.
- Produces: `_assemble_multiregion_parameters(strain_data, direct) -> tuple[np.ndarray, np.ndarray, np.ndarray, list]`, returning final magnitude, angle, slope map, and diagnostic region records; legacy `_Strain_2_Cur()` remains callable.

- [x] **Step 1: Write failing assembler tests**

Use a small six-point fixture with three regions having two, three, and four levels. Assert independent thresholds and dimensions:

```python
def test_each_region_uses_its_own_thresholds_weights_and_slopes():
    final_weight, slope_map, diagnostics = assemble(fixture)
    assert final_weight.shape == (6,)
    assert slope_map.shape == (6,)
    assert diagnostics['full']['mass_shape'][0] == 2
    assert diagnostics['end15cm']['mass_shape'][0] == 3
    assert diagnostics['end5cm']['mass_shape'][0] == 4
```

Add tests that support-range scores are calculated before owned-point extraction, every point is owned exactly once, global segment mapping is respected, and directions use 0/120/240.

- [x] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_multiregion_reconstruction.py -q`

Expected: missing multi-region constructor/assembler.

- [x] **Step 3: Add optional constructor input without breaking positional arguments**

Add `multi_region_parameters=None` as a keyword-only parameter after the existing `*args` boundary, or consume it through kwargs without changing tested positional ordering. Normalize and validate it once during construction.

- [x] **Step 4: Extract threshold-parameterized score helpers**

Allow score computation to receive thresholds, sharpness, window size, and boundary mode explicitly while preserving legacy defaults:

```python
def _get_scores(self, magnitude, *, thresholds=None, sharpness=None,
                min_consecutive=None, boundary_mode='constant'):
    thresholds = self.thresholds if thresholds is None else thresholds
    sharpness = self.sharpness if sharpness is None else sharpness
    min_consecutive = self.min_consecutive if min_consecutive is None else min_consecutive
    scores = []
    for threshold in thresholds:
        score = 1.0 / (1.0 + np.exp(-sharpness * (np.asarray(magnitude) - threshold)))
        if min_consecutive > 1:
            score = self._moving_average_scipy(score, min_consecutive, boundary_mode)
        scores.append(score)
    return np.asarray(scores)
```

- [x] **Step 5: Implement base slope and final parameter maps**

Build the base slope per global segment from its owner region's level-zero slope. Compute each region's masses on support points, mix region-specific weights/slopes for the selected literal direction, copy owned points into full arrays, and retain diagnostics for validation. Pass the final arrays into the unchanged strain conversion, interpolation, frame, and integration path.

- [x] **Step 6: Preserve single-region output exactly**

Run legacy and region-aware code with a one-region equivalent package and assert `magnitude`, `angle`, `final_weight`, and `slope_map` are numerically equal.

- [x] **Step 7: Run focused and reconstruction regression tests**

Run:

```powershell
python -m pytest tests/test_multiregion_reconstruction.py tests/test_vector_magnitude_input.py tests/test_vector_filter_configuration.py tests/test_reconstruction_intermediates.py tests/test_reconstructor_end_pose.py -q
```

- [x] **Step 8: Commit**

```powershell
git add reconstructor.py tests/test_multiregion_reconstruction.py tests/test_vector_filter_configuration.py
git commit -m "feat: assemble multiregion reconstruction parameters"
```

### Task 4: Score analysis and measured threshold decision

**Files:**
- Modify: `calibration_batch.py` if combined three-direction summaries are missing
- Create: `tests/test_calibration_score_summary.py`
- Create: `docs/calibration-score-20260914.md`
- Modify: `main.py` region thresholds only if the measured report justifies new values

**Interfaces:**
- Consumes: existing `diagnose_score_distribution(optim)` and the three calibration datasets.
- Produces: `summarize_score_runs(reports: Sequence[dict]) -> dict` and a three-direction threshold recommendation report.

- [x] **Step 1: Write failing score-summary tests**

Assert that summaries preserve direction, region, radius, global point, quantiles, average mass, endpoint mass, and sigmoid 10–90% width. Add a separability flag when adjacent target radii cannot be distinguished by the current highest classes.

- [x] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_calibration_score_summary.py tests/test_calibration_batch.py -q`

- [x] **Step 3: Implement the combined summary**

Keep production `_get_base()`, `_get_scores()`, and `_alloc_mass()` as the source of diagnostic values. Do not derive replacement thresholds from theoretical curvature alone.

- [x] **Step 4: Run score for all directions**

Run each direction with the current package/parser data:

```powershell
python main.py --task score --multi_region_calib True --direct 0
python main.py --task score --multi_region_calib True --direct 120
python main.py --task score --multi_region_calib True --direct 240
```

Summarize the resulting score reports in `docs/calibration-score-20260914.md`.

- [x] **Step 5: Decide whether thresholds/sharpness must change**

If 30/20/15 mm occupy indistinguishable masses, update only the affected region configuration using measured distribution gaps and record the selected values and transition widths. Mark all old optimized parameters for that region incompatible until re-optimization; do not combine new thresholds with old weights/slopes.

- [x] **Step 6: Run tests and commit analysis/code**

Run: `python -m pytest tests/test_calibration_score_summary.py tests/test_calibration_batch.py tests/test_calibration_regions.py -q`

Commit code and analysis. Do not commit large generated plots unless already permitted by repository policy.

### Task 5: Full-geometry offline validation and deployment gate

**Files:**
- Create: `tools/calibration_validation.py`
- Create: `tests/test_calibration_validation.py`
- Create: `docs/calibration-multiregion-validation.json`
- Create: `docs/calibration-multiregion-validation.md`
- Modify: `tools/sensor_parameter_package.py`
- Modify: `params/06B6_NeTi_v2_centraltube_multi_region.json`

**Interfaces:**
- Consumes: candidate package, full 22-point geometry, full/end15cm/end5cm source datasets.
- Produces: `validate_multiregion_package(package, parser_defaults) -> dict` with per-direction/per-region/per-radius errors, boundary diagnostics, and gate results.

- [x] **Step 1: Write failing validation tests**

Use synthetic straight-prefix/circular-tail curves to verify point error, tip position error, tangent angle error, pose error, and boundary metrics. Assert that one failed direction prevents deployment even when aggregate averages pass.

- [x] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_calibration_validation.py -q`

- [x] **Step 3: Implement full-point replay without GUI or hardware**

Construct Sensor/Optimiser inputs with all 22 real points, apply the merged assembler, and compare each experiment against its correct full or straight-prefix/circular-tail ideal geometry. Calculate boundary changes at global segment transitions 4→5 and 5→6 for base curvature, masses, final weight, slope map, accumulated phase, and curvature vector.

- [x] **Step 4: Produce per-direction reports**

Report full 2000–200 mm, end15cm 100/75/50/30 mm, and end5cm 30/20/15 mm separately for 0/120/240. Include tip position, tangent, pose, and boundary continuity. Do not hide 240° failures in combined means.

- [x] **Step 5: Apply phase and rot_ang gates**

Use the full-region phase as the only runtime candidate, record local phases as provenance, and validate local coefficients under continuous full-length accumulation. Search or verify one global rot_ang on merged full geometry. If phase or rot_ang validation fails, keep `deployment_ready=false`.

- [x] **Step 6: Update package gates and test**

Write validation results back into a newly generated package, never mutate source result files. Run:

```powershell
python -m pytest tests/test_calibration_validation.py tests/test_sensor_parameter_package.py tests/test_multiregion_reconstruction.py -q
```

- [x] **Step 7: Commit**

```powershell
git add tools/calibration_validation.py tools/sensor_parameter_package.py tests/test_calibration_validation.py docs/calibration-multiregion-validation.json docs/calibration-multiregion-validation.md params/06B6_NeTi_v2_centraltube_multi_region.json
git commit -m "feat: validate multiregion calibration deployment"
```

### Task 6: Final regression, documentation, and handoff

**Files:**
- Modify: `docs/calibration-regions.md`
- Modify: `README.md` if it contains the canonical CLI workflow
- Modify: plan checkboxes in this file as tasks complete

**Interfaces:**
- Consumes: all prior task outputs.
- Produces: documented export, load, local recon, merged recon, score, and validation commands.

- [x] **Step 1: Document exact commands and safety gates**

Document candidate export, package import, three single-region recon commands, merged full recon, score analysis, full validation, CLI override precedence, and the meaning of `deployment_ready`.

- [x] **Step 2: Run required targeted tests**

```powershell
python -m pytest tests/test_vector_filter_configuration.py tests/test_calibration_batch.py tests/test_calibration_regions.py -q
```

- [x] **Step 3: Run all new and affected tests**

```powershell
python -m pytest tests/test_sensor_parameter_package.py tests/test_multiregion_reconstruction.py tests/test_calibration_score_summary.py tests/test_calibration_validation.py tests/test_vector_magnitude_input.py tests/test_reconstruction_intermediates.py tests/test_reconstructor_end_pose.py -q
```

- [x] **Step 4: Run the complete test suite**

Run: `python -m pytest -q`

Record exact pass/fail counts and investigate any new failure. Existing unrelated UDP anchor failures may be reported only after confirming they reproduce on the base commit or are unchanged by this work.

- [x] **Step 5: Review repository state**

Run `git status --short`, `git diff --check`, and `git log --oneline dev-entrylimit-reducefilter..HEAD`. Confirm the user's pre-existing `main.py` line-ending change and runtime output directory were not accidentally committed unless implementation necessarily modified `main.py` with preserved content.

- [x] **Step 6: Commit final documentation**

```powershell
git add docs/calibration-regions.md README.md docs/superpowers/plans/2026-09-14-multiregion-calibration-export-and-reconstruction.md
git commit -m "docs: explain multiregion calibration deployment"
```
