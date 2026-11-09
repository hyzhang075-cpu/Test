import copy
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_score_cli_aliases_share_canonical_destination():
    import main

    new_args = main.parse_main_args([
        '--task', 'score', '--end5cm_independent_weight_score', 'True',
    ])
    old_args = main.parse_main_args([
        '--task', 'score', '--end5cm_groupwise_weight_score', 'True',
    ])
    assert new_args.end5cm_independent_weight_score is True
    assert old_args.end5cm_independent_weight_score is True
    assert 'end5cm_groupwise_weight_score' not in {
        action.dest for action in main.build_argument_parser()._actions
    }


def test_package_cli_override_uses_canonical_score_flag(tmp_path):
    import main
    from tools.sensor_parameter_package import (
        build_sensor_package, write_sensor_package,
    )
    from tests.test_sensor_parameter_package import _report

    reports = [_report(d) for d in (0, 120, 240)]
    for report in reports:
        report['regions']['end5cm']['context']['weight_group_ids'] = [0, 0]
        report['regions']['end5cm']['context']['weight_score_mode'] = 'group_mean'
    package = build_sensor_package(main.build_argument_parser(), reports)
    assert package['shared_parameters']['runtime_control_parameters'][
        'end5cm_independent_weight_score'
    ] is True
    path = tmp_path / 'params.json'
    write_sensor_package(package, path)

    defaults = main.package_parser_defaults(package)
    assert defaults['end5cm_independent_weight_score'] is True
    assert defaults['end5cm_groupwise_weight_score'] is True

    args = main.parse_main_args([
        '--task', 'score', '--sensor_params', str(path),
        '--end5cm_independent_weight_score', 'False',
    ])
    assert args.end5cm_independent_weight_score is False


def test_relative_folder_override_is_resolved_from_calibration_root():
    import main

    args = main.parse_main_args([
        '--task', 'score', '--optimization_region', 'end5cm',
        '--calibration_data_root', '0909-06B6末端固定前端滑轨定标重测',
        '--folder_path', '5cm', '--radii', "{'circ': [0, 15]}",
    ])
    context = main.configure_calibration_args(args)
    expected = ROOT / '0909-06B6末端固定前端滑轨定标重测' / '5cm'
    assert Path(args.folder_path) == expected
    assert Path(context['folder_path']) == expected


def test_report_folder_is_serialized_relative_to_calibration_root():
    from calibration_batch import _report_relative_folder

    root = ROOT / '0909-06B6末端固定前端滑轨定标重测'
    assert _report_relative_folder(root / '5cm', root) == '5cm'


def test_weights_only_requires_explicit_or_package_slopes():
    import main

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end5cm',
        '--optim_weights_only', 'True',
    ])
    with pytest.raises(ValueError, match='sensor_params|--slopes'):
        main.configure_calibration_args(args)

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end5cm',
        '--optim_weights_only', 'True', '--slopes', 'None',
    ])
    with pytest.raises(ValueError, match='sensor_params|--slopes'):
        main.configure_calibration_args(args)


def test_weights_only_skips_slope_stage_and_preserves_slopes(monkeypatch):
    from optimiser import Optimiser
    from tests.test_end5cm_point_calibration import point_optimizer

    optim = point_optimizer()
    optim.optim_weights_only = True
    optim.source_sensor_params = 'params/source.json'
    optim.method = 'Powell'
    optim.hyper_params = [1, 1e-6, 1e-6]
    optim.rot_ang = 0.0
    optim.k_point = optim.k_end = optim.k_pitch = optim.k_radius = 1.0
    optim.avg_point_err = {'calib': 0.0}
    optim.avg_end_err = {'calib': 0.0}
    optim.avg_pitch_err = optim.avg_radius_err = 0.0
    before = copy.deepcopy(optim.slopes[optim.direct])
    calls = []

    def fake_stage(*, coeff, **kwargs):
        calls.append(coeff)
        return 0.2, 'converge', 0.3, []

    monkeypatch.setattr(optim, '_optim_one_coeff_until_stop', fake_stage)
    monkeypatch.setattr(optim, 'reconstruct_shapes', lambda **kwargs: (None, None))
    monkeypatch.setattr(optim, '_compute_error', lambda **kwargs: None)
    monkeypatch.setattr(optim, '_print_errors', lambda: None)

    result = Optimiser.optim_coeff(optim, verbose=False)

    assert calls == ['weights']
    np.testing.assert_array_equal(optim.slopes[optim.direct], before)
    assert result['stages']['slopes']['status'] == 'fixed'
    assert result['stages']['slopes']['source_sensor_params'] == 'params/source.json'
    assert 'not optimized' in result['loss_definitions']['slopes']


