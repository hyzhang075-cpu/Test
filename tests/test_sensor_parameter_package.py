import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.sensor_parameter_package import (
    apply_validation_results,
    build_sensor_package,
    load_calibration_results,
    load_sensor_package,
    package_parameter_destinations,
    package_deployment_ready,
    package_parser_defaults,
    render_calibration_comparison,
    write_sensor_package,
)


REGIONS = {
    'full': dict(thresholds=[.8, 1.2, 2, 3, 4], segmentation=[2, 2],
                 point_ids=[1, 2, 3, 4], segment_ids=[0, 1], length=None),
    'end15cm': dict(thresholds=[.8, 1.2, 2, 3, 4, 8, 20], segmentation=[2],
                    point_ids=[3, 4], segment_ids=[1], length=.15),
    'end5cm': dict(thresholds=[.8, 1.2, 2, 3, 4, 8, 20, 35], segmentation=[2],
                   point_ids=[3, 4], segment_ids=[1], length=.05),
}


def _parser():
    import main
    return main.build_argument_parser()


def test_real_point_objective_package_roundtrip_and_legacy_default(tmp_path):
    reports = [_report(d) for d in (0, 120, 240)]
    for report in reports:
        report['regions']['end5cm']['context']['calibration_objective'] = 'real_points'
    package = build_sensor_package(_parser(), reports)
    assert package['regions']['end5cm']['calibration_objective'] == 'real_points'
    assert package_parser_defaults(package)['end5cm_point_calib'] is True
    assert package_parser_defaults(package)['calibration_regions']['full']['calibration_objective'] == 'geometry'
    path = tmp_path / 'point-mode.json'
    write_sensor_package(package, path)
    import main
    assert main.parse_main_args(['--task','optim','--sensor_params',str(path)]).end5cm_point_calib is True
    assert main.parse_main_args(['--task','optim','--sensor_params',str(path),
                                 '--end5cm_point_calib','False']).end5cm_point_calib is False
    legacy = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    assert package_parser_defaults(legacy)['end5cm_point_calib'] is False
    reports[1]['regions']['end5cm']['context']['calibration_objective'] = 'geometry'
    with pytest.raises(ValueError, match='context'):
        build_sensor_package(_parser(), reports)


def test_weight_groups_export_import_and_direction_consistency():
    reports = [_report(d) for d in (0,120,240)]
    # Fixture end5cm has two real points: generic metadata validation supports two groups.
    for report in reports:
        entry = report['regions']['end5cm']
        entry['context']['weight_group_ids'] = [0,1]
        entry['parameters']['weights'][str(report['direct'])] *= 2
    package = build_sensor_package(_parser(), reports)
    assert package['regions']['end5cm']['weight_group_ids'] == [0,1]
    assert package_parser_defaults(package)['calibration_regions']['end5cm']['weight_group_ids'] == [0,1]
    legacy = build_sensor_package(_parser(), [_report(d) for d in (0,120,240)])
    assert package_parser_defaults(legacy)['end5cm_independent_weights'] is False
    reports[1]['regions']['end5cm']['context']['weight_group_ids'] = [1,0]
    with pytest.raises(ValueError, match='context'):
        build_sensor_package(_parser(), reports)


def test_groupwise_weight_score_mode_round_trips_and_legacy_defaults_to_spatial_window(tmp_path):
    reports = [_report(d) for d in (0, 120, 240)]
    for report in reports:
        entry = report['regions']['end5cm']
        levels = len(REGIONS['end5cm']['thresholds']) + 1
        entry['context']['weight_group_ids'] = [0, 1]
        entry['context']['weight_score_mode'] = 'group_mean'
        entry['parameters']['weights'][str(report['direct'])] = [
            float(report['direct'] + level + 1)
            for _group in range(2) for level in range(levels)
        ]

    package = build_sensor_package(_parser(), reports)
    assert package['regions']['end5cm']['weight_score_mode'] == 'group_mean'
    defaults = package_parser_defaults(package)
    assert defaults['end5cm_groupwise_weight_score'] is True
    assert defaults['calibration_regions']['end5cm']['weight_score_mode'] == 'group_mean'
    path = tmp_path / 'groupwise.json'
    write_sensor_package(package, path)
    assert load_sensor_package(path)['regions']['end5cm']['weight_score_mode'] == 'group_mean'

    legacy = deepcopy(package)
    legacy['regions']['end5cm'].pop('weight_score_mode')
    assert package_parser_defaults(legacy)['end5cm_groupwise_weight_score'] is False
    assert package_parser_defaults(legacy)['calibration_regions']['end5cm']['weight_score_mode'] == 'spatial_window'


