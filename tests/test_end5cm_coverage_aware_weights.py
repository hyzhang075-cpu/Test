import numpy as np
import pytest


GROUP_IDS = [0, 0, 1, 2]
THRESHOLDS = [1.0, 2.0, 10.0, 20.0, 30.0]


def _sample(radius, level_masses, *, theory=None):
    masses = np.zeros((len(THRESHOLDS) + 1, 4), dtype=float)
    for group, level in level_masses.items():
        members = np.flatnonzero(np.asarray(GROUP_IDS) == group)
        masses[level, members] = 1.0
    return {
        'keys': [radius],
        'theoretical_curvature_m_inv': 1000 / radius if theory is None and radius else theory,
        'score_magnitude': [2.0, 2.0, 2.0, 2.0],
        'global_point_ids': [19, 20, 21, 22],
        'weight_masses': masses.tolist(),
    }


def test_support_map_excludes_radius_zero_and_keeps_groups_independent():
    from tools.end5_weight_coverage import build_groupwise_support_map

    samples = [
        _sample(0, {0: 5, 1: 5, 2: 5}, theory=0.0),
        _sample(20, {0: 0, 1: 2, 2: 4}),
        _sample(10, {0: 1, 1: 3, 2: 5}),
    ]
    support = build_groupwise_support_map(
        samples, thresholds=THRESHOLDS, group_ids=GROUP_IDS,
        min_effective_samples=1.0, min_max_mass=0.05,
    )

    assert support['groups']['0']['reliable_levels'] == [0, 1]
    assert support['groups']['1']['reliable_levels'] == [2, 3]
    assert support['groups']['2']['reliable_levels'] == [4, 5]
    assert support['groups']['0']['derived_levels'] == [2, 3, 4, 5]
    assert support['definition']['excluded_radius_zero_samples'] == 1


def test_support_map_rejects_invalid_threshold_coordinates_and_mass_shape():
    from tools.end5_weight_coverage import build_groupwise_support_map

    with pytest.raises(ValueError, match='thresholds'):
        build_groupwise_support_map([], thresholds=[2.0, 1.0], group_ids=GROUP_IDS)
    with pytest.raises(ValueError, match='weight_masses'):
        build_groupwise_support_map(
            [{'keys': [10], 'weight_masses': [[1.0, 1.0, 1.0, 1.0]]}],
            thresholds=THRESHOLDS, group_ids=GROUP_IDS,
        )


def test_log_interpolation_uses_threshold_coordinates_and_neutral_edges():
    from tools.end5_weight_coverage import expand_groupwise_weights

    support = {
        'thresholds': [1.0, 2.0, 10.0],
        'num_levels': 4,
        'groups': {
            '0': {'free_levels': [0, 2], 'derived_levels': [1, 3]},
            '1': {'free_levels': [], 'derived_levels': [0, 1, 2, 3]},
            '2': {'free_levels': [1, 2], 'derived_levels': [0, 3]},
        },
    }
    expanded = expand_groupwise_weights(
        {'0': {0: 1.0, 2: 9.0}, '1': {}, '2': {1: 2.0, 2: 8.0}},
        support,
    )

    assert expanded.shape == (3, 4)
    assert expanded[0, 1] == pytest.approx(3.0)
    assert expanded[0, 3] == pytest.approx(1.0)
    assert np.all(expanded[1] == 1.0)
    assert expanded[2, 0] == pytest.approx(1.0)
    assert expanded[2, 3] == pytest.approx(1.0)


def test_log_interpolation_uses_level_zero_edge_then_actual_threshold_coordinates():
    from tools.end5_weight_coverage import expand_groupwise_weights

    support = {
        'thresholds': [1.0, 4.0, 10.0], 'num_levels': 4,
        'groups': {'0': {'free_levels': [1, 3], 'derived_levels': [0, 2]}},
    }
    expanded = expand_groupwise_weights({'0': {1: 1.0, 3: 27.0}}, support)

    # level 2 is at threshold 4 between anchors at 1 and 10: fraction 1/3.
    assert expanded[0, 2] == pytest.approx(27.0 ** (1 / 3))
    assert expanded[0, 0] == pytest.approx(1.0)