def test_weights_only_log_describes_fixed_slopes_without_slope_stage(monkeypatch, capsys):
    from optimiser import Optimiser
    from tests.test_end5cm_point_calibration import point_optimizer

    optim = point_optimizer()
    optim.optim_weights_only = True
    optim.source_sensor_params = 'params/source.json'
    optim.method = 'Powell'
    optim.hyper_params = [1, 1e-6, 1e-6]
    optim.rot_ang = 0.0
    optim.k_point = optim.k_end = optim.k_pitch = optim.k_radius = 1.0
    optim.avg_point_err = {'calib': 0.0}
    optim.avg_end_err = {'calib': 0.0}
    optim.avg_pitch_err = optim.avg_radius_err = 0.0
    monkeypatch.setattr(optim, '_optim_one_coeff_until_stop',
                        lambda *, coeff, **kwargs: (0.2, 'converge', 0.3, []))
    monkeypatch.setattr(optim, 'reconstruct_shapes', lambda **kwargs: (None, None))
    monkeypatch.setattr(optim, '_compute_error', lambda **kwargs: None)
    monkeypatch.setattr(optim, '_print_errors', lambda: None)

    Optimiser.optim_coeff(optim, verbose=False)
    output = capsys.readouterr().out
    assert 'fixed slopes, optimize weights only' in output
    assert 'slopes(真实点方向) -> weights' not in output


def test_coverage_report_uses_group0_mean_and_separate_tip_groups():
    from tools.end5_weight_coverage import compute_groupwise_weight_coverage

    samples = [
        {
            'keys': [30], 'theoretical_curvature_m_inv': 1000 / 30,
            'global_point_ids': [19, 20, 21, 22],
            'score_magnitude': [10., 20., 30., 40.],
            'weight_masses': [[1., 1., 1., 1.], [0., 0., 0., 0.]],
        },
        {
            'keys': [15], 'theoretical_curvature_m_inv': 1000 / 15,
            'global_point_ids': [19, 20, 21, 22],
            'score_magnitude': [12., 18., 60., 80.],
            'weight_masses': [[0., 0., 0., 0.], [1., 1., 1., 1.]],
        },
    ]
    report = compute_groupwise_weight_coverage(
        samples, thresholds=[1.0], weights=np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]),
        weight_bounds=(0.6, 5.0), group_ids=[0, 0, 1, 2], mass_threshold=0.05,
    )

    assert report['definition']['mass_threshold'] == 0.05
    assert report['groups']['0']['samples'][0]['base_magnitude'] == 15.0
    assert report['groups']['1']['samples'][1]['base_magnitude'] == 60.0
    assert report['groups']['2']['samples'][1]['base_magnitude'] == 80.0
    assert report['groups']['2']['samples'][1]['required_gain'] == pytest.approx((1000 / 15) / 80)
    assert report['groups']['0']['levels'][1]['mass_threshold_count'] == 1
    assert report['opt_bound_hits']['upper'] == 1


def test_coverage_excludes_zero_theory_curvature_from_required_gain_bounds():
    from tools.end5_weight_coverage import compute_groupwise_weight_coverage

    sample = {
        'keys': [0], 'theoretical_curvature_m_inv': 0.0,
        'global_point_ids': [19, 20, 21, 22],
        'score_magnitude': [10., 20., 30., 40.],
        'weight_masses': [[1., 1., 1., 1.], [0., 0., 0., 0.]],
    }
    report = compute_groupwise_weight_coverage(
        [sample], thresholds=[1.0],
        weights=np.ones((3, 2)), weight_bounds=(0.6, 5.0),
        group_ids=[0, 0, 1, 2],
    )
    for group in report['groups'].values():
        assert group['samples'][0]['required_gain'] is None
        assert group['theory_gain_over_bounds'] == []


