from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reconstructor import Reconstructor


def package():
    directions = [0, 120, 240]

    def region(thresholds, segmentation, support, owned, segment_ids, base):
        levels = len(thresholds) + 1
        return {
            'thresholds': thresholds,
            'sharpness': 8.0,
            'score_window': 1,
            'score_boundary_mode': 'constant',
            'local_segmentation': segmentation,
            'global_segment_ids': segment_ids,
            'support_point_ids': support,
            'owned_point_ids': owned,
            'weights': {str(d): [base + level for level in range(levels)] for d in directions},
            'slopes': {str(d): [
                [base * 10 + level + segment for segment in range(len(segmentation))]
                for level in range(levels)
            ] for d in directions},
        }

    return {
        'multi_region': {'region_order': ['full', 'end15cm', 'end5cm'],
                         'directions': directions},
        'regions': {
            'full': region([1.0], [2, 2, 2], [1, 2, 3, 4, 5, 6], [1, 2], [0, 1, 2], 1),
            'end15cm': region([2.0, 3.0], [2, 2], [3, 4, 5, 6], [3, 4], [1, 2], 10),
            'end5cm': region([3.0, 4.0, 5.0], [2], [5, 6], [5, 6], [2], 100),
        },
    }


def bare_reconstructor(config=None):
    obj = Reconstructor.__new__(Reconstructor)
    obj.total_points = 6
    obj.global_point_ids = np.arange(1, 7)
    obj.base_segments = [(0, 2), (2, 4), (4, 6)]
    obj.soft = True
    obj.discont = np.pi
    obj.turn_threshold = 2.0
    obj.sharpness = 4.8
    obj.min_consecutive = 3
    obj.multi_region_parameters = obj._normalise_multiregion_parameters(config or package())
    obj._calculate_dynamic_angles = lambda **kwargs: np.zeros((3, obj.total_points))

    calls = []
    def curvature(epsilon, alpha_dynamic):
        calls.append(np.asarray(epsilon).copy())
        return np.abs(np.asarray(epsilon)[0]), np.zeros(obj.total_points)
    obj._calculate_curvature_and_angle = curvature
    return obj, calls


def test_runtime_assembly_supports_multiple_real_point_weight_groups():
    config = package()
    block = config['regions']['end5cm']
    block['weight_group_ids'] = [0,1]
    for direct in (0,120,240):
        block['weights'][str(direct)] = [2.]*4+[3.]*4
    obj, _ = bare_reconstructor(config)
    _, _, weight, _, _ = obj._assemble_multiregion_parameters(np.ones((3,6)),0)
    np.testing.assert_allclose(weight[-2:],[2.,3.])


def test_each_region_uses_its_own_threshold_count_weights_and_slopes():
    obj, calls = bare_reconstructor()
    strain = np.vstack((np.arange(6, dtype=float), np.zeros((2, 6))))

    magnitude, angle, final_weight, slope_map, diagnostics = (
        obj._assemble_multiregion_parameters(strain, 120)
    )

    assert magnitude.shape == angle.shape == final_weight.shape == slope_map.shape == (6,)
    assert [diagnostics[name]['mass_shape'][0] for name in ('full', 'end15cm', 'end5cm')] == [2, 3, 4]
    assert np.all(final_weight[:2] < 10)
    assert np.all((final_weight[2:4] >= 10) & (final_weight[2:4] < 100))
    assert np.all(final_weight[4:] >= 100)
    np.testing.assert_allclose(calls[-1], strain * final_weight)


def test_fixed_phase_mode_pins_only_bridges_in_base_and_final_maps():
    config = package()
    config['multi_region']['use_full_transported_phase'] = True
    config['multi_region']['phase_reference_directions'] = [0]
    obj, _ = bare_reconstructor(config)
    strain = np.vstack((np.arange(6, dtype=float), np.zeros((2, 6))))
    *_, slopes, diagnostics = obj._assemble_multiregion_parameters(strain, 0)
    assert diagnostics['fixed_full_level0_bridges'] is True
    assert diagnostics['base_slope_map'][2] == slopes[2] == 11.
    assert diagnostics['base_slope_map'][4] == slopes[4] == 12.
    assert slopes[3] >= 100. and slopes[5] >= 1000.
    *_, other, diagnostics = obj._assemble_multiregion_parameters(strain, 120)
    assert diagnostics['fixed_full_level0_bridges'] is False
    assert other[2] >= 100. and other[4] >= 1000.