def test_effective_sample_count_is_score_mass_not_nonzero_mass_count():
    from tools.end5_weight_coverage import build_groupwise_support_map

    weak = build_groupwise_support_map(
        [
            {'keys': [10], 'theoretical_curvature_m_inv': 100.0,
             'weight_masses': [[0.4], [0.4]]},
            {'keys': [20], 'theoretical_curvature_m_inv': 50.0,
             'weight_masses': [[0.4], [0.4]]},
        ], thresholds=[1.0], group_ids=[0],
        min_effective_samples=1.0, min_max_mass=0.05,
    )
    strong = build_groupwise_support_map(
        [
            {'keys': [10], 'theoretical_curvature_m_inv': 100.0,
             'weight_masses': [[0.6], [0.6]]},
            {'keys': [20], 'theoretical_curvature_m_inv': 50.0,
             'weight_masses': [[0.5], [0.5]]},
        ], thresholds=[1.0], group_ids=[0],
        min_effective_samples=1.0, min_max_mass=0.05,
    )

    assert weak['groups']['0']['levels'][0]['effective_sample_count'] == pytest.approx(0.8)
    assert weak['groups']['0']['reliable_levels'] == []
    assert strong['groups']['0']['levels'][0]['effective_sample_count'] == pytest.approx(1.1)
    assert strong['groups']['0']['reliable_levels'] == [0, 1]


def test_multi_level_internal_gap_is_order_independent():
    from tools.end5_weight_coverage import expand_groupwise_weights

    support = {
        'thresholds': [1.0, 2.0, 10.0], 'num_levels': 4,
        'groups': {'0': {'free_levels': [0, 3], 'derived_levels': [1, 2]}},
    }
    forward = expand_groupwise_weights({'0': {0: 1.0, 3: 16.0}}, support)
    reversed_gap = dict(support)
    reversed_gap['groups'] = {'0': {'free_levels': [3, 0], 'derived_levels': [2, 1]}}
    backward = expand_groupwise_weights({'0': {3: 16.0, 0: 1.0}}, reversed_gap)
    np.testing.assert_allclose(forward, backward)


def test_expansion_rejects_non_positive_anchor_and_reacts_to_candidate_changes():
    from tools.end5_weight_coverage import expand_groupwise_weights

    support = {
        'thresholds': THRESHOLDS[:3],
        'num_levels': 4,
        'groups': {
            '0': {'free_levels': [0, 2], 'derived_levels': [1, 3]},
            '1': {'free_levels': [], 'derived_levels': [0, 1, 2, 3]},
            '2': {'free_levels': [], 'derived_levels': [0, 1, 2, 3]},
        },
    }
    first = expand_groupwise_weights(
        {'0': {0: 1.0, 2: 9.0}, '1': {}, '2': {}}, support,
    )
    second = expand_groupwise_weights(
        {'0': {0: 1.0, 2: 4.0}, '1': {}, '2': {}}, support,
    )
    assert first[0, 1] != pytest.approx(second[0, 1])
    with pytest.raises(ValueError, match='positive'):
        expand_groupwise_weights(
            {'0': {0: 0.0, 2: 9.0}, '1': {}, '2': {}}, support,
        )


def test_coverage_aware_cli_defaults_off_and_requires_the_three_end5cm_modes():
    import main

    args = main.parse_main_args(['--task', 'optim'])
    assert args.end5cm_coverage_aware_weights is False
    assert args.end5cm_min_weight_effective_samples == 1.0
    assert args.end5cm_min_weight_max_mass == 0.05
    assert args.end5cm_uncovered_weight_policy == 'interpolate_neutral_edges'

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end5cm',
        '--end5cm_coverage_aware_weights', 'True',
    ])
    with pytest.raises(ValueError, match='end5cm_point_calib'):
        main.configure_calibration_args(args)

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end5cm',
        '--end5cm_point_calib', 'True', '--end5cm_independent_weights', 'True',
        '--end5cm_coverage_aware_weights', 'True',
    ])
    with pytest.raises(ValueError, match='end5cm_independent_weight_score'):
        main.configure_calibration_args(args)