def test_comparison_records_weight_score_mode():
    reports = [_report(d) for d in (0, 120, 240)]
    for report in reports:
        report['regions']['end5cm']['context']['weight_score_mode'] = 'group_mean'
    comparison = render_calibration_comparison(reports)
    assert 'weight score mode' in comparison
    assert 'group_mean' in comparison


def test_partial_end5_results_merge_keeps_upstream_and_source_history():
    from tools.sensor_parameter_package import merge_end5_results
    base = [_report(d) for d in (0,120,240)]
    partial = deepcopy(base)
    for old, new in zip(base, partial):
        old['_source_path'] = f'./old-{old["direct"]}/results.json'
        new['_source_path'] = f'./new-{new["direct"]}/results.json'
        new['regions'] = {'end5cm': new['regions']['end5cm']}
        new['regions']['end5cm']['parameters']['global_phases_set'] = .9
    merged = merge_end5_results(base, partial)
    assert merged[0]['regions']['full'] == base[0]['regions']['full']
    assert merged[0]['regions']['end15cm'] == base[0]['regions']['end15cm']
    assert merged[0]['regions']['end5cm']['parameters']['global_phases_set'] == .9
    assert base[0]['regions']['end5cm']['parameters']['global_phases_set'] != .9
    package = build_sensor_package(_parser(), merged)
    assert './old-0/results.json' in package['provenance']['source_results']
    assert './new-0/results.json' in package['provenance']['source_results']
    partial[0]['sensor_id'] = 'another-sensor'
    with pytest.raises(ValueError, match='sensor'):
        merge_end5_results(base, partial)


def test_package_base_can_replace_end5_then_end15_without_losing_other_regions():
    from tools.sensor_parameter_package import merge_region_into_package

    base = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    end5 = [_report(d) for d in (0, 120, 240)]
    end15 = [_report(d) for d in (0, 120, 240)]
    for report in end5:
        report['regions'] = {'end5cm': report['regions']['end5cm']}
        report['regions']['end5cm']['context']['calibration_objective'] = 'real_points'
        report['regions']['end5cm']['parameters']['weights'][str(report['direct'])][0] = 9.0
        report['_source_path'] = f'./end5-{report["direct"]}/results.json'
    for report in end15:
        report['regions'] = {'end15cm': report['regions']['end15cm']}
        report['regions']['end15cm']['context']['calibration_objective'] = 'real_points'
        report['regions']['end15cm']['parameters']['weights'][str(report['direct'])][0] = 8.0
        report['_source_path'] = f'./end15-{report["direct"]}/results.json'

    first = merge_region_into_package(base, end5, base_source='params/base.json')
    merged = merge_region_into_package(first, end15, base_source='params/end5.json')

    assert merged['regions']['full'] == base['regions']['full']
    assert merged['regions']['end5cm'] == first['regions']['end5cm']
    assert merged['regions']['end5cm']['weights']['0'][0] == 9.0
    assert merged['regions']['end15cm']['weights']['0'][0] == 8.0
    assert merged['regions']['end15cm']['calibration_objective'] == 'real_points'
    assert merged['shared_parameters']['runtime_control_parameters']['end15cm_point_calib'] is True
    assert merged['shared_parameters']['runtime_control_parameters']['end5cm_point_calib'] is True
    assert base['regions']['end15cm']['calibration_objective'] == 'geometry'
    assert len(merged['provenance']['source_results']) == 9
    assert merged['multi_region']['deployment_ready'] is False


def test_package_base_rejects_mixed_or_mismatched_partial_results():
    from tools.sensor_parameter_package import merge_region_into_package

    base = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    partial = [_report(d) for d in (0, 120, 240)]
    for report in partial:
        report['regions'] = {'end15cm': report['regions']['end15cm']}
    partial[1]['regions'] = {'end5cm': _entry('end5cm', 120)}
    with pytest.raises(ValueError, match='同一区域'):
        merge_region_into_package(base, partial)

    partial[1]['regions'] = {'end15cm': _entry('end15cm', 120)}
    partial[1]['regions']['end15cm']['context']['global_point_ids'] = [1, 2]
    with pytest.raises(ValueError, match='context|点位'):
        merge_region_into_package(base, partial)


