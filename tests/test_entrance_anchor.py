import unittest

import numpy as np

from entrance_anchor import EntranceAnchorConstraint


class EntranceAnchorConstraintTests(unittest.TestCase):
    @staticmethod
    def _constant_frames(t, y, z, count=3):
        return tuple(
            np.repeat(np.asarray(axis, dtype=float)[None, :], count, axis=0)
            for axis in (t, y, z)
        )

    def test_default_entrance_offset_is_6cm(self):
        constraint = EntranceAnchorConstraint(enabled=True)

        self.assertAlmostEqual(constraint.entrance_offset_m, 0.06)

    def test_first_nonzero_insert_is_baseline_and_next_10mm_advances_target(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.07)
        curve = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])

        placeholder = constraint.apply(curve, 0.0)
        baseline = constraint.apply(curve, 156.8)
        advanced = constraint.apply(curve, 166.8)

        np.testing.assert_allclose(placeholder.curve_m, curve)
        np.testing.assert_allclose(baseline.curve_m, curve)
        np.testing.assert_allclose(advanced.curve_m[:, 0], [0.01, 0.11])
        np.testing.assert_allclose(advanced.anchored_point_m, [0.03, 0.0, 0.0])
        self.assertAlmostEqual(advanced.relative_insert_mm, 10.0)
        self.assertAlmostEqual(constraint.insertion_baseline_mm, 156.8)

    def test_initial_anchor_uses_reverse_polyline_arclength_instead_of_global_x(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.07)
        curve = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.05, 0.0, 0.0],
                [0.05, 0.05, 0.0],
            ]
        )

        result = constraint.apply(curve, None)

        np.testing.assert_allclose(result.source_point_m, [0.03, 0.0, 0.0])
        np.testing.assert_allclose(result.anchor_m, result.source_point_m)
        np.testing.assert_allclose(result.anchored_point_m, result.anchor_m)
        np.testing.assert_allclose(result.translation_m, np.zeros(3))
        np.testing.assert_allclose(result.curve_m, curve)

    def test_constraint_preserves_shape_point_count_and_pairwise_vectors(self):
        curve = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.03, 0.04, 0.0],
                [0.08, 0.04, 0.02],
            ]
        )

        result = EntranceAnchorConstraint(enabled=True).apply(curve, None)

        self.assertEqual(result.curve_m.shape, curve.shape)
        np.testing.assert_allclose(np.diff(result.curve_m, axis=0), np.diff(curve, axis=0))

    def test_zero_after_baseline_holds_last_valid_relative_insertion(self):
        constraint = EntranceAnchorConstraint(enabled=True)
        curve = np.array([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0]])
        constraint.apply(curve, 156.8)
        advanced = constraint.apply(curve, 176.8)

        dropout = constraint.apply(curve, 0.0)

        self.assertAlmostEqual(dropout.relative_insert_mm, 20.0)
        np.testing.assert_allclose(dropout.curve_m, advanced.curve_m)

    def test_disabled_constraint_returns_an_independent_unchanged_curve(self):
        curve = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])

        result = EntranceAnchorConstraint(enabled=False).apply(curve, 166.8)

        np.testing.assert_array_equal(result.curve_m, curve)
        self.assertIsNot(result.curve_m, curve)
        self.assertIsNone(result.anchor_m)
        self.assertFalse(result.applied)

    def test_distance_beyond_curve_clamps_to_start_without_changing_point_count(self):
        constraint = EntranceAnchorConstraint(enabled=True)
        curve = np.array([[0.0, 0.0, 0.0], [0.05, 0.0, 0.0]])

        result = constraint.apply(curve, None)

        self.assertTrue(result.clamped)
        self.assertAlmostEqual(result.used_distance_m, 0.05)
        self.assertEqual(result.curve_m.shape, (2, 3))
        np.testing.assert_allclose(result.source_point_m, curve[0])

    def test_rejects_nonfinite_or_wrong_shape_curves(self):
        constraint = EntranceAnchorConstraint(enabled=True)

        with self.assertRaisesRegex(ValueError, "shape"):
            constraint.apply(np.zeros((3, 2)), None)
        with self.assertRaisesRegex(ValueError, "finite"):
            constraint.apply(np.array([[0.0, 0.0, 0.0], [np.nan, 0.0, 0.0]]), None)

    def test_configure_new_distance_resets_anchor_and_insertion_zero(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.07)
        old_curve = np.array([[0.0, 0.0, 0.0], [0.20, 0.0, 0.0]])
        constraint.apply(old_curve, 156.8)
        constraint.apply(old_curve, 166.8)

        constraint.configure(enabled=True, entrance_offset_m=0.08)

        self.assertTrue(constraint.enabled)
        self.assertAlmostEqual(constraint.entrance_offset_m, 0.08)
        self.assertIsNone(constraint.anchor_m)
        self.assertIsNone(constraint.insertion_baseline_mm)
        self.assertEqual(constraint.last_relative_insert_mm, 0.0)

        new_curve = np.array([[0.0, 0.0, 0.0], [0.30, 0.0, 0.0]])
        placeholder = constraint.apply(new_curve, 0.0)
        baseline = constraint.apply(new_curve, 200.0)

        np.testing.assert_allclose(placeholder.anchor_m, [0.22, 0.0, 0.0])
        self.assertAlmostEqual(baseline.relative_insert_mm, 0.0)
        self.assertAlmostEqual(constraint.insertion_baseline_mm, 200.0)

    def test_invalid_configure_is_atomic(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.07)
        curve = np.array([[0.0, 0.0, 0.0], [0.20, 0.0, 0.0]])
        constraint.apply(curve, 156.8)
        original_anchor = constraint.anchor_m.copy()

        with self.assertRaisesRegex(ValueError, "finite nonnegative"):
            constraint.configure(enabled=False, entrance_offset_m=np.nan)

        self.assertTrue(constraint.enabled)
        self.assertAlmostEqual(constraint.entrance_offset_m, 0.07)
        np.testing.assert_allclose(constraint.anchor_m, original_anchor)
        self.assertAlmostEqual(constraint.insertion_baseline_mm, 156.8)

    def test_tangent_anchor_translates_then_rotates_curve_about_fixed_anchor(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=1.0)
        reference_curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        reference_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(reference_curve, None, *reference_frames)

        current_curve = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0]]
        )
        current_frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )

        result = constraint.apply(current_curve, None, *current_frames)

        np.testing.assert_allclose(result.anchor_m, [1.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(result.anchored_point_m, result.anchor_m, atol=1e-12)
        np.testing.assert_allclose(
            result.rotation_matrix,
            [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            atol=1e-12,
        )
        np.testing.assert_allclose(result.curve_m, reference_curve, atol=1e-12)
        np.testing.assert_allclose(
            result.rotation_matrix @ result.source_frame[:, 0],
            result.anchor_frame[:, 0],
            atol=1e-12,
        )

    def test_translation_switch_applies_position_anchor_without_rotation(self):
        constraint = EntranceAnchorConstraint(
            translation_enabled=True,
            rotation_enabled=False,
            entrance_offset_m=1.0,
        )
        reference_curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        identity_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(reference_curve, None, *identity_frames)
        current_curve = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0]]
        )
        rotated_frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )

        result = constraint.apply(current_curve, None, *rotated_frames)

        np.testing.assert_allclose(
            result.curve_m,
            [[1.0, -1.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]],
            atol=1e-12,
        )
        np.testing.assert_allclose(result.translation_m, [1.0, -1.0, 0.0])
        np.testing.assert_allclose(result.rotation_matrix, np.eye(3), atol=1e-12)
        self.assertIsNone(result.anchor_frame)

    def test_rotation_switch_aligns_tangent_about_current_entrance_without_translation(self):
        constraint = EntranceAnchorConstraint(
            translation_enabled=False,
            rotation_enabled=True,
            entrance_offset_m=1.0,
        )
        reference_curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        identity_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(reference_curve, None, *identity_frames)
        current_curve = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0]]
        )
        rotated_frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )

        result = constraint.apply(current_curve, None, *rotated_frames)

        np.testing.assert_allclose(
            result.curve_m,
            [[-1.0, 1.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
            atol=1e-12,
        )
        np.testing.assert_allclose(result.translation_m, np.zeros(3), atol=1e-12)
        np.testing.assert_allclose(result.anchored_point_m, result.source_point_m, atol=1e-12)
        self.assertIsNone(result.anchor_m)

    def test_rotation_anchor_does_not_follow_yz_roll_when_tangent_is_unchanged(self):
        constraint = EntranceAnchorConstraint(
            translation_enabled=False,
            rotation_enabled=True,
            entrance_offset_m=1.0,
        )
        curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 1.0, 0.0]]
        )
        reference_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(curve, None, *reference_frames)
        rolled_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, -1.0, 0.0],
        )

        result = constraint.apply(curve, None, *rolled_frames)

        np.testing.assert_allclose(result.rotation_matrix, np.eye(3), atol=1e-12)
        np.testing.assert_allclose(result.curve_m, curve, atol=1e-12)

    def test_rotation_anchor_reference_tangent_is_independent_of_yz(self):
        constraint = EntranceAnchorConstraint(
            translation_enabled=False,
            rotation_enabled=True,
            entrance_offset_m=1.0,
        )
        curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        skewed_reference_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(curve, None, *skewed_reference_frames)
        current_frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )

        result = constraint.apply(curve, None, *current_frames)

        np.testing.assert_allclose(
            result.rotation_matrix,
            [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            atol=1e-12,
        )

    def test_both_switches_disabled_leave_curve_and_frame_unchanged(self):
        constraint = EntranceAnchorConstraint(
            translation_enabled=False,
            rotation_enabled=False,
            entrance_offset_m=1.0,
        )
        curve = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0]]
        )
        frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )

        result = constraint.apply(curve, 156.8, *frames)

        np.testing.assert_array_equal(result.curve_m, curve)
        np.testing.assert_allclose(result.rotation_matrix, np.eye(3), atol=1e-12)
        self.assertFalse(result.applied)

    def test_reset_clears_and_recaptures_position_and_tangent_together(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=1.0)
        curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        reference_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(curve, 100.0, *reference_frames)

        constraint.configure(enabled=True, entrance_offset_m=0.5, reset=True)

        self.assertIsNone(constraint.anchor_m)
        self.assertIsNone(constraint.anchor_frame)
        self.assertIsNone(constraint.anchor_tangent)
        rotated_frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        recaptured = constraint.apply(curve, 200.0, *rotated_frames)

        np.testing.assert_allclose(recaptured.anchor_m, [1.5, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(
            recaptured.anchor_frame,
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            atol=1e-12,
        )
        np.testing.assert_allclose(recaptured.rotation_matrix, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(constraint.insertion_baseline_mm, 200.0)

    def test_tangent_uses_same_arclength_fraction_with_spherical_interpolation(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.25)
        curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        identity_frames = self._constant_frames(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        constraint.apply(curve, None, *identity_frames)
        T = np.array(
            [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        )
        Y = np.array(
            [[0.0, 1.0, 0.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
        )
        Z = np.repeat([[0.0, 0.0, 1.0]], 3, axis=0)

        result = constraint.apply(curve, None, T, Y, Z)

        angle = np.deg2rad(67.5)
        expected_current_frame = np.array(
            [
                [np.cos(angle), -np.sin(angle), 0.0],
                [np.sin(angle), np.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        np.testing.assert_allclose(
            result.source_point_m,
            [1.75, 0.0, 0.0],
            atol=1e-12,
        )
        np.testing.assert_allclose(
            result.source_frame,
            expected_current_frame,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            result.rotation_matrix,
            expected_current_frame.T,
            atol=1e-12,
        )

    def test_invalid_frame_input_does_not_partially_initialize_anchor_session(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.06)
        curve = np.array([[0.0, 0.0, 0.0], [0.10, 0.0, 0.0]])
        invalid_T = np.zeros((3, 3))
        Y = np.repeat([[0.0, 1.0, 0.0]], 2, axis=0)
        Z = np.repeat([[0.0, 0.0, 1.0]], 2, axis=0)

        with self.assertRaisesRegex(ValueError, "T must have shape"):
            constraint.apply(curve, 100.0, invalid_T, Y, Z)

        self.assertIsNone(constraint.anchor_m)
        self.assertIsNone(constraint.anchor_frame)
        self.assertIsNone(constraint.anchor_tangent)
        self.assertIsNone(constraint.insertion_baseline_mm)

    def test_degenerate_local_frame_is_rejected_without_initializing_session(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.06)
        curve = np.array([[0.0, 0.0, 0.0], [0.10, 0.0, 0.0]])
        zero_T = np.zeros((2, 3))
        Y = np.repeat([[0.0, 1.0, 0.0]], 2, axis=0)
        Z = np.repeat([[0.0, 0.0, 1.0]], 2, axis=0)

        with self.assertRaisesRegex(ValueError, "degenerate"):
            constraint.apply(curve, 100.0, zero_T, Y, Z)

        self.assertIsNone(constraint.anchor_m)
        self.assertIsNone(constraint.anchor_frame)
        self.assertIsNone(constraint.anchor_tangent)
        self.assertIsNone(constraint.insertion_baseline_mm)

    def test_first_framed_call_recaptures_joint_session_after_translation_only_use(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=1.0)
        translation_only_curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        constraint.apply(translation_only_curve, 100.0)
        np.testing.assert_allclose(constraint.anchor_m, [1.0, 0.0, 0.0])

        framed_curve = np.array(
            [[0.0, 1.0, 0.0], [0.0, 2.0, 0.0], [0.0, 3.0, 0.0]]
        )
        frames = self._constant_frames(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )

        result = constraint.apply(framed_curve, 200.0, *frames)

        np.testing.assert_allclose(result.anchor_m, [0.0, 2.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(result.rotation_matrix, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(constraint.insertion_baseline_mm, 200.0)
        np.testing.assert_allclose(result.anchor_frame, result.source_frame, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
