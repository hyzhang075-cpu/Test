"""Numerical regression tests independent of hardware and calibration imports."""
import ast
from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import uniform_filter1d


def reconstructor():
    tree = ast.parse((Path(__file__).parents[1] / 'reconstructor.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Reconstructor')
    names = {'_moving_average_scipy', '_smooth_curvature_direction', '_interpolate_curvature_vector'}
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    cls.bases = []
    ns = dict(np=np, PchipInterpolator=PchipInterpolator, uniform_filter1d=uniform_filter1d)
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<numerical production methods>', 'exec'), ns)
    obj = ns['Reconstructor']()
    obj.ad_samp_dist = np.linspace(0, .04, 5)
    obj.interp_num = 5
    obj.move_filter = 3
    obj.move_filter_for_vector = True
    return obj


@pytest.mark.parametrize('method', ['linear', 'pchip'])
def test_preserves_sensor_magnitudes_and_does_not_spread_bend(method):
    r = reconstructor()
    m = np.array([0., 0., .001, 20., 25.])
    a = np.array([0., 0., 2., 0., 0.])
    c, angle, _ = r._interpolate_curvature_vector(m, a, method)
    np.testing.assert_allclose(c, m, atol=1e-12)
    assert abs(angle[2]) < .01  # unreliable low-curvature direction follows strong neighbor


def test_cancellation_and_antipodal_direction_fall_back_to_current_point():
    r = reconstructor()
    for m in [np.array([1., 1., 2., 1., 1.]), np.array([10., 10., 1., 10., 10.])]:
        a = np.array([0., 0., np.pi, 0., 0.])
        c, angle, _ = r._interpolate_curvature_vector(m, a, 'pchip')
        np.testing.assert_allclose(c, m, atol=1e-12)
        assert abs(np.cos(angle[2]) + 1.) < 1e-12


def test_zero_curvature_and_no_window_are_finite_and_repeatable():
    r = reconstructor()
    a = np.array([3., -3., 0., 1., -1.])
    c, angle, _ = r._interpolate_curvature_vector(np.zeros(5), a, 'pchip')
    assert np.isfinite(angle).all()
    np.testing.assert_array_equal(c, np.zeros(5))
    r.move_filter = 1
    m = np.arange(1., 6.)
    first = r._interpolate_curvature_vector(m, a, 'pchip')
    second = r._interpolate_curvature_vector(m, a, 'pchip')
    np.testing.assert_allclose(first[0], m)
    np.testing.assert_allclose(np.exp(1j*first[1]), np.exp(1j*a))
    for x, y in zip(first, second):
        np.testing.assert_array_equal(x, y)


def test_sensor_direction_smoothing_is_rotation_equivariant_across_angle_branch():
    r = reconstructor()
    m = np.array([2., 3., .01, 5., 6.])
    a = np.array([3.1, -3.1, 1., -3., 3.])
    first = r._interpolate_curvature_vector(m, a, 'pchip')
    second = r._interpolate_curvature_vector(m, a + .7, 'pchip')
    np.testing.assert_allclose(first[0], second[0], atol=1e-12)
    np.testing.assert_allclose(np.exp(1j*(first[1]+.7)), np.exp(1j*second[1]), atol=1e-12)


def test_weights_are_continuous_at_coherence_thresholds_and_antipodal_branch():
    r = reconstructor()
    # Choose symmetric neighbors so the central resultant norm equals rho.
    for rho in [.25, .75]:
        a = np.arccos((np.sqrt((3*rho)**2 - np.sin(.1)**2) - np.cos(.1))/2)
        outputs = []
        for epsilon in [-1e-7, 1e-7]:
            angles = np.array([-a, -a, .1, a+epsilon, a+epsilon])
            outputs.append(r._smooth_curvature_direction(np.ones(5), angles))
        np.testing.assert_allclose(outputs[0], outputs[1], atol=1e-6)
    outputs = [r._smooth_curvature_direction(np.array([10.,10.,1.,10.,10.]),
               np.array([0.,0.,np.pi+epsilon,0.,0.]))[2] for epsilon in [-1e-7,1e-7]]
    np.testing.assert_allclose(outputs[0], outputs[1], atol=1e-6)


def test_ideal_constant_curvature_is_preserved_without_mutating_inputs():
    r = reconstructor()
    m = np.full(5, 10.)
    a = np.linspace(-.2, .2, 5)
    saved_m, saved_a = m.copy(), a.copy()
    c, _, _ = r._interpolate_curvature_vector(m, a, 'pchip')
    np.testing.assert_allclose(c, m, atol=1e-12)
    np.testing.assert_array_equal(m, saved_m)
    np.testing.assert_array_equal(a, saved_a)


@pytest.mark.parametrize('method', ['linear', 'pchip'])
def test_disabling_vector_filter_interpolates_raw_components(method):
    r = reconstructor()
    r.move_filter_for_vector = False
    r.interp_num = 9
    magnitude = np.array([1., 2., 3., 4., 5.])
    angle = np.array([0.2, -0.4, 0.9, -0.8, 1.2])

    curvature, interpolated_angle, _ = r._interpolate_curvature_vector(
        magnitude, angle, method
    )

    components = magnitude[:, None] * np.column_stack((np.cos(angle), np.sin(angle)))
    target = np.linspace(r.ad_samp_dist[0], r.ad_samp_dist[-1], r.interp_num)
    if method == 'linear':
        expected = np.column_stack([
            np.interp(target, r.ad_samp_dist, components[:, index])
            for index in range(2)
        ])
    else:
        expected = PchipInterpolator(r.ad_samp_dist, components, axis=0)(target)
    actual = curvature[:, None] * np.column_stack(
        (np.cos(interpolated_angle), np.sin(interpolated_angle))
    )
    np.testing.assert_allclose(actual, expected, atol=1e-12)


def test_enabling_vector_filter_keeps_direction_smoothing():
    r = reconstructor()
    r.move_filter_for_vector = True
    magnitude = np.array([5., 5., 0.2, 5., 5.])
    angle = np.array([0., 0., 1.2, 0., 0.])

    _, interpolated_angle, _ = r._interpolate_curvature_vector(
        magnitude, angle, 'pchip'
    )

    assert abs(interpolated_angle[2]) < 0.1