def test_package_base_rejects_changed_scoring_configuration():
    from tools.sensor_parameter_package import merge_region_into_package

    base = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    partial = [_report(d) for d in (0, 120, 240)]
    for report in partial:
        report['regions'] = {'end15cm': report['regions']['end15cm']}
        report['regions']['end15cm']['context']['sharpness'] = 999
    with pytest.raises(ValueError, match='context|评分'):
        merge_region_into_package(base, partial)


@pytest.mark.parametrize('field,wrong', [
    ('crop_origin_m', .123),
    ('sample_dist_m', [.1, .2]),
    ('reconstruction_length_m', .99),
    ('ideal_len', .99),
    ('straight_trim', -.99),
    ('optimization_region', 'end5cm'),
])
def test_package_base_rejects_shared_geometry_mismatch(field, wrong):
    from tools.sensor_parameter_package import merge_region_into_package

    base = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    partial = [_report(d) for d in (0, 120, 240)]
    for report in partial:
        report['regions'] = {'end15cm': report['regions']['end15cm']}
        report['regions']['end15cm']['context'][field] = wrong
    with pytest.raises(ValueError, match='context|几何'):
        merge_region_into_package(base, partial)


def test_new_package_requires_complete_calibration_geometry():
    reports = [_report(d) for d in (0, 120, 240)]
    for report in reports:
        report['regions']['end15cm']['context'].pop('crop_origin_m')
    with pytest.raises(ValueError, match='context'):
        build_sensor_package(_parser(), reports)


def test_export_cli_accepts_one_package_as_base_results(tmp_path):
    from tools.sensor_parameter_package import main as export_main

    base = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    base_path = tmp_path / 'base.json'
    write_sensor_package(base, base_path)
    paths = []
    for direct in (0, 120, 240):
        report = _report(direct)
        report['regions'] = {'end15cm': report['regions']['end15cm']}
        report['regions']['end15cm']['context']['calibration_objective'] = 'real_points'
        path = tmp_path / f'end15-{direct}.json'
        path.write_text(json.dumps(report), encoding='utf-8')
        paths.append(str(path))
    output = tmp_path / 'combined.json'

    export_main(['--base_results', str(base_path), '--results', *paths,
                 '--output', str(output)])

    merged = load_sensor_package(output)
    assert merged['regions']['end15cm']['calibration_objective'] == 'real_points'
    assert merged['regions']['end5cm'] == base['regions']['end5cm']


def test_export_cli_does_not_overwrite_base_package(tmp_path):
    from tools.sensor_parameter_package import main as export_main

    base = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    base_path = tmp_path / 'base.json'
    write_sensor_package(base, base_path)
    before = base_path.read_bytes()
    paths = []
    for direct in (0, 120, 240):
        report = _report(direct)
        report['regions'] = {'end15cm': report['regions']['end15cm']}
        path = tmp_path / f'end15-{direct}.json'
        path.write_text(json.dumps(report), encoding='utf-8')
        paths.append(str(path))

    with pytest.raises(ValueError, match='覆盖'):
        export_main(['--base_results', str(base_path), '--results', *paths,
                     '--output', str(base_path)])
    assert base_path.read_bytes() == before


def test_export_preserves_fixed_phase_references_and_direction_scope():
    reports = [_report(d) for d in (0, 120, 240)]
    for region in ('end15cm', 'end5cm'):
        reports[0]['regions'][region]['parameters']['phase_reference'] = {
            'mode': 'full_level0_fixed_bridge', 'phase_at_first_point_rad': .4,
        }
    result = build_sensor_package(_parser(), reports)
    assert result['multi_region']['use_full_transported_phase'] is True
    assert result['multi_region']['phase_reference_directions'] == [0]
    assert package_parser_defaults(result)['use_full_transported_phase'] is True
    assert result['regions']['end5cm']['phase_reference']['0']['phase_at_first_point_rad'] == .4
    reports[0]['regions']['end5cm']['parameters']['phase_reference'] = None
    with pytest.raises(ValueError):
        build_sensor_package(_parser(), reports)


