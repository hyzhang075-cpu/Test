from types import MethodType

import numpy as np
import pytest

from optimiser import Optimiser


def _optimizer_returning(loss):
    optim = Optimiser.__new__(Optimiser)
    optim.direct = 240
    optim.max_iter = 1
    optim.min_loss_diff = 1e-4
    optim.slope_upper_bound = 50.0
    optim.weights = {240: np.ones(2)}
    optim.slopes = {240: np.ones((2, 1))}

    def fake_iter(self, **kwargs):
        self.weights[self.direct] = np.full(2, 2.0)
        return loss, 1.0

    optim._optim_coeff_iter = MethodType(fake_iter, optim)
    return optim


def test_finite_worse_candidate_is_no_improvement_and_rolls_back():
    optim = _optimizer_returning(1.1)
    final_loss, status, start_loss, recoveries = optim._optim_one_coeff_until_stop(
        'weights', None, options=None, verbose=False,
    )
    assert (final_loss, status, start_loss) == (1.0, 'no_improvement', 1.0)
    assert recoveries == []
    assert optim.weights[240].tolist() == [1.0, 1.0]


def test_nonfinite_candidate_is_divergence_and_rolls_back():
    optim = _optimizer_returning(np.nan)
    final_loss, status, start_loss, recoveries = optim._optim_one_coeff_until_stop(
        'weights', None, options=None, verbose=False,
    )
    assert (final_loss, status, start_loss) == (1.0, 'diverge', 1.0)
    assert recoveries == []
    assert optim.weights[240].tolist() == [1.0, 1.0]


def _optimizer_with_two_rounds():
    optim = Optimiser.__new__(Optimiser)
    optim.direct = 0
    optim.max_iter = 2
    optim.min_loss_diff = 1e-4
    optim.slope_upper_bound = 50.0
    optim.weights = {0: np.ones(2)}
    optim.slopes = {0: np.ones((2, 1))}
    return optim


def test_unknown_opcode_retries_failed_round_from_last_successful_snapshot():
    optim = _optimizer_with_two_rounds()
    calls = []

    def fake_iter(self, **kwargs):
        iteration = kwargs['i']
        calls.append(iteration)
        if iteration == 0:
            self.weights[self.direct] = np.full(2, 2.0)
            return 0.8, 1.0
        if calls.count(1) == 1:
            self.weights[self.direct] = np.full(2, 99.0)
            self.slopes[self.direct] = np.full((2, 1), 99.0)
            raise SystemError('unknown opcode')
        assert self.weights[self.direct].tolist() == [2.0, 2.0]
        assert self.slopes[self.direct].tolist() == [[1.0], [1.0]]
        self.weights[self.direct] = np.full(2, 3.0)
        return 0.7, 0.8

    optim._optim_coeff_iter = MethodType(fake_iter, optim)

    final_loss, status, start_loss, recoveries = optim._optim_one_coeff_until_stop(
        'weights', None, options=None, verbose=False,
    )

    assert (final_loss, status, start_loss) == (0.7, 'max_iter', 1.0)
    assert calls == [0, 1, 1]
    assert recoveries == [{
        'iteration': 1,
        'exception_type': 'SystemError',
        'message': 'unknown opcode',
        'retry_count': 1,
        'occurrences': 1,
        'outcome': 'retry_succeeded',
    }]
    assert optim.weights[0].tolist() == [3.0, 3.0]


