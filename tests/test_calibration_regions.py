"""Physical cropping and global segment compatibility for nested calibration."""

import importlib.util
from pathlib import Path
import sys
import warnings

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PRESET = [510, 521, 532, 543, 554, 588, 622, 656, 707, 758, 809,
          860, 911, 962, 1013, 1064, 1115, 1166, 1217, 1268, 1319, 1370]
FULL_SEGMENTS = [2, 3, 5, 2, 3, 3, 2, 2]


@pytest.mark.parametrize('enabled,start', [(True, -5), (True, 0), (True, 1), (True, -1.5), ('False', -1)])
def test_end_weight_region_validation_rejects_invalid_flags_and_indices(enabled, start):
    from calibration_regions import validate_end_weight_config
    with pytest.raises(ValueError):
        validate_end_weight_config(enabled, start, 4)


def resolve(**overrides):
    assert importlib.util.find_spec('calibration_regions'), 'missing region resolver'
    from calibration_regions import resolve_calibration_region
    profiles = {
        'full': dict(length_m=None, folder_path='body', radii={'circ': [0, 200]},
                     thresholds=[0.8, 4], segmentation=FULL_SEGMENTS),
        'end15cm': dict(length_m=.15, folder_path='15cm', radii={'circ': [0, 30]},
                        thresholds=[0.8, 4, 16.7], segmentation=[3, 2, 2]),
        'end5cm': dict(length_m=.05, folder_path='5cm', radii={'circ': [0, 15]},
                       thresholds=[0.8, 4, 58.3], segmentation=[2, 2]),
    }
    kwargs = dict(start_value=7, end_value=10, samp_dist_preset=PRESET,
                  full_segmentation=FULL_SEGMENTS, profiles=profiles,
                  optimization_region='full', multi_region_calib=False)
    kwargs.update(overrides)
    return resolve_calibration_region(**kwargs)


@pytest.mark.parametrize('region,ids,segments,trim,local,tip', [
    ('full', list(range(1, 23)), FULL_SEGMENTS, 0.0, [7, 867], .877),
    ('end15cm', list(range(16, 23)), [3, 2, 2], -.15, [28, 140], .15),
    ('end5cm', list(range(19, 23)), [2, 2], -.05, [7, 40], .05),
])
def test_selected_region_matches_physical_geometry(region, ids, segments, trim, local, tip):
    result = resolve(optimization_region=region, multi_region_calib=True)
    assert result['ideal_len'] == pytest.approx(.877)
    assert result['global_point_ids'] == ids
    assert result['segmentation'] == segments
    assert result['straight_trim'] == trim
    assert np.asarray(result['sample_dist_m'])[[0, -1]] == pytest.approx(np.array(local)/1000)
    assert result['reconstruction_length_m'] == pytest.approx(tip)


@pytest.mark.parametrize('region, ids', [
    ('full', list(range(1, 23))),
    ('end15cm', list(range(16, 23))),
    ('end5cm', list(range(19, 23))),
])
def test_disabled_region_mode_allows_one_selected_reconstruction_region(region, ids):
    assert resolve(optimization_region=region, multi_region_calib=False)['global_point_ids'] == ids


@pytest.mark.parametrize('region', ['full', 'end15cm', 'end5cm'])
def test_parse_main_args_configures_selected_local_reconstruction(region):
    import main
    args = main.parse_main_args([
        '--task', 'recon', '--multi_region_calib', 'False',
        '--optimization_region', region,
    ])
    context = main.configure_calibration_args(args)
    assert context['optimization_region'] == region


def test_crop_inside_global_segment_is_rejected_instead_of_truncated():
    # Old [2,2,3] tail splits the four-point 5 cm region through a segment.
    with pytest.raises(ValueError, match='分段'):
        resolve(full_segmentation=[2, 3, 5, 2, 3, 2, 2, 3],
                optimization_region='end5cm', multi_region_calib=True)


def test_local_segmentation_must_match_global_partition_not_just_point_count():
    # All four points are a full global segment, but profile requests two segments.
    with pytest.raises(ValueError, match='分段'):
        resolve(full_segmentation=[2, 3, 5, 2, 3, 3, 4],
                optimization_region='end5cm', multi_region_calib=True)


