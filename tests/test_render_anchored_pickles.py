import pickle
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tools.render_anchored_pickles import (
    _atomic_render,
    load_anchored_pickle,
    output_paths_for,
    process_file,
    render_tip_trajectory_html,
    render_tip_trajectory_png,
    video_render_specs,
)


def _straight_shape(point_count=120):
    shape = np.zeros((point_count, 3), dtype=float)
    shape[:, 0] = np.linspace(0.0, 0.1, point_count)
    return shape


def _write_frames(path, inserts):
    with Path(path).open("wb") as stream:
        for index, insert in enumerate(inserts):
            pickle.dump(
                {
                    "timestamp": 100.0 + 0.1 * index,
                    "r_results": _straight_shape(),
                    "insert_value": insert,
                },
                stream,
            )


class RenderAnchoredPicklesTests(unittest.TestCase):
    def test_loader_anchors_120_point_shapes_and_ignores_leading_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.pkl"
            _write_frames(source, [0.0, 156.8, 166.8])

            data = load_anchored_pickle(source)

        self.assertEqual(data.shapes_m.shape, (3, 120, 3))
        np.testing.assert_allclose(data.relative_inserts_mm, [0.0, 0.0, 10.0])
        np.testing.assert_allclose(data.shapes_m[2, :, 0] - data.shapes_m[1, :, 0], 0.01)
        np.testing.assert_allclose(data.anchor_m, [0.04, 0.0, 0.0])
        self.assertAlmostEqual(data.insertion_baseline_mm, 156.8)
        self.assertFalse(np.any(data.clamped))

    def test_loader_rejects_inconsistent_point_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "bad.pkl"
            with source.open("wb") as stream:
                pickle.dump(
                    {
                        "timestamp": 1.0,
                        "r_results": np.zeros((1, 59, 3)),
                        "insert_value": 1.0,
                    },
                    stream,
                )

            with self.assertRaisesRegex(ValueError, r"shape"):
                load_anchored_pickle(source)

    def test_loader_keeps_legacy_60_point_pickles_readable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "legacy.pkl"
            with source.open("wb") as stream:
                pickle.dump(
                    {
                        "timestamp": 1.0,
                        "r_results": _straight_shape(60),
                        "insert_value": 1.0,
                    },
                    stream,
                )

            data = load_anchored_pickle(source)

        self.assertEqual(data.shapes_m.shape, (1, 60, 3))

    def test_output_paths_are_distinct_from_legacy_outputs(self):
        source = Path("VTK_ShapeData_20260820_192216.pkl")

        png, html, video, top_video = output_paths_for(Path("tips"), Path("videos"), source)

        self.assertEqual(png, Path("tips/VTK_ShapeData_20260820_192216_anchored_tip_trajectory.png"))
        self.assertEqual(html, Path("tips/VTK_ShapeData_20260820_192216_anchored_tip_trajectory.html"))
        self.assertEqual(
            video,
            Path("videos/VTK_ShapeData_20260820_192216/VTK_ShapeData_20260820_192216_anchored_full.mp4"),
        )
        self.assertEqual(
            top_video,
            Path("videos/VTK_ShapeData_20260820_192216/VTK_ShapeData_20260820_192216_anchored_top_view.mp4"),
        )

    def test_png_renderer_draws_real_anchored_trajectory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.pkl"
            output = Path(temp_dir) / "trajectory.png"
            _write_frames(source, [156.8, 166.8, 176.8])
            data = load_anchored_pickle(source)

            render_tip_trajectory_png(data, output, title="Anchored test")

            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 1000)

    def test_html_renderer_writes_self_contained_interactive_hover_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.pkl"
            output = Path(temp_dir) / "trajectory.html"
            _write_frames(source, [156.8, 166.8, 176.8])
            data = load_anchored_pickle(source)

            render_tip_trajectory_html(data, output, title="Anchored interactive test")

            html = output.read_text(encoding="utf-8")
            self.assertGreater(output.stat().st_size, 1_000_000)
            self.assertIn("plotly.js", html)
            self.assertIn("Relative insertion", html)
            self.assertIn("Fixed entrance anchor", html)
            self.assertIn("Anchored interactive test", html)

    def test_video_render_specs_keep_original_view_and_add_pickle_batch_top_view(self):
        specs = video_render_specs(Path("original.mp4"), Path("top.mp4"))

        self.assertEqual(
            specs,
            (
                (Path("original.mp4"), 20.0, 45.0),
                (Path("top.mp4"), 90.0, 0.0),
            ),
        )

    def test_process_file_preserves_existing_outputs_and_renders_missing_top_view(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.pkl"
            trajectory_output = root / "tips"
            video_output = root / "videos"
            _write_frames(source, [156.8, 166.8, 176.8])
            png, html, legacy_video, top_video = output_paths_for(
                trajectory_output,
                video_output,
                source,
            )
            png.parent.mkdir(parents=True)
            legacy_video.parent.mkdir(parents=True)
            png.write_bytes(b"existing-png")
            legacy_video.write_bytes(b"existing-video")
            video_calls = []

            def fake_html(data, output_path, title=None):
                Path(output_path).write_text("interactive", encoding="utf-8")

            def fake_video(data, output_path, **kwargs):
                video_calls.append((Path(output_path).name, kwargs["elev"], kwargs["azim"]))
                Path(output_path).write_bytes(b"new-top-video")

            with patch(
                "tools.render_anchored_pickles.render_tip_trajectory_html",
                side_effect=fake_html,
            ), patch(
                "tools.render_anchored_pickles.render_shape_video",
                side_effect=fake_video,
            ):
                with redirect_stdout(io.StringIO()):
                    process_file(
                        source,
                        trajectory_output,
                        video_output,
                        max_frames=3,
                        fps=20,
                        overwrite=False,
                    )

            self.assertEqual(png.read_bytes(), b"existing-png")
            self.assertEqual(legacy_video.read_bytes(), b"existing-video")
            self.assertEqual(html.read_text(encoding="utf-8"), "interactive")
            self.assertEqual(top_video.read_bytes(), b"new-top-video")
            self.assertEqual(
                video_calls,
                [(f".{top_video.stem}.part{top_video.suffix}", 90.0, 0.0)],
            )

    def test_atomic_render_failure_preserves_existing_final_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            final_path = Path(temp_dir) / "existing.html"
            final_path.write_text("original", encoding="utf-8")

            def failing_render(temporary_path):
                Path(temporary_path).write_text("partial", encoding="utf-8")
                raise RuntimeError("render failed")

            with self.assertRaisesRegex(RuntimeError, "render failed"):
                _atomic_render(failing_render, final_path)

            self.assertEqual(final_path.read_text(encoding="utf-8"), "original")
            self.assertFalse((Path(temp_dir) / ".existing.part.html").exists())


if __name__ == "__main__":
    unittest.main()
