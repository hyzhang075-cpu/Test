# Entrance Anchor Constraint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a switchable, translation-only bronchial entrance anchor to live reconstruction and replay the 19:22–19:56 Pickles into anchored trajectory images and videos.

**Architecture:** A dependency-light `EntranceAnchorConstraint` owns all state and geometry. The live demonstrator and offline renderer call the same API after temporal curve filtering, so recording, rendering, and UDP consumers observe identical anchored coordinates.

**Tech Stack:** Python 3, NumPy, unittest, Matplotlib, FFmpeg

**Spec:** `docs/superpowers/specs/2026-08-23-entrance-anchor-constraint-design.md`

## Global Constraints

- The default carina-to-bronchial-entrance distance is exactly 0.06 m.
- The first finite non-zero insertion reading is the relative insertion baseline; leading zero placeholders are ignored.
- Anchoring applies translation only: no rotation, deformation, resampling, or point-count change.
- Live anchoring runs after temporal filtering and before recorder, display, JSON, or binary output.
- Existing Pickles and legacy plots/videos remain read-only.

---

### Task 1: Pure entrance-anchor geometry and state

**Files:**
- Create: `entrance_anchor.py`
- Create: `tests/test_entrance_anchor.py`

**Interfaces:**
- Produces: `AnchorConstraintResult`; `EntranceAnchorConstraint(enabled: bool, entrance_offset_m: float = 0.06)`; `EntranceAnchorConstraint.apply(curve_m, insert_value_mm) -> AnchorConstraintResult`.

- [ ] **Step 1: Write failing geometry/state tests**

```python
def test_first_nonzero_insert_is_baseline_and_next_10mm_advances_target():
    constraint = EntranceAnchorConstraint(enabled=True)
    curve = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])
    constraint.apply(curve, 0.0)
    baseline = constraint.apply(curve, 156.8)
    advanced = constraint.apply(curve, 166.8)
    np.testing.assert_allclose(baseline.curve_m, curve)
    np.testing.assert_allclose(advanced.curve_m[:, 0], [0.01, 0.11])
    np.testing.assert_allclose(advanced.anchored_point_m, [0.03, 0.0, 0.0])

def test_constraint_preserves_shape_and_point_count():
    curve = np.array([[0.0, 0.0, 0.0], [0.03, 0.04, 0.0], [0.08, 0.04, 0.0]])
    result = EntranceAnchorConstraint(enabled=True).apply(curve, None)
    assert result.curve_m.shape == curve.shape
    np.testing.assert_allclose(np.diff(result.curve_m, axis=0), np.diff(curve, axis=0))
```

- [ ] **Step 2: Run the tests and confirm they fail because the module does not exist**

Run: `python -m unittest tests.test_entrance_anchor -v`

Expected: import failure for `entrance_anchor`.

- [ ] **Step 3: Implement the minimal pure state machine and reverse-polyline interpolation**

Validate `(N, 3)` finite curves, latch the first non-zero insertion baseline, retain the last valid relative insertion across zero placeholders, interpolate the target point from the tip by arc length, and translate a copy of the full curve.

- [ ] **Step 4: Run the focused tests**

Run: `python -m unittest tests.test_entrance_anchor -v`

Expected: all anchor tests pass.

### Task 2: Wire the constraint into live demonstration

**Files:**
- Modify: `main.py`
- Modify: `demonstrator.py`
- Create: `tests/test_demonstrator_anchor_pipeline.py`

**Interfaces:**
- Consumes: `EntranceAnchorConstraint.apply(curve_m, insert_value_mm)`.
- Produces: CLI flag `--anchor_constraint_enabled`; constrained `r_results_postrot` delivered to recorder, VTK, JSON, and binary packet paths.

- [ ] **Step 1: Write a failing pipeline test**

```python
def test_live_anchor_stage_returns_unchanged_curve_when_disabled_and_translated_curve_when_enabled():
    curve = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])
    disabled = apply_entrance_anchor(EntranceAnchorConstraint(False), curve, 166.8)
    enabled_state = EntranceAnchorConstraint(True)
    apply_entrance_anchor(enabled_state, curve, 156.8)
    enabled = apply_entrance_anchor(enabled_state, curve, 166.8)
    np.testing.assert_allclose(disabled, curve)
    np.testing.assert_allclose(enabled[:, 0], [0.01, 0.11])
```

- [ ] **Step 2: Run it and confirm the live integration API is missing**

