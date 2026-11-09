from copy import deepcopy

import numpy as np
import pytest

import main
from calibration_batch import optimizer_parameters, prepare_calibration_jobs
from optimiser import Optimiser
from tests.test_end5cm_point_calibration import point_optimizer
from tests.test_sensor_parameter_package import _parser, _report
from tools.sensor_parameter_package import (
    build_sensor_package,
    package_parser_defaults,
    write_sensor_package,
)


@pytest.mark.parametrize(
    ('region', 'objective'),
    [('full', 'geometry'), ('end15cm', 'real_points'), ('end5cm', 'geometry')],
)
def test_end15cm_flag_selects_only_end15cm_objective(region, objective):
    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', region,
        '--end15cm_point_calib', 'True',
    ])
    context = main.configure_calibration_args(args)

    assert context['calibration_objective'] == objective
    assert optimizer_parameters(args)['real_point_calib'] is (region == 'end15cm')
    assert optimizer_parameters(args)['end5cm_point_calib'] is False


def test_batch_routes_both_real_point_flags_without_changing_full():
    args = main.parse_main_args([
        '--task', 'optim', '--multi_region_calib', 'True',
        '--end15cm_point_calib', 'True', '--end5cm_point_calib', 'True',
    ])
    jobs = prepare_calibration_jobs(args, main.configure_calibration_args)

    assert [context['calibration_objective'] for _, context in jobs] == [
        'geometry', 'real_points', 'real_points',
    ]
    assert [optimizer_parameters(job)['real_point_calib'] for job, _ in jobs] == [
        False, True, True,
    ]


def test_end15cm_real_point_objective_reuses_direction_and_magnitude_losses():
    optim = point_optimizer()
    optim.end5cm_point_calib = False
    optim.real_point_calib = True
    slopes = np.full(4, 0.2)

    direction = optim._loss_fn(0, np.ones(2), slopes, 50., force_ideal_magnitude=True)
    magnitude = optim._loss_fn(0, np.full(2, .8), slopes, 50., force_ideal_magnitude=False)

    assert direction > 0
    assert magnitude == pytest.approx(.04)


def test_end15cm_with_end5cm_package_keeps_end5cm_weight_features_outside_region():
    args = main.parse_main_args([
        '--task', 'optim', '--sensor_params',
        'params/08B5_NeTi_end5NewOptim.json',
        '--optimization_region', 'end15cm',
        '--end15cm_point_calib', 'True',
    ])
    context = main.configure_calibration_args(args)
    parameters = optimizer_parameters(args)

    assert context['calibration_objective'] == 'real_points'
    assert context['weight_group_ids'] is None
    assert context['end5cm_coverage_aware_weights'] is False
    assert parameters['real_point_calib'] is True
    assert parameters['end5cm_coverage_aware_weights'] is False
    assert parameters['end5cm_independent_weight_score'] is False


def test_end15cm_point_mode_rejects_non_circular_calibration():
    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end15cm',
        '--end15cm_point_calib', 'True', '--radii', "{'S': [30]}",
    ])
    with pytest.raises(ValueError, match='circ'):
        main.configure_calibration_args(args)


def test_end15cm_weights_only_remains_end5cm_specific():
    args = main.parse_main_args([
        '--task', 'optim', '--sensor_params', 'params/08B5_NeTi_end5NewOptim.json',
        '--optimization_region', 'end15cm',
        '--end15cm_point_calib', 'True', '--optim_weights_only', 'True',
    ])
    with pytest.raises(ValueError, match='end5cm_point_calib'):
        main.configure_calibration_args(args)


def test_end15cm_objective_roundtrips_without_changing_full_or_end5cm(tmp_path):
    reports = [_report(direct) for direct in (0, 120, 240)]
    for report in reports:
        report['regions']['end15cm']['context']['calibration_objective'] = 'real_points'

    package = build_sensor_package(_parser(), reports)
    assert [package['regions'][region]['calibration_objective']
            for region in ('full', 'end15cm', 'end5cm')] == [
                'geometry', 'real_points', 'geometry',
            ]
    assert package_parser_defaults(package)['end15cm_point_calib'] is True
    path = tmp_path / 'end15cm-point-mode.json'
    write_sensor_package(package, path)
    args = main.parse_main_args([
        '--task', 'recon', '--sensor_params', str(path),
        '--optimization_region', 'end15cm',
    ])
    assert args.end15cm_point_calib is True
    assert args.end5cm_point_calib is False

    legacy = build_sensor_package(_parser(), [_report(direct) for direct in (0, 120, 240)])
    assert package_parser_defaults(legacy)['end15cm_point_calib'] is False
    invalid = deepcopy(reports)
    for report in invalid:
        report['regions']['full']['context']['calibration_objective'] = 'real_points'
    with pytest.raises(ValueError, match='full calibration_objective'):
        build_sensor_package(_parser(), invalid)