def test_coverage_aware_weight_indices_are_free_only_and_expansion_is_dynamic(monkeypatch):
    from optimiser import Optimiser

    optim = Optimiser.__new__(Optimiser)
    optim.direct = 0
    optim.num_levels = 4
    optim.weight_group_ids = np.asarray(GROUP_IDS)
    optim.end5cm_coverage_aware_weights = True
    optim._coverage_support_map = {
        'thresholds': [1.0, 2.0, 10.0],
        'num_levels': 4,
        'groups': {
            '0': {'free_levels': [0, 2], 'derived_levels': [1, 3]},
            '1': {'free_levels': [], 'derived_levels': [0, 1, 2, 3]},
            '2': {'free_levels': [1], 'derived_levels': [0, 2, 3]},
        },
    }
    optim.weights = {0: np.ones(12)}
    indices = optim._get_weight_optim_indices()
    assert indices.tolist() == [0, 2, 9]
    assert optim._get_weight_freeze_mask().tolist() == [
        False, True, False, True,
        True, True, True, True,
        True, False, True, True,
    ]

    captured = {}
    optim.slopes = {0: np.zeros((4, 1))}
    optim.slopes_shape = (4, 1)
    optim.weight_bounds = [(0.5, 2.0)]
    optim.method = 'Powell'
    optim.rot_ang = 0.0
    optim._get_slope_freeze_mask = lambda: np.ones((4, 1), dtype=bool)
    optim._loss_fn = lambda _rot, weights, *_args, **_kwargs: float(np.sum(weights))

    class Result:
        x = np.array([1.5, 0.75, 1.25])
        fun = 0.0

    def fake_minimize(*, x0, bounds, **kwargs):
        captured['x0'] = np.array(x0)
        captured['bounds'] = list(bounds)
        return Result()

    monkeypatch.setattr('optimiser.minimize', fake_minimize)
    optim._optim_coeff_iter(
        coeff='weights', i=0, init_loss=None,
        slopes_normalised=np.zeros(4), slope_upper_bound=1.0,
        options=None,
    )
    assert captured['x0'].tolist() == [1.0, 1.0, 1.0]
    assert captured['bounds'] == [(0.5, 2.0)] * 3
    assert optim.weights[0].tolist() == pytest.approx([
        1.5, np.sqrt(1.5 * 0.75), 0.75, 1.0,
        1.0, 1.0, 1.0, 1.0,
        1.0, 1.25, 1.0, 1.0,
    ])


def test_legacy_weight_mode_still_exposes_all_thirty_variables():
    from optimiser import Optimiser

    optim = Optimiser.__new__(Optimiser)
    optim.direct = 0
    optim.weights = {0: np.ones(30)}
    optim.freeze = None
    optim.weight_group_ids = None
    optim.end_weights = False
    optim.end5cm_coverage_aware_weights = False
    assert optim._get_weight_optim_indices().tolist() == list(range(30))


def test_coverage_parameter_bounds_count_free_hits_and_report_derived_separately():
    from calibration_batch import diagnose_parameter_bounds

    diagnostics = diagnose_parameter_bounds(
        weights=np.array([0.5, 1.5, 2.0, 0.5]),
        slopes=np.zeros((2, 1)), weight_bounds=(0.5, 2.0),
        slope_upper_bound=1.0, free_weight_indices=[0, 2], derived_weight_indices=[1, 3],
    )

    assert diagnostics['weights']['lower_bound_hits'] == 1
    assert diagnostics['weights']['upper_bound_hits'] == 1
    assert diagnostics['weights']['total'] == 2
    assert diagnostics['weights']['free_parameter_count'] == 2
    assert diagnostics['weights']['derived'] == {
        'lower_bound_hits': 1, 'upper_bound_hits': 0, 'total': 2,
        'indices': [1, 3],
    }


def _coverage_metadata(thresholds, *, free_levels=(0, 2), derived_levels=(1, 3)):
    groups = {}
    for group in range(3):
        groups[str(group)] = {
            'point_ids': [19, 20] if group == 0 else [20 + group],
            'levels': [], 'reliable_levels': list(free_levels),
            'free_levels': list(free_levels), 'derived_levels': list(derived_levels),
        }
    return {
        'enabled': True,
        'min_effective_samples': 1.0,
        'min_max_mass': 0.05,
        'policy': 'interpolate_neutral_edges',
        'free_parameter_count': 6,
        'derived_parameter_count': 6,
        'support_map': {
            'thresholds': list(thresholds), 'num_levels': len(thresholds) + 1,
            'definition': {'excluded_radius_zero_samples': 1, 'used_nonzero_radius_samples': 2},
            'groups': groups,
        },
    }


