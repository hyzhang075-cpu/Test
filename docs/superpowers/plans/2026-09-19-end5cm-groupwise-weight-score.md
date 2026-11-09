# end5cm Groupwise Weight Score Implementation Plan

**Goal:** Add an opt-in end5cm groupwise weight-scoring mode for independent weight groups, preserve legacy spatial-window behavior, and provide an offline dynamic replay report.

**Architecture:** Keep the existing spatial score path as the compatibility default. Split slope and weight score/mass construction, with `group_mean` using the pre-weight base magnitude: points 19/20 share their arithmetic-mean score, while points 21 and 22 score independently. Record the mode in calibration context, result reports, sensor packages, runtime defaults, and diagnostics. Add a streaming replay tool that reuses pure reconstruction calculations without writing source inputs.

**Tech Stack:** Python, NumPy, pytest, JSON/CSV/Markdown, Matplotlib.

**Global Constraints**

- Continue on `dev-entrylimit-reducefilter-multiregion`; preserve existing tracked and untracked work.
- Do not run optimization, reset, clean, commit, or push.
- Legacy packages without `weight_score_mode` must remain `spatial_window`.
- Groupwise mode is valid only for `optimization_region=end5cm` with `end5cm_independent_weights=True`.
- `base_magnitude` is computed before weights with level-0 slope and `magnitude_ratio=1`.

### Task 1: Score behavior and CLI validation

Add red tests for groupwise scores/masses, slope compatibility, flag combinations, diagnostics, and legacy fallback; then implement the smallest scoring and parser changes.

### Task 2: Parameter package round-trip

Add `weight_score_mode` to result context/package comparison, export/import, shape validation, and parser-default restoration while preserving old-package behavior.

### Task 3: Offline replay tool

Add a streaming replay utility with pure metric helpers, unit tests, and JSON/CSV/Markdown/PNG outputs for both supplied recordings and the four requested variants.

### Task 4: Verification

Run targeted tests, replay tests/tool, and the full suite. Report known unrelated UDP-anchor failures if present; do not change unrelated code.