@pytest.mark.parametrize('segments', [[2, 3], [22, 1], [18, 0, 4], [18, 2.5, 1.5]])
def test_invalid_full_partition_is_not_silently_repaired(segments):
    with pytest.raises(ValueError, match='分段'):
        resolve(full_segmentation=segments)


@pytest.mark.parametrize('overrides', [
    dict(start_value=float('nan')), dict(end_value=-1), dict(end_value=float('nan')),
    dict(samp_dist_preset=[510, 510, 520]),
    dict(samp_dist_preset=[510, 500]),
])
def test_invalid_geometry_fails_before_data_read(overrides):
    with pytest.raises(ValueError):
        resolve(**overrides)


def test_negative_start_is_allowed_and_points_before_zero_are_removed_from_full_region():
    profiles = {
        'full': dict(length_m=None, folder_path='body', radii={'circ': [0, 200]},
                     thresholds=[1], segmentation=[2, 2]),
    }
    with pytest.warns(RuntimeWarning, match='首段仅剩 1 个点.*重新分段'):
        result = resolve(
            start_value=-5, end_value=5,
            samp_dist_preset=[100, 110, 120, 130],
            full_segmentation=[2, 2], profiles=profiles,
        )
    assert result['ideal_len'] == pytest.approx(.030)
    assert result['global_point_ids'] == [2, 3, 4]
    assert result['segmentation'] == [1, 2]
    assert result['global_sample_dist_m'] == pytest.approx([.005, .015, .025])
    assert result['sample_dist_m'] == pytest.approx([.005, .015, .025])


def test_negative_start_does_not_warn_when_trimmed_first_segment_still_has_two_points():
    profiles = {
        'full': dict(length_m=None, folder_path='body', radii={'circ': [0, 200]},
                     thresholds=[1], segmentation=[3, 2]),
    }
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        result = resolve(
            start_value=-5, end_value=5,
            samp_dist_preset=[100, 110, 120, 130, 140],
            full_segmentation=[3, 2], profiles=profiles,
        )
    assert result['segmentation'] == [2, 2]


def test_exact_crop_boundary_keeps_real_point_and_full_segment():
    profiles = {
        'full': dict(length_m=None, folder_path='body', radii={'circ': [0, 200]},
                     thresholds=[1], segmentation=[2, 2]),
        'tail': dict(length_m=.020, folder_path='tail', radii={'circ': [0, 15]},
                     thresholds=[1], segmentation=[2]),
    }
    result = resolve(samp_dist_preset=[100, 110, 120, 130],
                     full_segmentation=[2, 2], profiles=profiles,
                     optimization_region='tail', multi_region_calib=True)
    assert result['global_point_ids'] == [3, 4]
    assert result['sample_dist_m'] == pytest.approx([0, .01])
    assert result['global_segment_ids'] == [1]


def test_selected_dataset_and_levels_travel_together():
    result = resolve(optimization_region='end5cm', multi_region_calib=True)
    assert result['folder_path'] == '5cm'
    assert result['radii'] == {'circ': [0, 15]}
    assert result['thresholds'] == [.8, 4, 58.3]
    assert result['global_segment_ids'] == [6, 7]


def test_parameter_shape_rejects_old_local_slopes_for_full_calibration():
    from calibration_regions import validate_calibration_parameters
    with pytest.raises(ValueError, match='slopes'):
        validate_calibration_parameters(None, {0: np.ones((6, 2))},
                                        [.8, 1.2, 2, 3, 4], FULL_SEGMENTS, [0])


@pytest.mark.parametrize('region,enabled,count,segments,last_radius', [
    ('full', False, 21, [2, 4, 8, 3, 2, 2], 200),
    ('end15cm', True, 7, [3, 2, 2], 30),
    ('end5cm', True, 4, [2, 2], 15),
])
def test_main_region_selection_reaches_optimizer(monkeypatch, region, enabled, count, segments, last_radius):
    import main

    class ConfigReached(Exception):
        pass

    # Stop before the real optimizer reads CSV files or builds any GUI.
    received = {}
    def capture(**kwargs):
        received.update(kwargs)
        raise ConfigReached
    monkeypatch.setattr(main, 'Optimiser', capture)
    monkeypatch.setattr(sys, 'argv', ['main.py', '--task', 'init',
                                    '--multi_region_calib', str(enabled),
                                    '--optimization_region', region])
    with pytest.raises(ConfigReached):
        main.main()
    assert received['ideal_len'] == pytest.approx(.895)
    assert received['segmentation'] == segments
    assert sum(received['segmentation']) == count
    assert received['radii']['circ'][-1] == last_radius
    assert Path(received['folder_path']).is_dir()
    assert received['weights'] is None and received['slopes'] is None
    assert 'multi_region_calib' not in received