Run: `python -m unittest tests.test_demonstrator_anchor_pipeline -v`

Expected: import or attribute failure naming the missing pipeline API.

- [ ] **Step 3: Add the main flag and live post-filter/pre-output application**

Add `anchor_constraint_enabled` to the Demonstrator-only parameter list. Initialize one constraint per Demonstrator, default `insert_dis` to `None`, and apply it after Kalman/moving-average filtering but before `recorder.save`, `_update_frame`, and UDP serialization.

- [ ] **Step 4: Run focused and existing tests**

Run: `python -m unittest tests.test_entrance_anchor tests.test_demonstrator_anchor_pipeline tests.test_demonstrator_end_pose -v`

Expected: all tests pass after dependencies are available.

### Task 3: Offline anchored Pickle renderer

**Files:**
- Create: `tools/render_anchored_pickles.py`
- Create: `tests/test_render_anchored_pickles.py`

**Interfaces:**
- Consumes: sequential Pickle dictionaries with `timestamp`, `r_results`, and `insert_value`; `EntranceAnchorConstraint`.
- Produces: `load_anchored_pickle(path)`, `render_tip_trajectory_png(data, path)`, `render_shape_video(data, path, max_frames, fps)` and a batch CLI.

- [ ] **Step 1: Write a failing replay test with three literal frames**

```python
def test_loader_anchors_recorded_shapes_and_ignores_leading_zero(tmp_path):
    source = tmp_path / "sample.pkl"
    write_frames(source, inserts=[0.0, 156.8, 166.8])
    data = load_anchored_pickle(source)
    assert data.shapes_m.shape == (3, 60, 3)
    np.testing.assert_allclose(data.relative_inserts_mm, [0.0, 0.0, 10.0])
    np.testing.assert_allclose(data.shapes_m[2, :, 0] - data.shapes_m[1, :, 0], 0.01)
```

- [ ] **Step 2: Run it and confirm the renderer module is missing**

Run: `python -m unittest tests.test_render_anchored_pickles -v`

Expected: import failure for `tools.render_anchored_pickles`.

- [ ] **Step 3: Implement streaming load, PNG rendering, sampled MP4 rendering, and CLI discovery**

Keep source files read-only, require `(60, 3)` finite shapes, convert plot/video coordinates to millimetres, draw the fixed entrance anchor, and write distinct `_anchored_` output names through temporary files followed by atomic replace.

- [ ] **Step 4: Run replay tests**

Run: `python -m unittest tests.test_render_anchored_pickles -v`

Expected: replay and PNG smoke tests pass.

### Task 4: Documentation and real-data artifact verification

**Files:**
- Modify: `README.md`
- Generate outside Git: `E:/shape_exp/0820光明豬肺實測/fiber_tip_trajectories/*_anchored_tip_trajectory.png`
- Generate outside Git: `E:/shape_exp/0820光明豬肺實測/pickle_videos/*/*_anchored_full.mp4`

**Interfaces:**
- Consumes: Task 3 CLI and the four Pickles from 19:22 through 19:56.
- Produces: documented live command, four PNGs, four MP4s, and numerical invariant audit.

- [ ] **Step 1: Document live and offline commands**

```powershell
python main.py --task demo --anchor_constraint_enabled
python tools/render_anchored_pickles.py `
  'E:\shape_exp\0820光明豬肺實測\待分析的数据' `
  --from-time 1922 --to-time 1956 `
  --trajectory-output 'E:\shape_exp\0820光明豬肺實測\fiber_tip_trajectories' `
  --video-output 'E:\shape_exp\0820光明豬肺實測\pickle_videos'
```

- [ ] **Step 2: Run the full unit suite**

Run: `python -m unittest discover -s tests -v`

Expected: zero failures and zero errors.

- [ ] **Step 3: Generate the four real-data result pairs**

Run the documented offline command with `--overwrite` and inspect every command exit code.

- [ ] **Step 4: Audit every frame numerically**

For each file, report frame count, insertion baseline, requested-distance clamp count, maximum anchor residual, output point shapes, PNG byte size, MP4 byte size, and ffprobe duration. Require `(60, 3)` finite output for all frames and near-zero anchor residual for unclamped frames.

- [ ] **Step 5: Visually inspect all four PNGs and representative MP4 frames**

Open each trajectory PNG and sample the first, middle, and final MP4 frames. Confirm the anchor marker is fixed, trajectory axes are legible, and no rendering bounds hide the curve.
