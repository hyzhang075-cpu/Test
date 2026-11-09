from pathlib import Path
import json
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.calibration_validation as validation_module

from tools.calibration_validation import (
    DEFAULT_VALIDATION_POLICY,
    build_phase_transport_evidence,
    boundary_diagnostics,
    circular_angle_error_deg,
    compute_curve_metrics,
    evaluate_direction_gates,
    integrate_phase_to_point,
    straight_prefix_circular_tail,
    validate_score_evidence,
)


def test_curve_metrics_include_tip_tangent_and_pose_error():
    ideal = np.column_stack((np.linspace(0, .1, 6), np.zeros((6, 2))))
    result = ideal.copy()
    result[:, 1] += np.linspace(0, .002, 6)
    metrics = compute_curve_metrics(
        result, ideal, result_tangent=[1, .1, 0], ideal_tangent=[1, 0, 0],
        distances=np.linspace(0, .1, 6), evaluation_start_m=.06,
        full_length_m=.2,
    )
    assert metrics['mean_point_error_mm'] > 0
    assert metrics['tip_position_error_mm'] == pytest.approx(2.0)
    assert metrics['tip_tangent_error_deg'] > 0
    assert metrics['pose_error_mm'] > metrics['tip_position_error_mm']
    assert metrics['evaluated_region_point_error_mm'] > metrics['mean_point_error_mm']
    assert metrics['tip_position_error_percent_full_length'] == pytest.approx(1.0)


def test_tail_ideal_is_continuous_at_region_start():
    distances = np.array([0, .05, .1, .15, .2])
    curve, tangent = straight_prefix_circular_tail(distances, .1, .03)
    np.testing.assert_allclose(curve[2], [.1, 0, 0])
    np.testing.assert_allclose(tangent, [np.cos(.1/.03), np.sin(.1/.03), 0])
    assert np.all(np.isfinite(curve))


def test_boundary_diagnostics_reports_each_region_transition():
    diagnostics = {
        'final_weight': [1, 1, 1, 2, 2, 3],
        'slope_map': [10, 10, 10, 20, 20, 30],
        'base_magnitude': [0, 1, 2, 3, 4, 5],
        'final_magnitude': [0, 1, 2, 4, 5, 7],
        'final_angle': [0, 0, 0, .1, .1, .3],
        'final_theta_dynamic': [[0, 0, 0, .2, .2, .4]],
    }
    result = boundary_diagnostics(diagnostics, [3, 5])
    assert list(result) == ['3->4', '5->6']
    assert result['3->4']['weight_jump'] == 1
    assert result['5->6']['slope_jump'] == 10
    assert result['5->6']['curvature_vector_jump_m_inv'] > 0


def test_circular_phase_transport_wraps_and_end5cm_is_non_blocking():
    assert circular_angle_error_deg(np.deg2rad(179), np.deg2rad(-179)) == pytest.approx(2)
    distances = [0.0, 0.1, 0.2, 0.3]
    slopes = [0.0, 1.0, 2.0, 3.0]
    phase_at_two = integrate_phase_to_point(0.5, distances, slopes, 2)
    assert phase_at_two == pytest.approx(0.8)

    evidence = build_phase_transport_evidence(
        0.5, distances, slopes,
        local_phases={'end15cm': 0.8 + np.deg2rad(29.9),
                      'end5cm': 1.1 + np.deg2rad(30.1)},
        start_indices={'end15cm': 2, 'end5cm': 3}, tolerance_deg=30,
    )
    assert evidence['end15cm']['within_30_deg'] is True
    assert evidence['end15cm']['blocking'] is True
    assert evidence['end5cm']['within_30_deg'] is False
    assert evidence['end5cm']['blocking'] is False


def _score_package():
    return {
        'sensor_id': 'sensor-A',
        'regions': {
            'full': {'thresholds': [1.0, 2.0]},
            'end15cm': {'thresholds': [1.0, 3.0]},
            'end5cm': {'thresholds': [1.0, 3.0, 45.0]},
        },
    }