def test_end_weight_package_roundtrip_keeps_region_scope_and_old_packages_disabled(tmp_path):
    reports = [_report(d) for d in (0, 120, 240)]
    for report in reports:
        entry = report['regions']['end5cm']
        entry['context'].update(end_weights=True, end_start=-1)
        key = str(report['direct'])
        entry['parameters']['weights'][key] *= 2
    package = build_sensor_package(_parser(), reports)
    profiles = package_parser_defaults(package)['calibration_regions']
    assert profiles['end5cm']['end_weights'] is True
    assert profiles['end5cm']['end_start'] == -1
    assert profiles['full']['end_weights'] is False
    assert profiles['end15cm']['end_weights'] is False
    path = tmp_path / 'sensor.json'
    write_sensor_package(package, path)
    import main
    args = main.parse_main_args(['--task', 'recon', '--sensor_params', str(path),
                                 '--optimization_region', 'end5cm',
                                 '--full_segmentation', '[2,2]',
                                 '--samp_dist_preset', '[0,11,45,100]'])
    main.configure_calibration_args(args)
    assert args.end_weights is True and args.end_start == -1
    assert args.weights[0].shape == (2 * (len(profiles['end5cm']['thresholds'])+1),)
    legacy = build_sensor_package(_parser(), [_report(d) for d in (0, 120, 240)])
    assert package_parser_defaults(legacy)['calibration_regions']['end5cm']['end_weights'] is False
    reports[1]['regions']['end5cm']['context']['end_start'] = -2
    with pytest.raises(ValueError, match='context'):
        build_sensor_package(_parser(), reports)


def _entry(region, direct, *, stage_status='converge'):
    cfg = REGIONS[region]
    levels = len(cfg['thresholds']) + 1
    segments = len(cfg['segmentation'])
    phase = {'full': -.7, 'end15cm': -.2, 'end5cm': .7}[region]
    return {
        'status': 'complete',
        'context': {
            'optimization_region': region,
            'length_m': cfg['length'],
            'folder_path': region,
            'radii': {'circ': [0, 200]},
            'thresholds': cfg['thresholds'],
            'segmentation': cfg['segmentation'],
            'global_point_ids': cfg['point_ids'],
            'global_segment_ids': cfg['segment_ids'],
            'global_sample_dist_m': [index / 100 for index in cfg['point_ids']],
            'sample_dist_m': [index / 100 for index in range(len(cfg['point_ids']))],
            'crop_origin_m': 0.0,
            'reconstruction_length_m': .4 if region == 'full' else cfg['length'],
            'ideal_len': .4,
            'straight_trim': 0 if region == 'full' else -cfg['length'],
        },
        'parameters': {
            'weights': {str(direct): [float(direct + level + 1) for level in range(levels)]},
            'slopes': {str(direct): [
                [float(direct + level + segment) for segment in range(segments)]
                for level in range(levels)
            ]},
            'global_phases_set': phase,
            'rot_ang': 0.0,
        },
        'errors': {
            'normal_weighted_loss': .01,
            'avg_point_err': {'calib': .005},
            'avg_end_err': {'calib': .01},
            'avg_pitch_err': 0.0,
            'avg_radius_err': 0.0,
            'point_errors_by_sample': {'circ': {'200': .005}},
            'end_errors_by_sample': {'circ': {'200': .01}},
        },
        'optimization': {'stages': {
            'slopes': {'status': stage_status, 'start_loss': .02, 'final_loss': .01},
            'weights': {'status': stage_status, 'start_loss': .02, 'final_loss': .01},
        }},
    }


def _report(direct, *, sensor_id='sensor-A', stage_status='converge'):
    return {
        'sensor_id': sensor_id,
        'task': 'optim',
        'direct': direct,
        'regions': {
            region: _entry(region, direct, stage_status=stage_status)
            for region in REGIONS
        },
    }


