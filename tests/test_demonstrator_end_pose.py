import unittest

import numpy as np

from demonstrator import _build_end_pose_arrow_matrices


class BuildEndPoseArrowMatricesTests(unittest.TestCase):
    def test_uses_scaled_curve_endpoint_and_end_pose_rows(self):
        endpoint = np.array([0.01, -0.02, 0.03])
        end_pose = np.array(
            [
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
            ]
        )

        matrices = _build_end_pose_arrow_matrices(
            endpoint,
            end_pose,
            scale_factor=5000.0,
            axis_length=250.0,
        )

        expected_origin = np.array([50.0, -100.0, 150.0])
        np.testing.assert_allclose(matrices[:, :3, 3], np.tile(expected_origin, (3, 1)))
        np.testing.assert_allclose(matrices[:, :3, 0], end_pose * 250.0)
        np.testing.assert_allclose(matrices[:, 3, :], np.tile([0.0, 0.0, 0.0, 1.0], (3, 1)))

    def test_rejects_invalid_end_pose_shape(self):
        with self.assertRaisesRegex(ValueError, "end_pose must have shape"):
            _build_end_pose_arrow_matrices(
                np.zeros(3),
                np.zeros((3,)),
                scale_factor=5000.0,
                axis_length=250.0,
            )


if __name__ == "__main__":
    unittest.main()