def test_coverage_metadata_is_saved_in_results_and_survives_package_roundtrip(tmp_path):
    from calibration_batch import collect_calibration_result
    from tools.sensor_parameter_package import build_sensor_package, package_parser_defaults
    from tests.test_sensor_parameter_package import _report
    from types import SimpleNamespace

    optim = SimpleNamespace(
        direct=0, weights={0: np.ones(12)}, slopes={0: np.zeros((4, 1))},
        weight_bounds=[(0.5, 2.0)], slope_upper_bound=1.0,
        avg_point_err={'calib': 0.0}, avg_end_err={'calib': 0.0},
        avg_pitch_err=0.0, avg_radius_err=0.0, k_point=1.0, k_end=0.0,
        k_pitch=1.0, k_radius=1.0, point_errors_avg={}, end_errors={},
        global_phases_set=0.0, rot_ang=0.0,
        end_weights=True, end_start=-1, end5cm_point_calib=True,
        weight_group_ids=[0, 0, 1, 2], end5cm_independent_weight_score=True,
        calibration_context={'weight_score_mode': 'group_mean'},
        source_sensor_params=None, end5cm_coverage_aware_weights=True,
        end5cm_min_weight_effective_samples=1.0,
        end5cm_min_weight_max_mass=0.05,
        end5cm_uncovered_weight_policy='interpolate_neutral_edges',
        _coverage_support_map={
            'thresholds': [1.0, 2.0, 10.0], 'num_levels': 4,
            'definition': {'excluded_radius_zero_samples': 1},
            'groups': {
                '0': {'free_levels': [0, 2], 'derived_levels': [1, 3]},
                '1': {'free_levels': [], 'derived_levels': [0, 1, 2, 3]},
                '2': {'free_levels': [1], 'derived_levels': [0, 2, 3]},
            },
        },
        _get_weight_optim_indices=lambda: np.array([0, 2, 9]),
        _ensure_coverage_support_map=lambda: optim._coverage_support_map,
    )
    result = collect_calibration_result(optim, {'stages': {}})
    metadata = result['parameters']['coverage_aware_weights']
    assert metadata['enabled'] is True
    assert metadata['free_parameter_count'] == 3
    assert metadata['support_map']['groups']['0']['free_levels'] == [0, 2]
    assert len(result['parameters']['weights'][0]) == 12

    reports = [_report(direct) for direct in (0, 120, 240)]
    for report in reports:
        entry = report['regions']['end5cm']
        entry['context'].update(
            global_point_ids=[19, 20, 21, 22], global_segment_ids=[1],
            segmentation=[4], global_sample_dist_m=[0.0, 0.01, 0.02, 0.03],
            thresholds=entry['context']['thresholds'] + [45.0],
        )
        entry['context'].update(
            calibration_objective='real_points', weight_group_ids=[0, 0, 1, 2],
            weight_score_mode='group_mean',
            end_weights=True, end_start=-1,
            coverage_aware_weights=_coverage_metadata(
                entry['context']['thresholds'],
            ),
        )
        entry['parameters'].update(
            calibration_objective='real_points', weight_group_ids=[0, 0, 1, 2],
            weight_score_mode='group_mean', end_weights=True, end_start=-1,
            coverage_aware_weights=_coverage_metadata(
                entry['context']['thresholds'],
            ),
        )
        entry['parameters']['weights'][str(report['direct'])] = [1.0] * 30
        entry['parameters']['slopes'][str(report['direct'])] = [[0.0]] * 10
    package = build_sensor_package(__import__('main').build_argument_parser(), reports)
    coverage = package['regions']['end5cm']['coverage_aware_weights']
    assert coverage['enabled'] is True
    assert coverage['directions']['0']['free_parameter_count'] == 6
    assert coverage['directions']['0']['support_map']['groups']['0']['derived_levels'] == [1, 3]
    assert all(len(values) == 30 for values in package['regions']['end5cm']['weights'].values())
    defaults = package_parser_defaults(package)
    assert defaults['end5cm_coverage_aware_weights'] is True
    assert defaults['end5cm_min_weight_effective_samples'] == 1.0
    assert defaults['end5cm_uncovered_weight_policy'] == 'interpolate_neutral_edges'


def test_old_package_without_coverage_metadata_defaults_off():
    from tools.sensor_parameter_package import build_sensor_package, package_parser_defaults
    from tests.test_sensor_parameter_package import _parser, _report

    package = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    defaults = package_parser_defaults(package)
    assert defaults['end5cm_coverage_aware_weights'] is False