def test_package_merges_literal_direction_angles_in_stable_order():
    package = build_sensor_package(
        _parser(), [_report(240), _report(0), _report(120)],
        source_commit='abc123', generated_at='2026-09-14T00:00:00Z',
    )

    assert list(package) == [
        'sensor_id', 'format_version', 'shared_parameters',
        'multi_region', 'regions', 'provenance',
    ]
    assert package['multi_region']['directions'] == [0, 120, 240]
    assert list(package['regions']) == ['full', 'end15cm', 'end5cm']
    assert list(package['regions']['end5cm']['weights']) == ['0', '120', '240']
    assert len(package['regions']['full']['weights']['0']) == 6
    assert len(package['regions']['end15cm']['weights']['0']) == 8
    assert len(package['regions']['end5cm']['weights']['0']) == 9
    assert package['provenance']['source_commit'] == 'abc123'
    assert package['provenance']['generated_at'] == '2026-09-14T00:00:00Z'


def test_parser_and_exported_package_use_project_relative_paths():
    parser = _parser()
    assert parser.get_default('zero_reference_path') == (
        './params/06B6_NeTi_v2_ftube_zero_reference.json'
    )

    reports = [_report(direct) for direct in (0, 120, 240)]
    for report in reports:
        report['_source_path'] = str(
            ROOT / 'calibration_results' / f'run-direct{report["direct"]}' / 'results.json'
        )
        for region in REGIONS:
            report['regions'][region]['context']['folder_path'] = str(
                ROOT / '0908-06B6' / region
            )

    package = build_sensor_package(parser, reports)

    # Region folders are relative to calibration_data_root, avoiding a duplicated
    # ``0908-06B6/0908-06B6`` prefix when main resolves them at runtime.
    assert package['regions']['full']['folder_path'] == 'full'
    assert package['provenance']['source_results'][0] == (
        './calibration_results/run-direct0/results.json'
    )
    assert not any(':' in path for path in package['provenance']['source_results'])


def test_export_converts_project_external_data_root_to_relative_path():
    parser = _parser()
    external_root = ROOT.parent / 'portable-calibration-data'
    parser.set_defaults(calibration_data_root=str(external_root))

    package = build_sensor_package(
        parser, [_report(0), _report(120), _report(240)]
    )

    runtime = package['shared_parameters']['runtime_control_parameters']
    assert runtime['calibration_data_root'] == '../portable-calibration-data'
    assert not Path(runtime['calibration_data_root']).is_absolute()


def test_export_converts_folder_override_relative_to_calibration_data_root():
    parser = _parser()
    data_root = ROOT / 'portable-calibration-data'
    parser.set_defaults(
        calibration_data_root=str(data_root),
        folder_path=str(data_root / 'full'),
    )

    package = build_sensor_package(
        parser, [_report(0), _report(120), _report(240)]
    )

    runtime = package['shared_parameters']['runtime_control_parameters']
    assert runtime['folder_path'] == 'full'


def test_export_rejects_region_folder_outside_calibration_data_root():
    parser = _parser()
    data_root = ROOT / 'portable-calibration-data'
    parser.set_defaults(calibration_data_root=str(data_root))
    reports = [_report(0), _report(120), _report(240)]
    for report in reports:
        report['regions']['full']['context']['folder_path'] = str(ROOT / 'elsewhere')

    with pytest.raises(ValueError, match='calibration_data_root'):
        build_sensor_package(parser, reports)


def test_every_parser_destination_has_one_authoritative_package_location():
    parser = _parser()
    expected = [action.dest for action in parser._actions if action.dest != 'help']
    package = build_sensor_package(parser, [_report(0), _report(120), _report(240)])

    actual = package_parameter_destinations(package)

    assert sorted(actual) == sorted(expected)
    assert len(actual) == len(set(actual))
    assert list(package['shared_parameters']) == [
        'hardware_parameters', 'calibration_experiment_parameters',
        'optimization_hyperparameters', 'dynamic_display_parameters',
        'reconstruction_parameters', 'initialization_parameters',
        'angle_optimization_parameters', 'runtime_control_parameters',
    ]


def test_package_rejects_direction_indices_and_sensor_mismatch():
    with pytest.raises(ValueError, match='0、120、240'):
        build_sensor_package(_parser(), [_report(0), _report(1), _report(2)])
    with pytest.raises(ValueError, match='sensor_id'):
        build_sensor_package(_parser(), [_report(0), _report(120), _report(240, sensor_id='sensor-B')])


def test_region_parameter_shape_is_validated_independently():
    reports = [_report(0), _report(120), _report(240)]
    reports[0]['regions']['end5cm']['parameters']['slopes']['0'] = [[1.0, 2.0]]

    with pytest.raises(ValueError, match='end5cm.*slopes'):
        build_sensor_package(_parser(), reports)