@pytest.mark.parametrize('task', ['optim', 'recon'])
def test_single_region_end5cm_uses_local_phase_from_sensor_package(task):
    import main

    args = main.parse_main_args([
        '--task', task,
        '--sensor_params', str(ROOT / 'params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json'),
        '--optimization_region', 'end5cm', '--direct', '0',
    ])
    assert args.global_phases_set == pytest.approx(0.6969803684104529)


def test_optim_weights_only_is_not_persisted_in_sensor_package():
    import main
    from tools.sensor_parameter_package import build_sensor_package
    from tests.test_sensor_parameter_package import _report

    parser = main.build_argument_parser()
    package = build_sensor_package(parser, [_report(d) for d in (0, 120, 240)])
    assert 'optim_weights_only' not in package['shared_parameters']['runtime_control_parameters']
    assert main.package_parser_defaults(package)['optim_weights_only'] is False

    package['shared_parameters']['runtime_control_parameters']['optim_weights_only'] = True
    assert main.package_parser_defaults(package)['optim_weights_only'] is False


def test_calibration_radius_mismatch_fails_before_real_point_loss():
    from optimiser import Optimiser

    optim = Optimiser.__new__(Optimiser)
    optim.exp_directs = [0]
    optim.radii = {0: {'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200, 100, 75, 50, 30, 20, 15]}}
    optim.processed_Data = {'circ': {0: {
        0: np.zeros((2, 2)), 2000: np.zeros((2, 2)), 1500: np.zeros((2, 2)),
        1000: np.zeros((2, 2)), 800: np.zeros((2, 2)), 600: np.zeros((2, 2)),
        400: np.zeros((2, 2)), 300: np.zeros((2, 2)), 150: np.zeros((2, 2)),
        100: np.zeros((2, 2)), 50: np.zeros((2, 2)), 30: np.zeros((2, 2)),
        20: np.zeros((2, 2)), 15: np.zeros((2, 2)),
    }}}

    with pytest.raises(ValueError, match=r'missing configured radii=.*200.*75') as error:
        optim.validate_calibration_data_radii()
    assert 'unexpected data radii=[150]' in str(error.value)


def test_single_direction_radius_validation_ignores_unloaded_directions():
    from optimiser import Optimiser

    radii = [0, 30, 15]
    optim = Optimiser.__new__(Optimiser)
    optim.direct = 0
    optim.exp_directs = [0, 120, 240]
    optim.radii = {direct: {'circ': radii} for direct in optim.exp_directs}
    optim.processed_Data = {'circ': {0: {
        0: np.zeros((2, 2)), 30: np.zeros((2, 2)), 15: np.zeros((2, 2)),
    }}}

    optim.validate_calibration_data_radii()


def test_single_direction_radius_validation_still_checks_current_direct():
    from optimiser import Optimiser

    optim = Optimiser.__new__(Optimiser)
    optim.direct = 0
    optim.exp_directs = [0, 120, 240]
    optim.radii = {direct: {'circ': [0, 30, 15]} for direct in optim.exp_directs}
    optim.processed_Data = {'circ': {0: {
        0: np.zeros((2, 2)), 30: np.zeros((2, 2)),
    }}}

    with pytest.raises(ValueError, match=r'direct=0.*missing configured radii=\[15\]'):
        optim.validate_calibration_data_radii()


def test_explicit_new_radii_config_matches_end5cm_data_directory():
    import main

    args = main.parse_main_args([
        '--task', 'score', '--sensor_params', str(
            ROOT / 'params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json'),
        '--optimization_region', 'end5cm',
        '--calibration_data_root', '0909-06B6末端固定前端滑轨定标重测',
        '--folder_path', '5cm',
        '--radii', "{'circ': [0,2000,1500,1000,800,600,400,300,150,100,50,30,20,15]}",
    ])
    context = main.configure_calibration_args(args)
    assert context['radii']['circ'] == [0, 2000, 1500, 1000, 800, 600, 400, 300, 150, 100, 50, 30, 20, 15]