@pytest.mark.parametrize('end_start,tail_count', [(-1, 1), (-2, 2)])
def test_region_tail_weights_use_second_bank_only_on_selected_real_points(end_start, tail_count):
    config = package()
    block = config['regions']['end5cm']
    block.update(end_weights=True, end_start=end_start)
    for direction in (0, 120, 240):
        block['weights'][str(direction)] = [2.]*4+[5.]*4
    obj, _ = bare_reconstructor(config)
    strain = np.vstack((np.ones(6), np.zeros((2, 6))))
    _, _, weights, _, _ = obj._assemble_multiregion_parameters(strain, 0)
    np.testing.assert_allclose(weights[-tail_count:], 5.)
    if tail_count == 1:
        assert weights[-2] == pytest.approx(2.)


def test_scores_are_computed_on_support_before_owned_points_are_extracted():
    config = package()
    config['regions']['end15cm']['owned_point_ids'] = [3, 4, 5]
    config['regions']['end5cm']['owned_point_ids'] = [6]
    config['regions']['end5cm']['score_window'] = 2
    obj, _ = bare_reconstructor(config)
    strain = np.vstack(([0., 0., 0., 0., 10., 10.], np.zeros((2, 6))))

    *_, diagnostics = obj._assemble_multiregion_parameters(strain, 0)

    assert diagnostics['end5cm']['support_point_ids'] == [5, 6]
    assert diagnostics['end5cm']['owned_point_ids'] == [6]
    assert diagnostics['end5cm']['mass_shape'] == [4, 2]
    # constant-window averaging on the two-point support attenuates both edges;
    # it would be different if each owned point were scored separately.
    assert diagnostics['end5cm']['scores'][0] == pytest.approx([.5, 1.0], rel=1e-3)


def test_region_validation_rejects_gaps_overlap_and_direction_indices():
    config = package()
    config['regions']['end5cm']['owned_point_ids'] = [4, 5, 6]
    with pytest.raises(ValueError, match='owned'):
        bare_reconstructor(config)

    config = package()
    config['multi_region']['directions'] = [0, 1, 2]
    with pytest.raises(ValueError, match='0、120、240'):
        bare_reconstructor(config)


def test_global_segment_mapping_drives_region_base_and_final_slopes():
    obj, _ = bare_reconstructor()
    strain = np.vstack((np.arange(6, dtype=float), np.zeros((2, 6))))

    *_, slope_map, diagnostics = obj._assemble_multiregion_parameters(strain, 0)

    assert diagnostics['base_slope_map'][:2] == [10.0, 10.0]
    assert diagnostics['base_slope_map'][2:4] == [100.0, 100.0]
    assert diagnostics['base_slope_map'][4:] == [1000.0, 1000.0]
    assert np.all(slope_map[:2] < 100)
    assert np.all((slope_map[2:4] >= 100) & (slope_map[2:4] < 1000))
    assert np.all(slope_map[4:] >= 1000)


def test_strain_to_curvature_uses_assembler_when_multiregion_is_configured():
    obj, _ = bare_reconstructor()
    strain = np.vstack((np.arange(6, dtype=float), np.zeros((2, 6))))
    obj.processed = strain

    magnitude, angle = obj._Strain_2_Cur(
        keys=None, calib_shape='circ', calib_Data=strain.T,
        weight=None, slope=None, direct=240,
    )

    assert magnitude.shape == angle.shape == (6,)
    assert obj.last_parameter_assembly['direct'] == 240


def _groupwise_package():
    config = package()
    config['regions']['end15cm']['owned_point_ids'] = [3, 4]
    end5 = config['regions']['end5cm']
    end5['thresholds'] = [1.0, 2.0, 3.0]
    end5['sharpness'] = 1.0
    end5.update(
        local_segmentation=[1, 1, 1, 1],
        global_segment_ids=[1, 2, 3, 4],
        support_point_ids=[3, 4, 5, 6],
        owned_point_ids=[5, 6],
        weight_group_ids=[0, 0, 1, 2],
        weight_score_mode='group_mean',
    )
    levels = len(end5['thresholds']) + 1
    for direct in (0, 120, 240):
        end5['weights'][str(direct)] = [1. + level for level in range(levels)] * 3
        end5['slopes'][str(direct)] = [
            [100. + level + segment for segment in range(4)]
            for level in range(levels)
        ]
    return config