def test_unverified_phase_and_diverged_stage_produce_candidate_only():
    package = build_sensor_package(
        _parser(), [_report(0), _report(120), _report(240, stage_status='diverge')]
    )

    assert package['multi_region']['deployment_ready'] is False
    directions = package['multi_region']['direction_deployment']
    assert directions['0']['quality_gates']['optimization_usable'] is True
    assert directions['120']['quality_gates']['optimization_usable'] is True
    assert directions['240']['quality_gates']['optimization_usable'] is False
    assert directions['0']['quality_gates']['end15cm_phase_verified'] is False
    assert any('240/full slopes diverged' in failure for failure in directions['240']['failures'])


def test_no_improvement_stage_is_not_optimization_complete():
    package = build_sensor_package(
        _parser(), [_report(0), _report(120), _report(240, stage_status='no_improvement')]
    )
    directions = package['multi_region']['direction_deployment']
    assert directions['0']['quality_gates']['optimization_usable'] is True
    assert directions['120']['quality_gates']['optimization_usable'] is True
    assert directions['240']['quality_gates']['optimization_usable'] is False
    assert any('240/full slopes no_improvement' in failure for failure in directions['240']['failures'])


def test_json_round_trip_preserves_order_and_rejects_strict_deployment(tmp_path):
    package = build_sensor_package(_parser(), [_report(0), _report(120), _report(240)])
    path = tmp_path / 'sensor.json'

    write_sensor_package(package, path)
    loaded = load_sensor_package(path, expected_sensor_id='sensor-A')

    assert list(json.loads(path.read_text(encoding='utf-8'))) == list(package)
    assert loaded == package
    with pytest.raises(ValueError, match='deployment'):
        load_sensor_package(path, require_deployable=True)


def test_load_calibration_results_reads_json_and_rejects_duplicate_direct(tmp_path):
    paths = []
    for direct in (0, 120, 240):
        path = tmp_path / f'{direct}.json'
        path.write_text(json.dumps(_report(direct)), encoding='utf-8')
        paths.append(path)
    assert [report['direct'] for report in load_calibration_results(paths)] == [0, 120, 240]

    duplicate = tmp_path / 'duplicate.json'
    duplicate.write_text(json.dumps(_report(240)), encoding='utf-8')
    with pytest.raises(ValueError, match='重复'):
        load_calibration_results([*paths, duplicate])


def test_load_calibration_results_accepts_result_directories(tmp_path):
    paths = []
    for direct in (0, 120, 240):
        directory = tmp_path / f'run-direct{direct}'
        directory.mkdir()
        (directory / 'results.json').write_text(
            json.dumps(_report(direct)), encoding='utf-8'
        )
        paths.append(directory)

    reports = load_calibration_results(paths)

    assert [report['direct'] for report in reports] == [0, 120, 240]
    assert all(Path(report['_source_path']).name == 'results.json' for report in reports)


def test_comparison_report_exposes_parameters_errors_and_failed_stages():
    reports = [_report(0), _report(120), _report(240, stage_status='diverge')]

    markdown = render_calibration_comparison(reports)

    assert '| 240 | full |' in markdown
    assert 'diverged' in markdown
    assert 'weights: `[241.0, 242.0' in markdown
    assert 'point=1.250% full length' in markdown
    assert 'end=2.500% full length' in markdown
    assert 'point error (% full length)' in markdown
    assert '| 0 | end5cm | 2.500 | 1.250 | 2.500 |' in markdown
    assert 'point errors (% full length): `{"200": 1.25}`' in markdown
    assert 'end errors (% full length): `{"200": 2.5}`' in markdown
    assert 'local global phase' in markdown
    assert reports[0]['regions']['end5cm']['errors']['avg_point_err']['calib'] == .005


@pytest.mark.parametrize('length', [None, 0, -1, float('nan'), float('inf')])
def test_comparison_rejects_invalid_full_length(length):
    report = _report(0)
    report['regions']['full']['context']['ideal_len'] = length
    with pytest.raises(ValueError, match='full.*ideal_len'):
        render_calibration_comparison([report])