def test_repeated_unknown_opcode_falls_back_to_last_successful_round():
    optim = _optimizer_with_two_rounds()
    calls = []

    def fake_iter(self, **kwargs):
        iteration = kwargs['i']
        calls.append(iteration)
        if iteration == 0:
            self.weights[self.direct] = np.full(2, 2.0)
            return 0.8, 1.0
        self.weights[self.direct] = np.full(2, 99.0)
        self.slopes[self.direct] = np.full((2, 1), 99.0)
        raise SystemError('unknown opcode')

    optim._optim_coeff_iter = MethodType(fake_iter, optim)

    final_loss, status, start_loss, recoveries = optim._optim_one_coeff_until_stop(
        'weights', None, options=None, verbose=False,
    )

    assert (final_loss, status, start_loss) == (0.8, 'runtime_error_fallback', 1.0)
    assert calls == [0, 1, 1]
    assert recoveries == [{
        'iteration': 1,
        'exception_type': 'SystemError',
        'message': 'unknown opcode',
        'retry_count': 1,
        'occurrences': 2,
        'outcome': 'fallback_previous_iteration',
        'fallback_iteration': 0,
        'fallback_loss': 0.8,
    }]
    assert optim.weights[0].tolist() == [2.0, 2.0]
    assert optim.slopes[0].tolist() == [[1.0], [1.0]]


def test_repeated_unknown_opcode_in_first_round_still_raises():
    optim = _optimizer_with_two_rounds()
    calls = []

    def fake_iter(self, **kwargs):
        calls.append(kwargs['i'])
        self.weights[self.direct] = np.full(2, 99.0)
        raise SystemError('unknown opcode')

    optim._optim_coeff_iter = MethodType(fake_iter, optim)

    with pytest.raises(SystemError, match='unknown opcode'):
        optim._optim_one_coeff_until_stop('weights', None, options=None, verbose=False)

    assert calls == [0, 0]
    assert optim.weights[0].tolist() == [1.0, 1.0]


def test_unrelated_system_error_is_not_retried():
    optim = _optimizer_with_two_rounds()
    calls = []

    def fake_iter(self, **kwargs):
        calls.append(kwargs['i'])
        raise SystemError('internal invariant failed')

    optim._optim_coeff_iter = MethodType(fake_iter, optim)

    with pytest.raises(SystemError, match='internal invariant failed'):
        optim._optim_one_coeff_until_stop('weights', None, options=None, verbose=False)

    assert calls == [0]


def test_optim_coeff_continues_to_weights_after_slope_runtime_fallback():
    optim = Optimiser.__new__(Optimiser)
    optim.method = 'Nelder-Mead'
    optim.direct = 0
    optim.rot_ang = 0.0
    optim.weights = {0: np.ones(2)}
    optim.slopes = {0: np.ones((2, 1))}
    optim.calib_shapes = ['circ']
    optim.end5cm_point_calib = False
    optim.optim_weights_only = False
    optim.source_sensor_params = None
    optim.validate_calibration_data_radii = MethodType(lambda self: None, optim)
    optim._ensure_coverage_support_map = MethodType(lambda self: None, optim)
    calls = []
    slope_recovery = [{
        'iteration': 3,
        'exception_type': 'SystemError',
        'message': 'unknown opcode',
        'retry_count': 1,
        'occurrences': 2,
        'outcome': 'fallback_previous_iteration',
        'fallback_iteration': 2,
        'fallback_loss': 0.0037,
    }]

    def fake_stage(self, coeff, **kwargs):
        calls.append(coeff)
        if coeff == 'slopes':
            return 0.0037, 'runtime_error_fallback', 0.01, slope_recovery
        return 0.0029, 'converge', 0.004, []

    def fake_reconstruct(self, **kwargs):
        return np.zeros((2, 3)), np.array([0.0, 1.0])

    def fake_compute_error(self, **kwargs):
        self.avg_point_err = {'calib': 0.001}
        self.avg_end_err = {'calib': 0.001}
        self.avg_pitch_err = 0.0
        self.avg_radius_err = 0.0

    optim._optim_one_coeff_until_stop = MethodType(fake_stage, optim)
    optim.reconstruct_shapes = MethodType(fake_reconstruct, optim)
    optim._compute_error = MethodType(fake_compute_error, optim)
    optim._print_errors = MethodType(lambda self: None, optim)

    stages = optim.optim_coeff(verbose=False)['stages']

    assert calls == ['slopes', 'weights']
    assert stages['slopes']['status'] == 'runtime_error_fallback'
    assert stages['slopes']['recoveries'] == slope_recovery
    assert stages['weights']['status'] == 'converge'
    assert 'recoveries' not in stages['weights']