def _score_report():
    def region(thresholds, values):
        return {
            'status': 'complete',
            'score_distribution': {
                'thresholds': thresholds,
                'sigmoid_10_90_width_m_inv': .9,
                'samples': [{
                    'keys': [15],
                    'score_magnitude': values,
                    'quantiles': {'min': min(values), 'median': 2.0,
                                  'p90': max(values), 'max': max(values)},
                }],
            },
        }
    return {
        'sensor_id': 'sensor-A', 'task': 'score', 'direct': 0,
        'regions': {
            'full': region([1.0, 2.0], [0.0, 3.0]),
            'end15cm': region([1.0, 3.0], [0.0, 4.0]),
            'end5cm': region([1.0, 3.0, 45.0], [0.0, 50.0]),
        },
    }


def test_score_evidence_is_shared_and_requires_empirical_threshold_crossing():
    evidence = validate_score_evidence(_score_package(), _score_report(), 'score/results.json')
    assert evidence['score_thresholds_verified'] is True
    assert evidence['source_path'] == 'score/results.json'
    assert evidence['regions']['end5cm']['observed_max_m_inv'] == 50.0

    report = _score_report()
    report['regions']['end5cm']['score_distribution']['samples'][0]['score_magnitude'] = [0, 40]
    failed = validate_score_evidence(_score_package(), report, 'score/results.json')
    assert failed['score_thresholds_verified'] is False
    assert any('45.0' in reason for reason in failed['failures'])


@pytest.mark.parametrize('mutation, match', [
    ('sensor', 'sensor_id'),
    ('threshold', 'thresholds'),
    ('missing', 'end15cm'),
    ('nonfinite', '非有限'),
])
def test_score_evidence_rejects_incompatible_reports(mutation, match):
    report = _score_report()
    if mutation == 'sensor':
        report['sensor_id'] = 'sensor-B'
    elif mutation == 'threshold':
        report['regions']['full']['score_distribution']['thresholds'] = [1.0, 2.5]
    elif mutation == 'missing':
        del report['regions']['end15cm']
    else:
        report['regions']['full']['score_distribution']['samples'][0]['score_magnitude'][0] = float('nan')
    evidence = validate_score_evidence(_score_package(), report, 'score/results.json')
    assert evidence['score_thresholds_verified'] is False
    assert any(match in reason for reason in evidence['failures'])


def _metric(mean_percent=.5, tip_percent=.5, tangent_deg=5.0):
    return {
        'mean_point_error_percent_full_length': mean_percent,
        'evaluated_region_point_error_percent_full_length': mean_percent,
        'tip_position_error_percent_full_length': tip_percent,
        'tip_tangent_error_deg': tangent_deg,
    }


def test_direction_gates_accept_policy_boundaries_and_nonblocking_end5_phase():
    replay = {
        'full': {
            '2000': {'baseline': _metric(.4), 'candidate': _metric(.6)},
        },
        'end15cm': {
            '30': {'baseline': _metric(.8), 'candidate': _metric(.7),
                   'tail_improvement_percent': 12.5},
        },
        'end5cm': {
            radius: {'baseline': _metric(1.0), 'candidate': _metric(.9),
                     'tail_improvement_percent': 10.0}
            for radius in ('30', '20', '15')
        },
    }
    report = {
        'replay': replay,
        'phase_transport': {
            'end15cm': {'max_phase_error_deg': 30.0, 'within_30_deg': True, 'blocking': True},
            'end5cm': {'max_phase_error_deg': 90.0, 'within_30_deg': False, 'blocking': False},
        },
        'max_boundary_curvature_angle_jump_deg': 30.0,
    }
    result = evaluate_direction_gates(
        report, optimization_usable=True, score_verified=True,
        policy=DEFAULT_VALIDATION_POLICY,
    )
    assert result['quality_gates']['end15cm_phase_verified'] is True
    assert result['quality_gates']['full_geometry_verified'] is True
    assert result['deployment_ready'] is True


