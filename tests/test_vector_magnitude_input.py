"""Exercise numerical reconstruction without loading hardware/calibration dependencies."""
import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


@pytest.mark.parametrize('mode', ['vector_pchip', 'vector_linear', 'hermite'])
@pytest.mark.parametrize('virtual_points', [False, True])
def test_vector_bypasses_kalman_but_scalar_keeps_it(mode, virtual_points):
    tree = ast.parse((Path(__file__).parents[1] / 'reconstructor.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Reconstructor')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_reconstruct_frame')
    ns = {'np': np}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<reconstruct_frame>', 'exec'), ns)
    magnitude = np.array([.1, .2, 12., 20.])
    expected = np.r_[magnitude[0], magnitude, magnitude[-1]] if virtual_points else magnitude
    captured = {}

    def vector(magnitude, angle, method):
        captured['input'] = magnitude.copy()
        return magnitude, angle, np.arange(len(magnitude), dtype=float)

    def scalar(data, **kwargs):
        captured['input'] = data.copy()
        return data, np.arange(len(data), dtype=float)

    obj = SimpleNamespace(
        _Strain_2_Cur=lambda **kw: (magnitude.copy(), np.zeros(4)),
        zero_init=virtual_points, end_point=virtual_points, move_filter=3,
        _framewise_unwrap_limit=lambda **kw: kw['angle'],
        _moving_average_scipy=lambda **kw: kw['data'],
        _Kalman_filter=lambda **kw: kw['data'] * .5,
        kalman_params={'magnitude': {'Rk': .0001, 'Bk': .01}},
        curvature_interp=mode, nonnegative_curvature=False,
        _vector_curvature_method=lambda mode: mode.removeprefix('vector_'),
        _interpolate_curvature_vector=vector,
        _interpolate_curvature=scalar,
        _KT_Hermit_interp_tang=lambda data: (data, np.arange(len(data), dtype=float)),
        frame_rule='TNN', _parallel_frame=lambda **kw: (None,) * 6,
    )
    result = ns['_reconstruct_frame'](obj, None, 'dynamic', None, None, None, 1., [1., 0., 0.])
    np.testing.assert_array_equal(captured['input'], expected if mode.startswith('vector') else expected*.5)
    np.testing.assert_array_equal(result[-1]['magnitude'], magnitude)
    np.testing.assert_array_equal(result[-1]['cur_kal'], expected*.5)