def _groupwise_run(values, mode='group_mean'):
    config = _groupwise_package()
    config['regions']['end5cm']['weight_score_mode'] = mode
    obj, _ = bare_reconstructor(config)
    strain = np.vstack((np.asarray(values, dtype=float), np.zeros((2, 6))))
    return obj._assemble_multiregion_parameters(strain, 0)[-1]


def test_groupwise_weight_scores_share_19_20_and_keep_21_22_independent():
    diagnostics = _groupwise_run([0., 0., .5, 1., 2., 3.])['end5cm']
    weight_scores = np.asarray(diagnostics['weight_scores'])
    weight_masses = np.asarray(diagnostics['weight_masses'])

    assert diagnostics['weight_score_mode'] == 'group_mean'
    assert diagnostics['group_base_magnitude'] == pytest.approx({'0': .75, '1': 2., '2': 3.})
    assert weight_scores[:, 0] == pytest.approx(weight_scores[:, 1])
    assert weight_masses[:, 0] == pytest.approx(weight_masses[:, 1])
    assert not np.allclose(weight_masses[:, 1], weight_masses[:, 2])
    assert not np.allclose(weight_masses[:, 2], weight_masses[:, 3])


def test_groupwise_weight_score_does_not_cross_contaminate_groups():
    base = _groupwise_run([0., 0., .5, 1., 2., 3.])
    changed_20 = _groupwise_run([0., 0., .5, 100., 2., 3.])
    changed_21 = _groupwise_run([0., 0., .5, 1., 100., 3.])
    base_scores = np.asarray(base['end5cm']['weight_scores'])
    changed_20_scores = np.asarray(changed_20['end5cm']['weight_scores'])
    changed_21_scores = np.asarray(changed_21['end5cm']['weight_scores'])

    np.testing.assert_allclose(base_scores[:, 2], changed_20_scores[:, 2])
    np.testing.assert_allclose(base_scores[:, 3], changed_20_scores[:, 3])
    np.testing.assert_allclose(base_scores[:, 3], changed_21_scores[:, 3])
    assert not np.allclose(base_scores[:, 0], changed_20_scores[:, 0])
    assert not np.allclose(base_scores[:, 2], changed_21_scores[:, 2])


def test_groupwise_mode_only_changes_weight_scores_not_slope_scores_or_map():
    values = [0., 0., .5, 1., 2., 3.]
    old = _groupwise_run(values, mode='spatial_window')
    new = _groupwise_run(values, mode='group_mean')

    np.testing.assert_allclose(old['end5cm']['slope_scores'], new['end5cm']['slope_scores'])
    np.testing.assert_allclose(old['end5cm']['slope_masses'], new['end5cm']['slope_masses'])
    np.testing.assert_allclose(old['slope_map'], new['slope_map'])
    assert old['end5cm']['scores'] == old['end5cm']['slope_scores']
    assert old['end5cm']['masses'] == old['end5cm']['slope_masses']


def test_groupwise_score_flag_requires_end5cm_independent_weights():
    import main

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end5cm',
        '--end5cm_groupwise_weight_score', 'True',
    ])
    with pytest.raises(ValueError, match='end5cm_independent_weights'):
        main.configure_calibration_args(args)

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'full',
        '--end5cm_groupwise_weight_score', 'True',
        '--end5cm_independent_weights', 'True',
    ])
    with pytest.raises(ValueError, match='optimization_region=end5cm'):
        main.configure_calibration_args(args)

    args = main.parse_main_args([
        '--task', 'optim', '--optimization_region', 'end5cm',
        '--end5cm_groupwise_weight_score', 'True',
        '--end5cm_independent_weights', 'True',
    ])
    context = main.configure_calibration_args(args)
    assert context['weight_score_mode'] == 'group_mean'
