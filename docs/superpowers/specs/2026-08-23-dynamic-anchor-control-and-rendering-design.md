# Dynamic Anchor Control and Rendering Design

## Goal

Make the bronchial-entrance distance configurable at startup and safely changeable while the process is running, without committing to a UDP command format that still needs agreement with the software team. Add interactive trajectory HTML and a second top-view video while preserving every existing output.

## Runtime control

- `main.py` exposes `--anchor_offset_m`, default `0.06` m.
- `Demonstrator` accepts `anchor_offset_m` and constructs the constraint with that value.
- `EntranceAnchorConstraint.configure(enabled=None, entrance_offset_m=None, reset=True)` is the protocol-independent state transition. A reset clears the fixed anchor, the first-nonzero insertion baseline, and the last relative insertion.
- `Demonstrator.configure_anchor_constraint(enabled=None, entrance_offset_m=None, reset=True)` is the thread-safe integration interface. It serializes configuration and frame application with one lock and returns the actual state.
- Reconfiguring with `enabled=True` and a new distance represents the moment the sensor reaches the carina. The next processed curve establishes the fixed entrance anchor; the next finite nonzero insertion establishes the relative-insertion zero. Leading placeholder zero values remain ignored.
- UDP commands `anchor_configure`, `anchor_reset`, and `anchor_status` validate their payloads and call the thread-safe integration interface. They do not send UDP replies, so the external `sendObj` stream cannot be mixed with control ACK/NACK datagrams.
- The UDP adapter treats external `entrance_offset_m` as the catheter-tip-to-entrance distance and subtracts the fixed 0.01 m sensor setback before calling `configure_anchor_constraint`. Values below 0.01 m are rejected atomically. Direct in-process configuration already uses the effective sensor distance and is not adjusted again.
- Invalid distances (non-finite or negative) raise `ValueError` without partially changing state.

## Offline rendering

- Keep the existing `*_anchored_tip_trajectory.png` and `*_anchored_full.mp4` behavior and files.
- Add `*_anchored_tip_trajectory.html`, built with Plotly and written as a self-contained interactive 3D document. It contains the tip path, start/end points, fixed entrance anchor, and hover fields for elapsed time, relative insertion, and XYZ in millimetres.
- Add `*_anchored_top_view.mp4`, rendered with `elev=90` and `azim=0`, matching the useful view from `pickle_video_batch.py`.
- Rendering is atomic. Existing outputs are skipped unless `--overwrite` is supplied; the new video has a distinct name, so the old video is never overwritten.
- Offline replay uses the shared default 0.06 m anchor offset unless explicitly overridden.

## Verification

- Unit tests cover runtime reset, length replacement, invalid-value atomicity, startup propagation, and lock-protected pipeline application.
- Renderer tests cover the four distinct output paths, real interactive HTML content, and explicit top-view arguments.
- Run the focused unit tests, then the project test suite.
- Generate four HTML files and four top-view videos from the 2026-08-20 recordings, then verify file existence, nonzero size, MP4 metadata, and preservation of existing videos.