def _package_path(tmp_path, **shared_overrides):
    package = build_sensor_package(_parser(), [_report(0), _report(120), _report(240)])
    for name, value in shared_overrides.items():
        matches = [group for group in package['shared_parameters'].values() if name in group]
        assert len(matches) == 1
        matches[0][name] = value
    path = tmp_path / 'sensor.json'
    write_sensor_package(package, path)
    return path, package


def test_package_parser_defaults_restore_region_profiles_and_literal_directions(tmp_path):
    path, package = _package_path(tmp_path)

    defaults = package_parser_defaults(load_sensor_package(path))

    assert defaults['sensor_id'] == 'sensor-A'
    assert defaults['global_phases_set'] == -.7
    assert defaults['rot_ang'] == 0.0
    assert defaults['calibration_regions']['end5cm']['thresholds'] == REGIONS['end5cm']['thresholds']
    assert list(defaults['calibration_regions']['end5cm']['weights']) == [0, 120, 240]
    assert defaults['calibration_regions']['end5cm']['slopes'][120][0][0] == 120.0


def test_parse_main_args_loads_package_and_cli_explicit_value_wins(tmp_path):
    import main
    path, _ = _package_path(tmp_path, move_filter=11)

    loaded = main.parse_main_args([
        '--task', 'recon', '--sensor_params', str(path), '--move_filter', '5',
    ])

    assert loaded.sensor_id == 'sensor-A'
    assert loaded.move_filter == 5
    assert loaded.sensor_params == str(path)


def test_parse_main_args_keeps_task_required_and_rejects_explicit_sensor_conflict(tmp_path):
    import main
    path, package = _package_path(tmp_path)
    package['shared_parameters']['runtime_control_parameters']['task'] = 'recon'
    write_sensor_package(package, path)

    with pytest.raises(SystemExit):
        main.parse_main_args(['--sensor_params', str(path)])
    with pytest.raises(ValueError, match='sensor_id'):
        main.parse_main_args([
            '--task', 'recon', '--sensor_params', str(path), '--sensor_id', 'sensor-B',
        ])


def test_parse_main_args_rejects_unknown_package_version_before_runtime(tmp_path):
    import main
    path, package = _package_path(tmp_path)
    package['format_version'] = 999
    write_sensor_package(package, path)

    with pytest.raises(ValueError, match='format_version'):
        main.parse_main_args(['--task', 'recon', '--sensor_params', str(path)])


def test_validation_evidence_keeps_failed_candidate_non_deployable():
    package = build_sensor_package(_parser(), [_report(0), _report(120), _report(240)])
    package['shared_parameters']['dynamic_display_parameters']['direction_reference_direct'] = 240
    validation = {
        'shared_quality_gates': {'score_thresholds_verified': True},
        'directions': {
            str(direct): {
                'quality_gates': {
                    'end15cm_phase_verified': direct != 240,
                    'full_geometry_verified': direct != 240,
                },
                'failures': [] if direct != 240 else ['240-degree full reconstruction failed'],
                'phase_transport': {'end5cm': {'blocking': False, 'within_30_deg': False}},
            }
            for direct in (0, 120, 240)
        },
    }

    updated = apply_validation_results(package, validation)

    assert updated['multi_region']['deployment_ready'] is False
    assert updated['provenance']['full_geometry_validation'] == validation
    assert updated['multi_region']['available_deployment_directions'] == [0, 120]
    assert updated['multi_region']['direction_deployment']['0']['deployment_ready'] is True
    assert updated['multi_region']['direction_deployment']['240']['deployment_ready'] is False
    assert updated['multi_region']['direction_deployment']['240']['phase_transport']['end5cm']['blocking'] is False


def test_package_readiness_uses_reference_direction_when_blending_is_disabled():
    package = build_sensor_package(_parser(), [_report(0), _report(120), _report(240)])
    package['shared_parameters']['dynamic_display_parameters'].update({
        'direction_blend_enabled': False,
        'direction_reference_direct': 0,
    })
    package['multi_region']['shared_quality_gates']['score_thresholds_verified'] = True
    for direct, ready in ((0, True), (120, False), (240, False)):
        gates = package['multi_region']['direction_deployment'][str(direct)]['quality_gates']
        gates['end15cm_phase_verified'] = ready
        gates['full_geometry_verified'] = ready

    assert package_deployment_ready(package) is True

    package['shared_parameters']['dynamic_display_parameters']['direction_blend_enabled'] = True
    assert package_deployment_ready(package) is False
