# Dynamic Anchor Control and Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add protocol-independent live anchor reconfiguration, interactive trajectory HTML, and a preserved top-view video variant.

**Architecture:** Keep anchor state transitions inside `EntranceAnchorConstraint`, expose them through a locked `Demonstrator` method, and leave UDP parsing unchanged. Extend the existing offline renderer with Plotly HTML and a parameterized camera, producing new distinct paths.

**Tech Stack:** Python, NumPy, threading, argparse, Plotly, Matplotlib, FFmpeg, unittest

**Spec:** `docs/superpowers/specs/2026-08-23-dynamic-anchor-control-and-rendering-design.md`

## Global Constraints

- Do not define a new UDP command or payload format.
- Default entrance distance is exactly `0.06` m.
- Reconfiguration resets anchor and insertion baseline atomically.
- Keep existing PNG and `*_anchored_full.mp4`; create distinct HTML and `*_anchored_top_view.mp4`.
- Preserve user-owned untracked files and directories.

---

### Task 1: Reconfigurable anchor state

**Files:**
- Modify: `entrance_anchor.py`
- Test: `tests/test_entrance_anchor.py`

**Interfaces:**
- Produces: `EntranceAnchorConstraint.configure(enabled=None, entrance_offset_m=None, reset=True) -> None`

- [x] Write tests showing that enabling with `0.08` resets the old anchor/baseline and that an invalid distance leaves all state unchanged.
- [x] Run `python -m unittest tests.test_entrance_anchor -v` and confirm the new tests fail because `configure` is absent.
- [x] Implement validated atomic configuration and reset.
- [x] Re-run the test module and confirm it passes.

### Task 2: Startup parameter and thread-safe process interface

**Files:**
- Modify: `main.py`
- Modify: `demonstrator.py`
- Test: `tests/test_demonstrator_anchor_pipeline.py`

**Interfaces:**
- Consumes: `EntranceAnchorConstraint.configure(...)`
- Produces: `Demonstrator.configure_anchor_constraint(enabled=None, entrance_offset_m=None, reset=True) -> dict`

- [x] Write tests against small real harness objects showing locked configure/apply behavior and changed-offset propagation.
- [x] Run `python -m unittest tests.test_demonstrator_anchor_pipeline -v` and confirm failure for missing interfaces.
- [x] Add `--anchor_offset_m` with default `0.06`, pass it into `Demonstrator`, create one anchor lock, and guard both configure and apply with the lock.
- [x] Re-run the focused test module and confirm it passes.

### Task 3: HTML and top-view renderer

**Files:**
- Modify: `tools/render_anchored_pickles.py`
- Test: `tests/test_render_anchored_pickles.py`

**Interfaces:**
- Produces: `render_tip_trajectory_html(data, output_path, title=None) -> Path`
- Produces: `render_shape_video(..., elev=20, azim=45) -> Path`
- Produces: `output_paths_for(...) -> (png_path, html_path, legacy_video_path, top_video_path)`

- [x] Write tests for four distinct output names, an actual Plotly HTML artifact with hover data, and forwarding `elev=90, azim=0` to the top-view render.
- [x] Run `python -m unittest tests.test_render_anchored_pickles -v` and confirm failures for missing HTML/top-view behavior.
- [x] Implement Plotly HTML, camera parameters, atomic output generation, and per-output skip behavior.
- [x] Re-run the focused renderer tests and confirm they pass.

### Task 4: Verification and artifact generation

**Files:**
- Modify only generated output directories outside the repository.

**Interfaces:**
- Consumes: extended renderer CLI.

- [x] Run all repository unit tests and confirm zero failures.
- [x] Run the renderer against the four selected 2026-08-20 pickle recordings without `--overwrite`.
- [x] Confirm four new HTML files and four new top-view MP4 files exist and are nonempty.
- [x] Use FFprobe to verify each new video stream and duration, and confirm existing `*_anchored_full.mp4` files remain present.
- [x] Review the final diff and request code review before reporting completion.
