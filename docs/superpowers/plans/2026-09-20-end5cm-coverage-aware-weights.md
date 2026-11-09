# End5cm Coverage-Aware Weights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an opt-in coverage-aware end5cm group-mean weight optimizer that keeps the existing 30-weight package shape while optimizing only reliably covered levels and dynamically deriving the remaining levels.

**Architecture:** Add pure support-map and expansion functions to `tools/end5_weight_coverage.py`. `Optimiser` will keep a fixed per-run support map, expose only reliable free levels to SciPy, and expand candidates into the complete 30-vector before every loss call. Existing mode remains unchanged when the new flag is false; package import/export stores optional diagnostics without changing the runtime schema.

**Tech Stack:** Python, NumPy, SciPy optimize, pytest, existing JSON sensor-package format.

**Spec:** User-approved compatibility-first coverage-aware weights design in the current task request.

## Global Constraints

- Default `--end5cm_coverage_aware_weights` is `False`; old packages and old runs retain current all-30 optimization.
- Enable only for end5cm real-point calibration with independent group weights and canonical group-mean scoring.
- Radius 0 never contributes to curvature-weight coverage.
- Threshold coordinates, not level indices, define log-space interpolation.
- Derived edge levels are exactly `1.0`; invalid/non-positive anchor weights raise clear `ValueError`.
- Do not change the serialized 30-weight / 10x2-slope schema or run actual optim/demo during this task.

## Review Focus

- A group with no reliable levels must produce deterministic all-1 derived weights and no NaN.
- A non-positive free anchor must fail before SciPy receives a candidate.
- A candidate update must recompute derived levels from the current free anchors, not from the initial vector.
- Group-specific support maps must not leak levels between group 0, 1, and 2.
- Package round-trip and old mode must still expose complete 30-weight vectors.

### Task 1: Pure coverage support map and expansion

**Files:**
- Modify: `tools/end5_weight_coverage.py`
- Test: `tests/test_end5cm_coverage_aware_weights.py`

**Interfaces:**
- Produce `build_groupwise_support_map(samples, thresholds, group_ids, min_effective_samples=1.0, min_max_mass=0.05)` returning per-group `reliable_levels`, `free_levels`, `derived_levels`, coverage metrics, and thresholds.
- Produce `expand_groupwise_weights(free_weights, support_map, neutral=1.0)` returning complete group-by-level weights and rejecting non-positive anchors.

- [x] Add failing tests for radius-0 exclusion, distinct group support maps, threshold-coordinate log interpolation, neutral edges, invalid anchors, and dynamic candidate expansion.
- [x] Run the focused tests and observe expected missing-symbol failures.
- [x] Implement the two pure functions with fixed support maps and deterministic interpolation.
- [x] Run focused tests to GREEN.

### Task 2: CLI/configuration and optimizer integration

**Files:**
- Modify: `main.py`, `calibration_batch.py`, `optimiser.py`, `reconstructor.py`
- Test: `tests/test_end5cm_coverage_aware_weights.py`, existing end5cm optimizer tests

**Interfaces:**
- Add `--end5cm_coverage_aware_weights`, `--end5cm_min_weight_effective_samples`, `--end5cm_min_weight_max_mass`, and `--end5cm_uncovered_weight_policy=interpolate_neutral_edges`.
- Add optimizer methods for fixed support-map construction, complete-vector expansion, and free-level mask/bounds handling.

- [x] Add RED tests for flag validation, free-level-only `x0`/bounds, dynamic derived updates, and unchanged legacy mode.
- [x] Implement configuration validation and pass coverage controls through batch parameters.
- [x] Build support maps from production group-mean score masses once per optimizer run.
- [x] Modify weight optimization candidate handling so free variables are expanded before loss evaluation and final weights are complete 30-vectors.
- [x] Run focused optimizer tests and existing end5cm tests.

### Task 3: Result/package diagnostics and offline support-map check

**Files:**
- Modify: `calibration_batch.py`, `tools/sensor_parameter_package.py`
- Create: `docs/diagnostics-0920-coverage-aware-support.md`
- Test: `tests/test_end5cm_coverage_aware_weights.py`, package round-trip tests

- [x] Add RED tests for optimization metadata, free-vs-derived bound-hit accounting, package round-trip, and old-package default-off behavior.
- [x] Store support maps, thresholds, policy, free parameter count, derived levels, and coverage metrics in results; preserve the 30-weight export.
- [x] Extend package region metadata compatibly, defaulting missing fields off.
- [x] Run the pure support-map check against the existing 191514 score/192950 result data and record exact group lists plus radius-0 exclusion rationale.

### Task 4: Verification

- [x] Run related tests and `python -m py_compile` for modified modules.
- [x] Run the full pytest suite; report existing unrelated failures precisely.
- [x] Do not run actual `optim`, actual demo, commit, or cleanup.
