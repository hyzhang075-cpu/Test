# end5cm Weights-Only and Coverage Diagnostics Plan

**Goal:** Disambiguate the end5cm groupwise CLI, support weights-only calibration with inherited slopes, repair relative folder overrides, and expose reproducible per-group weight-coverage diagnostics.

**Architecture:** Use one canonical argparse destination, `end5cm_independent_weight_score`, with the previous groupwise spelling as an alias. Keep `weight_score_mode=group_mean` in package semantics. Add an explicit weights-only branch in `Optimiser.optim_coeff` that validates and preserves source slopes, records a fixed slope stage, then runs only the existing real-point weight loss. Keep path resolution relative to `calibration_data_root` and add pure coverage functions over score samples.

**Global constraints:**

- Continue on `dev-entrylimit-reducefilter-multiregion` in the current workspace.
- Preserve all existing tracked changes and untracked diagnostics.
- Do not run `optim`, reset, clean, commit, or push.
- Shared end5cm thresholds remain `[0.8, 1.2, 2, 3, 4, 10, 20, 35, 45]`.
- New coverage reports must account for both dominant-level counts and mass-above-threshold counts.

### Task 1: CLI canonicalization

Write failing tests for new/legacy names, canonical explicit precedence, package defaults, and round-trip export/import. Implement one canonical argparse destination with the old spelling as an alias and update internal references while preserving legacy runtime keys where needed.

### Task 2: Weights-only calibration

Write failing tests proving slopes are not minimized, remain elementwise unchanged, weights are minimized, missing source slopes and explicit `--slopes None` fail, and explicit `--weights None` resets only weights. Implement source validation, a fixed slope stage result, and package/result provenance.

### Task 3: Relative folder override

Write failing path-resolution/export tests for `calibration_data_root=0909-...` plus `folder_path=5cm`, then implement relative override resolution and relative result/package serialization without breaking absolute paths.

### Task 4: Coverage diagnostics

Write failing pure-function tests for groupwise base/theory/required gain, dominant-level and mass-threshold coverage, bounds exceedance, and bound hits. Implement reusable report fields and validate them against the supplied 20260919 direct=0 score result.

### Task 5: Verification

Run related tests, the score task with the new path/CLI, and the full suite. Report all failures, including known unrelated failures, and provide the final non-optim command without executing it.