@pytest.mark.parametrize('field,value,expected', [
    ('full_error', 1.01, 'full mean point error'),
    ('regression', .21, 'full regression'),
    ('improvement', 9.9, 'tail improvement'),
    ('tip', 1.01, 'tip position'),
    ('tangent', 10.1, 'tip tangent'),
    ('boundary', 30.1, 'boundary curvature angle'),
    ('phase', 30.1, 'end15cm phase'),
])
def test_direction_gates_name_each_failed_limit(field, value, expected):
    replay = {
        'full': {'2000': {'baseline': _metric(.8), 'candidate': _metric(.8)}},
        'end5cm': {r: {'baseline': _metric(.9), 'candidate': _metric(.8),
                       'tail_improvement_percent': 11.111}
                   for r in ('30', '20', '15')},
    }
    report = {
        'replay': replay,
        'phase_transport': {
            'end15cm': {'max_phase_error_deg': 20, 'within_30_deg': True, 'blocking': True},
            'end5cm': {'max_phase_error_deg': 80, 'within_30_deg': False, 'blocking': False},
        },
        'max_boundary_curvature_angle_jump_deg': 20,
    }
    if field == 'full_error':
        replay['full']['2000']['candidate']['mean_point_error_percent_full_length'] = value
    elif field == 'regression':
        replay['full']['2000']['baseline']['mean_point_error_percent_full_length'] = .8
        replay['full']['2000']['candidate']['mean_point_error_percent_full_length'] = .8 + value
    elif field == 'improvement':
        replay['end5cm']['15']['tail_improvement_percent'] = value
    elif field == 'tip':
        replay['full']['2000']['candidate']['tip_position_error_percent_full_length'] = value
    elif field == 'tangent':
        replay['full']['2000']['candidate']['tip_tangent_error_deg'] = value
    elif field == 'boundary':
        report['max_boundary_curvature_angle_jump_deg'] = value
    else:
        report['phase_transport']['end15cm'].update(
            max_phase_error_deg=value, within_30_deg=False,
        )
    result = evaluate_direction_gates(report, True, True, DEFAULT_VALIDATION_POLICY)
    assert result['deployment_ready'] is False
    assert any(expected in failure for failure in result['failures'])


def test_validation_cli_writes_report_and_separate_validated_package(tmp_path, monkeypatch):
    metrics = _metric()
    metrics.update(tip_position_error_mm=4.0)
    report = {
        'global_phases_set': -.7,
        'rot_ang': 31.8,
        'shared_quality_gates': {'score_thresholds_verified': True},
        'score_evidence': {'source_path': 'score/results.json', 'failures': []},
        'directions': {
            str(direct): {
                'deployment_ready': direct == 0,
                'quality_gates': {
                    'optimization_usable': direct != 240,
                    'end15cm_phase_verified': direct == 0,
                    'full_geometry_verified': direct == 0,
                },
                'failures': [] if direct == 0 else ['failed'],
                'phase_transport': {
                    'end15cm': {'max_phase_error_deg': 10, 'tolerance_deg': 30,
                                'within_30_deg': True, 'blocking': True},
                    'end5cm': {'max_phase_error_deg': 80, 'tolerance_deg': 30,
                               'within_30_deg': False, 'blocking': False},
                },
                'replay': {'full': {'200': {
                    'baseline': metrics, 'candidate': metrics,
                    'tail_improvement_percent': 0,
                }}},
            }
            for direct in (0, 120, 240)
        },
    }
    source = tmp_path / 'source.json'
    source.write_text('{}', encoding='utf-8')
    json_output = tmp_path / 'report.json'
    markdown_output = tmp_path / 'report.md'
    package_output = tmp_path / 'validated.json'
    monkeypatch.setattr(validation_module, 'validate_multiregion_package',
                        lambda *args, **kwargs: report)
    from tools import sensor_parameter_package
    monkeypatch.setattr(sensor_parameter_package, 'load_sensor_package', lambda path: {'source': True})
    monkeypatch.setattr(sensor_parameter_package, 'apply_validation_results',
                        lambda package, evidence: {'validated': evidence is report})
    monkeypatch.setattr(sensor_parameter_package, 'write_sensor_package',
                        lambda package, path: Path(path).write_text(json.dumps(package), encoding='utf-8'))

    _, validated = validation_module.main([
        '--sensor-params', str(source), '--score-results', 'score-dir',
        '--json-output', str(json_output), '--markdown-output', str(markdown_output),
        '--package-output', str(package_output),
    ])

    assert validated == {'validated': True}
    assert json.loads(json_output.read_text(encoding='utf-8'))['directions']['0']['deployment_ready']
    assert 'Direction gates' in markdown_output.read_text(encoding='utf-8')
    assert json.loads(package_output.read_text(encoding='utf-8')) == {'validated': True}
    assert source.read_text(encoding='utf-8') == '{}'