def test_main_geometry_overrides_recompute_length_before_optimizer(monkeypatch):
    import main
    class ConfigReached(Exception):
        pass
    def capture(**kwargs):
        assert kwargs['ideal_len'] == pytest.approx(.930)
        assert kwargs['straight_trim'] == 0.0
        raise ConfigReached
    monkeypatch.setattr(main, 'Optimiser', capture)
    monkeypatch.setattr(sys, 'argv', ['main.py', '--task', 'init',
                                    '--start_value', '10', '--end_value', '20'])
    with pytest.raises(ConfigReached):
        main.main()


def test_main_rejects_cross_boundary_segments_before_optimizer(monkeypatch):
    import main
    def forbidden(**kwargs):
        pytest.fail('invalid spatial partition reached optimizer')
    monkeypatch.setattr(main, 'Optimiser', forbidden)
    monkeypatch.setattr(sys, 'argv', ['main.py', '--task', 'optim',
                                    '--multi_region_calib', 'True',
                                    '--optimization_region', 'end5cm',
                                    '--full_segmentation', '[2,3,5,2,3,2,2,3]'])
    with pytest.warns(RuntimeWarning, match='重新分段'):
        with pytest.raises(ValueError, match='分段'):
            main.main()


@pytest.mark.parametrize('trim,ids,samples,tip', [
    (0.0, list(range(1, 23)), [7, 867], .877),
    (-.15, list(range(16, 23)), [28, 140], .15),
    (-.05, list(range(19, 23)), [7, 40], .05),
])
def test_sensor_geometry_matches_resolver_even_with_stale_ideal_length(trim, ids, samples, tip):
    from sensor import Sensor
    sensor = Sensor.__new__(Sensor)  # geometry only; no CSV or hardware construction
    sensor.interrogator = 'FiberTecc'
    sensor.ideal_len = .878
    sensor.generate_samp_dist(False, 7, 10, trim, PRESET, None, False)
    assert sensor.ideal_len == pytest.approx(.877)
    assert sensor.global_point_ids.tolist() == ids
    assert sensor.samp_dist[[0, -1]] == pytest.approx(np.array(samples)/1000)
    assert sensor.ad_samp_dist[-1] == pytest.approx(tip)


def test_sensor_exact_boundary_and_reverse_preserve_global_ids():
    from sensor import Sensor
    sensor = Sensor.__new__(Sensor)
    sensor.interrogator = 'FiberTecc'
    sensor.ideal_len = 100
    sensor.generate_samp_dist(True, 7, 10, -.02, [100, 110, 120, 130], None, False)
    assert sensor.global_point_ids.tolist() == [4, 3]
    assert sensor.samp_dist == pytest.approx([.01, .02])


def test_sensor_negative_start_crops_pre_zero_point_before_zero_init():
    from sensor import Sensor
    sensor = Sensor.__new__(Sensor)
    sensor.interrogator = 'FiberTecc'
    sensor.ideal_len = 100
    sensor.generate_samp_dist(False, -5, 5, 0.0, [100, 110, 120, 130], None, False)
    assert sensor.raw_trim_idx == 1
    assert sensor.global_point_ids.tolist() == [2, 3, 4]
    assert sensor.samp_dist == pytest.approx([.005, .015, .025])
    assert sensor.zero_init is True
    assert sensor.ad_samp_dist == pytest.approx([0, .005, .015, .025, .030])


def test_live_packet_indices_are_shifted_by_the_same_pre_zero_crop():
    import struct
    from sensor import Sensor, WavelengthContinuityGuard
    sensor = Sensor.__new__(Sensor)
    sensor.buffer = bytearray(struct.pack('<I', 1) + b'x')
    sensor._parse_packet = lambda body: [(101, 1.0), (102, 2.0), (104, 4.0)]
    sensor.active_channels = {1: 0}
    sensor.raw_trim_idx = 1
    sensor.total_points = 3
    sensor.current_snapshot = np.zeros((3, 1))
    sensor.zero_points = {1: [None] * 3}
    sensor.is_zero_set = {1: False}
    sensor.wavelength_jump_guard_enabled = True
    sensor._wavelength_guard = WavelengthContinuityGuard()

    sensor._process_buffer()

    assert sensor.current_snapshot[:, 0] == pytest.approx([2.0, 0.0, 4.0])
    assert sensor.zero_points[1] == [2.0, None, 4.0]


def test_main_preloaded_lists_support_reconstructor_two_axis_indexing(monkeypatch):
    import main
    level_count = len(main.build_argument_parser().get_default('calibration_regions')['end5cm']['thresholds']) + 1
    class ConfigReached(Exception):
        pass
    def capture(**kwargs):
        # _Strain_2_Cur indexes slope[level, segment], which plain nested lists reject.
        assert kwargs['slopes'][0][level_count - 1, 1] == 1.0
        assert kwargs['weights'][0].shape == (2 * level_count,)
        raise ConfigReached
    slopes = {d: [[1.0, 1.0] for _ in range(level_count)] for d in [0, 120, 240]}
    weights = {d: [1.0] * (2 * level_count) for d in [0, 120, 240]}
    monkeypatch.setattr(main, 'Optimiser', capture)
    monkeypatch.setattr(sys, 'argv', ['main.py', '--task', 'recon',
                                    '--multi_region_calib', 'False', '--optimization_region', 'end5cm',
                                    '--weights', repr(weights), '--slopes', repr(slopes)])
    with pytest.raises(ConfigReached):
        main.main()


def test_merged_recon_requires_package_and_passes_full_geometry_to_optimizer(monkeypatch):
    import main
    package_path = ROOT / 'params' / '06B6_NeTi_v2_centraltube_multi_region.json'

    class ConfigReached(Exception):
        pass

    def capture(**kwargs):
        assert kwargs['ideal_len'] == pytest.approx(.877)
        assert kwargs['segmentation'] == FULL_SEGMENTS
        assert kwargs['multi_region_parameters']['multi_region']['directions'] == [0, 120, 240]
        raise ConfigReached

    monkeypatch.setattr(main, 'Optimiser', capture)
    monkeypatch.setattr(sys, 'argv', [
        'main.py', '--task', 'recon', '--multi_region_calib', 'True',
        '--sensor_params', str(package_path), '--optimization_region', 'end5cm',
    ])
    with pytest.raises(ConfigReached):
        main.main()

    args = main.parse_main_args(['--task', 'recon', '--multi_region_calib', 'True'])
    with pytest.raises(ValueError, match='sensor_params'):
        main.configure_calibration_args(args)


def test_merged_demo_passes_full_geometry_and_region_package_to_optimizer(monkeypatch):
    import main
    package_path = ROOT / 'params' / '06B6_NeTi_v2_centraltube_multi_region.json'

    class ConfigReached(Exception):
        pass

    def capture(**kwargs):
        assert kwargs['ideal_len'] == pytest.approx(.877)
        assert kwargs['segmentation'] == FULL_SEGMENTS
        assert kwargs['multi_region_parameters']['multi_region']['directions'] == [0, 120, 240]
        raise ConfigReached

    monkeypatch.setattr(main, 'Optimiser', capture)
    monkeypatch.setattr(sys, 'argv', [
        'main.py', '--task', 'demo', '--multi_region_calib', 'True',
        '--sensor_params', str(package_path),
    ])
    with pytest.raises(ConfigReached):
        main.main()


def test_multiregion_demo_warns_but_runs_with_non_deployable_package(monkeypatch, capsys):
    import main
    package_path = ROOT / 'params' / '06B6_NeTi_v2_ftube_multi_region.json'

    class ConfigReached(Exception):
        pass

    def capture(**kwargs):
        assert kwargs['multi_region_parameters']['multi_region']['deployment_ready'] is False
        raise ConfigReached

    monkeypatch.setattr(main, 'Optimiser', capture)
    monkeypatch.setattr(sys, 'argv', [
        'main.py', '--task', 'demo', '--multi_region_calib', 'True',
        '--sensor_params', str(package_path),
    ])

    with pytest.raises(ConfigReached):
        main.main()

    output = capsys.readouterr().out
    assert 'WARNING' in output
    assert 'deployment_ready=False' in output
    assert 'direction_reference_direct=120' in output
    assert '120/end15cm transported phase is unverified' in output
