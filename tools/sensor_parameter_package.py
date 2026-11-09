"""Merge regional calibration reports into an ordered sensor parameter package."""

from copy import deepcopy
import json
import os
from pathlib import Path
import sys

# 直接执行tools脚本时也从项目根目录导入主程序和其他模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, "") and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from calibration_regions import (
    resolve_calibration_region, validate_end_weight_config,
    validate_weight_group_ids,
)


FORMAT_VERSION = 2
REQUIRED_DIRECTIONS = (0, 120, 240)
REGION_ORDER = ('full', 'end15cm', 'end5cm')

PARSER_GROUPS = {
    'hardware_parameters': (
        'start_value', 'end_value', 'R', 'ideal_len', 'samp_dist_preset',
        'samp_dist_preset_sub', 'centre_fibre', 'interlaced_grating',
        'interlaced_offset',
    ),
    'calibration_experiment_parameters': (
        'interrogator', 'active_channels', 'channel_change', 'channel_layout',
        'active_angles', 'rot_dir', 'exp_directs', 'end_len', 'ss',
    ),
    'optimization_hyperparameters': (
        'freeze', 'weight_bounds', 'slope_upper_bound', 'max_iter', 'k_point',
        'k_end', 'k_pitch', 'k_radius', 'method', 'hyper_params', 'min_loss_diff',
    ),
    'dynamic_display_parameters': (
        'IP', 'PORT', 'maxsize', 'data_freq', 'use_stored_zero',
        'zero_reference_path', 'wavelength_jump_guard_enabled', 'wavelength_jump_threshold_pm',
        'total_scale', 'imu', 'imu_com', 'imu_maxlen',
        'demo_recorder', 'unwrap_threshold', 'align_threshold',
        'direction_blend_enabled', 'direction_reference_direct',
        'direction_min_curvature', 'direction_min_consecutive',
        'direction_consistency_threshold', 'direction_smooth_alpha',
        'demo_kalman_enabled', 'demo_kalman_Rk', 'demo_kalman_Bk',
        'anchor_translation_enabled', 'anchor_rotation_enabled',
        'anchor_constraint_enabled', 'anchor_offset_m',
    ),
    'reconstruction_parameters': (
        'soft', 'reverse', 'discont', 'frame_rule', 'straight_threshold',
        'rot_threshold', 'min_consecutive', 'move_filter',
        'move_filter_for_vector', 'kalman_params', 'smoothing_params',
        'interp_num', 'curvature_interp', 'nonnegative_curvature', 'sharpness',
        'end_weights', 'end_start', 'TNB_threshold',
    ),
    'initialization_parameters': ('connect', 'turn_threshold', 'sensing_ranges'),
    'angle_optimization_parameters': ('ang_step', 'ang_range'),
    'runtime_control_parameters': (
        'phase_output',
            'sensor_params',
        'use_full_transported_phase',
        'full_point_calib',
        'full_absolute_direction',
        'full_preserve_first_point',
        'end15cm_point_calib',
        'end5cm_point_calib',
        'end5cm_independent_weights',
        'end5cm_independent_weight_score',
        'end5cm_coverage_aware_weights',
        'end5cm_min_weight_effective_samples',
        'end5cm_min_weight_max_mass',
        'end5cm_uncovered_weight_policy',
        'multi_region_calib', 'optimization_region', 'optimization_regions',
        'full_segmentation', 'calibration_data_root', 'calibration_output_dir',
        'folder_path', 'radii', 'direct', 'thresholds', 'straight_trim',
        'segmentation', 'weights', 'slopes', 'task',
    ),
}

SPECIAL_DESTINATIONS = ('sensor_id', 'calibration_regions', 'global_phases_set', 'rot_ang')
TRANSIENT_DESTINATIONS = ('optim_weights_only', 'end15cm_assembly_loss', 'end15cm_assembly_loss_weight')
PATH_PARAMETER_DESTINATIONS = (
    'sensor_params', 'zero_reference_path', 'calibration_data_root',
    'calibration_output_dir',
)

def _project_relative_path(value, *, require_relative=False):
    """将项目内路径写成以 ``./`` 开头的 POSIX 相对路径，便于跨电脑迁移。"""
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        try:
            path = Path(os.path.relpath(path.resolve(), PROJECT_ROOT))
        except ValueError as exc:
            if require_relative:
                raise ValueError(f'路径无法转换为项目相对路径: {path}') from exc
            return path.as_posix()
    relative = path.as_posix()
    return relative if relative.startswith(('./', '../')) else f'./{relative}'


def _calibration_relative_path(value, calibration_data_root):
    """将区域数据目录保存为相对 calibration_data_root 的路径。"""
    if value is None:
        return None
    path = Path(value)
    root = Path(calibration_data_root)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    root = root.resolve()
    candidate = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(
            f'folder_path 必须位于 calibration_data_root 内: {path}'
        ) from exc


def _native(value):
    """递归转换 NumPy、Path 和容器值，生成严格 JSON 可序列化的数据。"""
    if isinstance(value, np.ndarray):
        return _native(value.tolist())
    if isinstance(value, np.generic):
        return _native(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError('参数包不能包含非有限数值')
    return value


def _parser_defaults(parser):
    """按 parser 注册顺序复制全部参数默认值，用于生成可审计参数包。"""
    return {
        action.dest: deepcopy(action.default)
        for action in parser._actions
        if action.dest != 'help'
    }


def _validate_parser_groups(defaults):
    """确保每个 parser 参数恰好属于一个共享参数组或特殊顶层字段。"""
    grouped = [name for names in PARSER_GROUPS.values() for name in names]
    represented = grouped + list(SPECIAL_DESTINATIONS) + list(TRANSIENT_DESTINATIONS)
    missing = [name for name in defaults if name not in represented]
    duplicate = sorted({name for name in represented if represented.count(name) > 1})
    extra = [name for name in represented if name not in defaults
             and name not in TRANSIENT_DESTINATIONS]
    if missing or duplicate or extra:
        raise ValueError(
            f'parser 参数分组不完整: missing={missing}, duplicate={duplicate}, extra={extra}'
        )


def load_calibration_results(paths):
    """读取三个结果文件或目录，并按字面方向角 0、120、240 排序。"""
    reports = []
    seen = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            path = path / 'results.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        direct = report.get('direct')
        if direct in seen:
            raise ValueError(f'定标方向重复: {direct}')
        seen.add(direct)
        report['_source_path'] = _project_relative_path(path)
        reports.append(report)
    return sorted(reports, key=lambda item: REQUIRED_DIRECTIONS.index(item['direct'])
                  if item.get('direct') in REQUIRED_DIRECTIONS else len(REQUIRED_DIRECTIONS))


def merge_region_results(base_reports, partial_reports):
    """Replace one regional result in three complete direction reports."""
    base = {r['direct']: r for r in base_reports}
    updates = {r['direct']: r for r in partial_reports}
    if set(base) != set(REQUIRED_DIRECTIONS) or set(updates) != set(REQUIRED_DIRECTIONS):
        raise ValueError('base_results和results均需要0/120/240三个方向')
    regions = [set(report.get('regions', {})) for report in updates.values()]
    if len(set(map(frozenset, regions))) != 1 or regions[0] not in ({'end15cm'}, {'end5cm'}):
        raise ValueError('results三个方向必须只包含同一区域end15cm或end5cm')
    region = next(iter(regions[0]))
    merged = []
    for direct in REQUIRED_DIRECTIONS:
        old, new = base[direct], updates[direct]
        if old['sensor_id'] != new['sensor_id']:
            raise ValueError('base_results与results的sensor_id不一致')
        if set(old['regions']) != set(REGION_ORDER):
            raise ValueError('base_results必须包含完整三区域')
        report = deepcopy(old)
        report['regions'][region] = deepcopy(new['regions'][region])
        report['_base_source_path'] = old.get('_source_path')
        report['_source_path'] = new.get('_source_path')
        merged.append(report)
    return merged


def merge_end5_results(base_reports, end5_reports):
    """Backward-compatible helper for existing end5cm callers."""
    if any(set(report.get('regions', {})) != {'end5cm'} for report in end5_reports):
        raise ValueError('results必须只包含end5cm')
    return merge_region_results(base_reports, end5_reports)


def _region_context(entry, region):
    """提取并校验结果中用于部署的区域几何与曲率分级上下文。"""
    context = entry.get('context')
    if not isinstance(context, dict):
        raise ValueError(f'{region} 缺少 context')
    required = (
        'thresholds', 'segmentation', 'global_point_ids', 'global_segment_ids',
        'optimization_region', 'sample_dist_m', 'crop_origin_m',
        'reconstruction_length_m', 'ideal_len', 'straight_trim',
    )
    if any(name not in context for name in required):
        raise ValueError(f'{region} context 不完整')
    objective = context.get('calibration_objective', 'geometry')
    if objective not in ('geometry', 'real_points'):
        raise ValueError(f'{region} calibration_objective 不合法')
    score_mode = context.get('weight_score_mode', 'spatial_window')
    if score_mode not in ('spatial_window', 'group_mean'):
        raise ValueError(f'{region} weight_score_mode 不合法')
    if score_mode == 'group_mean' and context.get('weight_group_ids') is None:
        raise ValueError(f'{region} weight_score_mode=group_mean 需要 weight_group_ids')
    return context


def _same_context(left, right):
    """比较两个方向的区域上下文，确认其点位、分段和阈值完全一致。"""
    keys = (
        'optimization_region', 'length_m', 'radii', 'thresholds', 'segmentation',
        'global_point_ids', 'global_segment_ids', 'global_sample_dist_m',
        'sample_dist_m', 'crop_origin_m', 'reconstruction_length_m',
        'ideal_len', 'straight_trim',
    )
    return (all(_native(left.get(key)) == _native(right.get(key)) for key in keys)
            and left.get('end_weights', False) == right.get('end_weights', False)
            and left.get('end_start', -5) == right.get('end_start', -5)
            and left.get('calibration_objective', 'geometry') == right.get('calibration_objective', 'geometry')
            and left.get('weight_group_ids') == right.get('weight_group_ids')
            and left.get('weight_score_mode', 'spatial_window') == right.get(
                'weight_score_mode', 'spatial_window'))


def _stage_failures(report):
    """收集一个方向各区域 slope/weight 优化未收敛的阶段。"""
    failures = []
    direct = report['direct']
    for region in REGION_ORDER:
        entry = report['regions'][region]
        stages = entry.get('optimization', {}).get('stages', {})
        for stage in ('slopes', 'weights'):
            status = stages.get(stage, {}).get('status')
            if status != 'converge':
                status_text = 'diverged' if status == 'diverge' else (status or 'missing')
                failures.append(f'{direct}/{region} {stage} {status_text}')
    return failures


def _direction_stage_failures(reports):
    """按 0/120/240 方向汇总优化阶段失败原因。"""
    return {
        str(report['direct']): _stage_failures(report)
        for report in reports
    }


def _shared_parameter(package, name, default=None):
    """跨共享参数分组查找指定参数，未记录时返回默认值。"""
    for group in package.get('shared_parameters', {}).values():
        if name in group:
            return group[name]
    return default


def package_deployment_ready(package):
    """判断参数包在当前 demo 方向模式下是否通过全部部署门禁。

    单方向模式只检查 ``direction_reference_direct``；方向混合模式要求三个
    方向均通过。该状态仍可供告警和报告使用，不强制阻止动态验证启动。
    """
    multi = package.get('multi_region', {})
    shared = multi.get('shared_quality_gates', {})
    if shared.get('score_thresholds_verified') is not True:
        return False
    states = multi.get('direction_deployment', {})
    if _shared_parameter(package, 'direction_blend_enabled', False):
        required = multi.get('directions', REQUIRED_DIRECTIONS)
    else:
        required = [_shared_parameter(package, 'direction_reference_direct', 0)]
    def direction_ready(direct):
        """检查一个字面方向角的优化、end15cm 相位和全长几何门禁。"""
        gates = states.get(str(direct), {}).get('quality_gates', {})
        return all(gates.get(name) is True for name in (
            'optimization_usable', 'end15cm_phase_verified',
            'full_geometry_verified',
        ))
    return all(direction_ready(direct) for direct in required)


def _owned_points(supports, region_index):
    """从区域支持点中扣除更短末端区域，得到无重叠的最终参数归属点。"""
    inner = set()
    for later in REGION_ORDER[region_index + 1:]:
        inner.update(supports[later])
    return [point for point in supports[REGION_ORDER[region_index]] if point not in inner]


def build_sensor_package(parser, reports, *, source_commit=None, generated_at=None):
    """合并三个方向、三个区域的优化结果，生成有序 multi-region 参数包。

    共享参数保持 parser 顺序；局部相位仅保存在 provenance 中用于相位传递
    验证，运行时的全局相位和旋转参考来自 full 区域。
    """
    defaults = _parser_defaults(parser)
    _validate_parser_groups(defaults)
    for name in PATH_PARAMETER_DESTINATIONS:
        defaults[name] = _project_relative_path(defaults[name], require_relative=True)
    defaults['folder_path'] = _calibration_relative_path(
        defaults['folder_path'], defaults['calibration_data_root'],
    )
    reports = sorted(list(reports), key=lambda item: item.get('direct', -1))
    directions = [report.get('direct') for report in reports]
    if directions != list(REQUIRED_DIRECTIONS):
        raise ValueError(f'direct 必须恰好为 0、120、240；收到 {directions}')
    sensor_ids = {report.get('sensor_id') for report in reports}
    if len(sensor_ids) != 1 or None in sensor_ids:
        raise ValueError(f'results.json 的 sensor_id 不一致: {sensor_ids}')
    sensor_id = next(iter(sensor_ids))

    for report in reports:
        if set(report.get('regions', {})) != set(REGION_ORDER):
            raise ValueError(f'{report["direct"]} 缺少 full/end15cm/end5cm 区域')

    first_entries = {region: reports[0]['regions'][region] for region in REGION_ORDER}
    contexts = {region: _region_context(first_entries[region], region) for region in REGION_ORDER}
    supports = {region: list(contexts[region]['global_point_ids']) for region in REGION_ORDER}
    region_blocks = {}
    local_phases = {}
    local_rot_angles = {}

    for region_index, region in enumerate(REGION_ORDER):
        context = contexts[region]
        thresholds = list(context['thresholds'])
        segmentation = list(context['segmentation'])
        levels = len(thresholds) + 1
        end_weights, end_start = validate_end_weight_config(
            context.get('end_weights', False), context.get('end_start', -5), len(supports[region]))
        groups = validate_weight_group_ids(context.get('weight_group_ids'), len(supports[region]))
        weight_count = levels * (max(groups)+1 if groups is not None else (2 if end_weights else 1))
        weights = {}
        slopes = {}
        errors = {}
        statuses = {}
        references = {}
        coverage_config = None
        coverage_diagnostics = {}
        local_phases[region] = {}
        local_rot_angles[region] = {}
        for report in reports:
            direct = report['direct']
            entry = report['regions'][region]
            if entry.get('status') != 'complete':
                raise ValueError(f'{direct}/{region} 未完成')
            other_context = _region_context(entry, region)
            if not _same_context(context, other_context):
                raise ValueError(f'{region} 跨方向 context 不一致')
            params = entry.get('parameters', {})
            raw_coverage = params.get('coverage_aware_weights', {})
            if not isinstance(raw_coverage, dict):
                raw_coverage = {}
            candidate_coverage = {
                'enabled': bool(raw_coverage.get('enabled', False)),
                'min_effective_samples': float(raw_coverage.get('min_effective_samples', 1.0)),
                'min_max_mass': float(raw_coverage.get('min_max_mass', 0.05)),
                'policy': raw_coverage.get('policy', 'interpolate_neutral_edges'),
            }
            if coverage_config is None:
                coverage_config = candidate_coverage
            elif coverage_config != candidate_coverage:
                raise ValueError(f'{region} 跨方向 coverage-aware weight 配置不一致')
            if candidate_coverage['enabled']:
                coverage_diagnostics[str(direct)] = deepcopy(raw_coverage)
            if params.get('weight_group_ids', groups) != groups:
                raise ValueError(f'{direct}/{region} 参数与context的权重分组不一致')
            if params.get('calibration_objective', context.get('calibration_objective', 'geometry')) != context.get('calibration_objective', 'geometry'):
                raise ValueError(f'{direct}/{region} 参数与context的定标目标不一致')
            if params.get('weight_score_mode', context.get('weight_score_mode', 'spatial_window')) != context.get(
                    'weight_score_mode', 'spatial_window'):
                raise ValueError(f'{direct}/{region} 参数与context的评分模式不一致')
            if (params.get('end_weights', end_weights) != end_weights
                    or params.get('end_start', end_start) != end_start):
                raise ValueError(f'{direct}/{region} 参数与context的末端权重配置不一致')
            direct_key = str(direct)
            weight = np.asarray(params.get('weights', {}).get(direct_key), dtype=float)
            slope = np.asarray(params.get('slopes', {}).get(direct_key), dtype=float)
            if weight.shape != (weight_count,) or not np.all(np.isfinite(weight)):
                raise ValueError(f'{direct}/{region} weights 形状应为 {(weight_count,)}，收到 {weight.shape}')
            expected_slope = (levels, len(segmentation))
            if slope.shape != expected_slope or not np.all(np.isfinite(slope)):
                raise ValueError(f'{direct}/{region} slopes 形状应为 {expected_slope}，收到 {slope.shape}')
            weights[direct_key] = weight.tolist()
            slopes[direct_key] = slope.tolist()
            errors[direct_key] = deepcopy(entry.get('errors', {}))
            statuses[direct_key] = deepcopy(entry.get('optimization', {}))
            local_phases[region][direct_key] = params.get('global_phases_set')
            references[direct_key] = deepcopy(params.get('phase_reference'))
            local_rot_angles[region][direct_key] = params.get('rot_ang')

        region_blocks[region] = {
            'calibration_objective': context.get('calibration_objective', 'geometry'),
            'calibration_geometry': {
                key: deepcopy(context.get(key)) for key in (
                    'optimization_region', 'sample_dist_m', 'crop_origin_m',
                    'reconstruction_length_m', 'ideal_len', 'straight_trim',
                )
            },
            'weight_group_ids': groups,
            'weight_score_mode': context.get('weight_score_mode', 'spatial_window'),
            'length_m': context.get('length_m'),
            'folder_path': _calibration_relative_path(
                context.get('folder_path'), defaults['calibration_data_root'],
            ),
            'radii': deepcopy(context.get('radii')),
            'thresholds': thresholds,
            'end_weights': end_weights,
            'end_start': end_start,
            'sharpness': defaults['sharpness'],
            'score_window': defaults['min_consecutive'],
            'score_boundary_mode': 'constant',
            'local_segmentation': segmentation,
            'global_segment_ids': list(context['global_segment_ids']),
            'support_point_ids': supports[region],
            'owned_point_ids': _owned_points(supports, region_index),
            'global_sample_dist_m': list(context.get('global_sample_dist_m', [])),
            'weights': weights,
            'slopes': slopes,
            'errors': errors,
            'optimization': statuses,
            'phase_reference': references,
        }
        if coverage_config and coverage_config['enabled']:
            coverage_block = deepcopy(coverage_config)
            coverage_block['directions'] = coverage_diagnostics
            region_blocks[region]['coverage_aware_weights'] = coverage_block

    reference_directions = []
    for direct in REQUIRED_DIRECTIONS:
        local_refs = [region_blocks[name]['phase_reference'][str(direct)]
                      for name in ('end15cm','end5cm')]
        if any(local_refs) and not all(local_refs):
            raise ValueError(f'{direct} 局部固定相位模式不一致；end15cm/end5cm必须配套优化')
        if all(local_refs):
            reference_directions.append(direct)

    direction_failures = _direction_stage_failures(reports)
    full_phase_values = list(local_phases['full'].values())
    full_rot_values = list(local_rot_angles['full'].values())
    global_phase = full_phase_values[0] if len(set(full_phase_values)) == 1 else None
    rot_ang = full_rot_values[0] if len(set(full_rot_values)) == 1 else None
    shared_reference_failures = []
    if global_phase is None:
        shared_reference_failures.append('full global phase differs by direction')
    if rot_ang is None:
        shared_reference_failures.append('full rot_ang differs by direction')
    direction_deployment = {}
    for direct in REQUIRED_DIRECTIONS:
        key = str(direct)
        failures = list(direction_failures[key]) + shared_reference_failures
        failures.extend([
            f'{direct}/end15cm transported phase is unverified',
            f'{direct}/full geometry reconstruction is unverified',
        ])
        direction_deployment[key] = {
            'deployment_ready': False,
            'quality_gates': {
                'optimization_usable': not direction_failures[key],
                'end15cm_phase_verified': False,
                'full_geometry_verified': False,
            },
            'failures': failures,
        }

    shared = {
        group: {name: _native(defaults[name]) for name in names}
        for group, names in PARSER_GROUPS.items()
    }
    shared['runtime_control_parameters']['use_full_transported_phase'] = bool(reference_directions)
    shared['runtime_control_parameters']['full_point_calib'] = (
        region_blocks['full']['calibration_objective'] == 'real_points')
    shared['runtime_control_parameters']['end15cm_point_calib'] = (
        region_blocks['end15cm']['calibration_objective'] == 'real_points')
    shared['runtime_control_parameters']['end5cm_point_calib'] = (
        region_blocks['end5cm']['calibration_objective'] == 'real_points')
    shared['runtime_control_parameters']['end5cm_independent_weights'] = (
        region_blocks['end5cm']['weight_group_ids'] is not None)
    shared['runtime_control_parameters']['end5cm_independent_weight_score'] = (
        region_blocks['end5cm']['weight_score_mode'] == 'group_mean')
    end5_coverage = region_blocks['end5cm'].get('coverage_aware_weights', {})
    shared['runtime_control_parameters']['end5cm_coverage_aware_weights'] = bool(
        end5_coverage.get('enabled', False))
    shared['runtime_control_parameters']['end5cm_min_weight_effective_samples'] = float(
        end5_coverage.get('min_effective_samples', 1.0))
    shared['runtime_control_parameters']['end5cm_min_weight_max_mass'] = float(
        end5_coverage.get('min_max_mass', 0.05))
    shared['runtime_control_parameters']['end5cm_uncovered_weight_policy'] = end5_coverage.get(
        'policy', 'interpolate_neutral_edges')

    package = {
        'sensor_id': sensor_id,
        'format_version': FORMAT_VERSION,
        'shared_parameters': shared,
        'multi_region': {
            'use_full_transported_phase': bool(reference_directions),
            'phase_reference_directions': reference_directions,
            'region_order': list(REGION_ORDER),
            'directions': list(REQUIRED_DIRECTIONS),
            'global_phases_set': _native(global_phase),
            'rot_ang': _native(rot_ang),
            'deployment_ready': False,
            'shared_quality_gates': {
                'score_thresholds_verified': False,
            },
            'direction_deployment': direction_deployment,
            'available_deployment_directions': [],
        },
        'regions': region_blocks,
        'provenance': {
            'source_commit': source_commit,
            'generated_at': generated_at,
            'parser_destination_order': list(defaults),
            'source_results': [
                _project_relative_path(path) for report in reports
                for path in ([report.get('_base_source_path'), report.get('_source_path')]
                             if '_base_source_path' in report else [report.get('_source_path')])
            ],
            'local_global_phases_set': local_phases,
            'local_rot_ang': local_rot_angles,
        },
    }
    return _native(package)


def _package_region_geometry(package, region):
    """Read saved geometry, or reconstruct it for older packages."""
    saved = package['regions'][region].get('calibration_geometry')
    if saved is not None:
        return saved
    defaults = package_parser_defaults(package)
    profiles = deepcopy(defaults['calibration_regions'])
    profiles['full']['segmentation'] = list(defaults['full_segmentation'])
    preset = defaults['samp_dist_preset']
    if defaults['interlaced_grating']:
        preset = sorted(list(preset) + list(defaults['samp_dist_preset_sub']))
    resolved = resolve_calibration_region(
        start_value=defaults['start_value'], end_value=defaults['end_value'],
        samp_dist_preset=preset, full_segmentation=defaults['full_segmentation'],
        profiles=profiles, multi_region_calib=False, optimization_region=region,
    )
    return {key: resolved[key] for key in (
        'optimization_region', 'sample_dist_m', 'crop_origin_m',
        'reconstruction_length_m', 'ideal_len', 'straight_trim',
    )}


def merge_region_into_package(base_package, partial_reports, *, base_source=None):
    """Layer one three-direction regional calibration onto an existing package."""
    package = deepcopy(base_package)
    if package.get('format_version') != FORMAT_VERSION or set(package.get('regions', {})) != set(REGION_ORDER):
        raise ValueError('base package缺少完整三区域或format_version不受支持')
    reports = {report.get('direct'): report for report in partial_reports}
    if len(partial_reports) != len(REQUIRED_DIRECTIONS) or set(reports) != set(REQUIRED_DIRECTIONS):
        raise ValueError('results必须恰好包含0/120/240三个方向')
    regions = [set(report.get('regions', {})) for report in reports.values()]
    if len(set(map(frozenset, regions))) != 1 or regions[0] not in ({'end15cm'}, {'end5cm'}):
        raise ValueError('results三个方向必须只包含同一区域end15cm或end5cm')
    region = next(iter(regions[0]))
    block = package['regions'][region]
    expected_geometry = _package_region_geometry(package, region)
    contexts = []
    coverages = []
    for direct in REQUIRED_DIRECTIONS:
        report = reports[direct]
        if report.get('sensor_id') != package.get('sensor_id'):
            raise ValueError(f'{direct}/{region} sensor_id与base package不一致')
        entry = report['regions'][region]
        if entry.get('status') != 'complete':
            raise ValueError(f'{direct}/{region} 未完成')
        context = _region_context(entry, region)
        contexts.append(context)
        if (context.get('optimization_region') != region
                or any(_native(context.get(key)) != _native(value)
                       for key, value in expected_geometry.items())):
            raise ValueError(f'{direct}/{region} context与base package几何配置不一致')
        folder = _calibration_relative_path(
            context.get('folder_path'), _shared_parameter(package, 'calibration_data_root'))
        if folder != block.get('folder_path'):
            raise ValueError(f'{direct}/{region} context与base package的数据目录不一致')
        expected = {
            'length_m': block.get('length_m'), 'radii': block.get('radii'),
            'thresholds': block.get('thresholds'),
            'segmentation': block.get('local_segmentation'),
            'global_point_ids': block.get('support_point_ids'),
            'global_segment_ids': block.get('global_segment_ids'),
            'global_sample_dist_m': block.get('global_sample_dist_m'),
            'owned_point_ids': block.get('owned_point_ids'),
            'end_weights': block.get('end_weights', False),
            'end_start': block.get('end_start', -5),
            'weight_group_ids': block.get('weight_group_ids'),
            'weight_score_mode': block.get('weight_score_mode', 'spatial_window'),
            'sharpness': block.get('sharpness'),
            'score_window': block.get('score_window'),
            'score_boundary_mode': block.get('score_boundary_mode', 'constant'),
        }
        if any(_native(context.get(key, expected[key])) != _native(value)
               for key, value in expected.items()):
            raise ValueError(f'{direct}/{region} context与base package的点位/分段/权重配置不一致')
        params = entry.get('parameters', {})
        for key in ('end_weights', 'end_start', 'weight_group_ids', 'weight_score_mode', 'calibration_objective'):
            if key in params and params[key] != context.get(key, expected.get(key, 'geometry')):
                raise ValueError(f'{direct}/{region} 参数与context的{key}不一致')
        levels = len(block['thresholds']) + 1
        groups = validate_weight_group_ids(block.get('weight_group_ids'), len(block['support_point_ids']))
        end_weights, _ = validate_end_weight_config(
            block.get('end_weights', False), block.get('end_start', -5), len(block['support_point_ids']))
        weight_count = levels * (max(groups) + 1 if groups is not None else (2 if end_weights else 1))
        direct_key = str(direct)
        weights = np.asarray(params.get('weights', {}).get(direct_key), dtype=float)
        slopes = np.asarray(params.get('slopes', {}).get(direct_key), dtype=float)
        if weights.shape != (weight_count,) or not np.all(np.isfinite(weights)):
            raise ValueError(f'{direct}/{region} weights形状应为{(weight_count,)}')
        expected_slopes = (levels, len(block['local_segmentation']))
        if slopes.shape != expected_slopes or not np.all(np.isfinite(slopes)):
            raise ValueError(f'{direct}/{region} slopes形状应为{expected_slopes}')
        coverage = params.get('coverage_aware_weights', {})
        coverages.append(coverage if isinstance(coverage, dict) else {})
        block['weights'][direct_key] = weights.tolist()
        block['slopes'][direct_key] = slopes.tolist()
        block['errors'][direct_key] = deepcopy(entry.get('errors', {}))
        block['optimization'][direct_key] = deepcopy(entry.get('optimization', {}))
        block['phase_reference'][direct_key] = deepcopy(params.get('phase_reference'))
        package['provenance']['local_global_phases_set'][region][direct_key] = params.get('global_phases_set')
        package['provenance']['local_rot_ang'][region][direct_key] = params.get('rot_ang')
    if any(not _same_context(contexts[0], context) for context in contexts[1:]):
        raise ValueError(f'{region} 跨方向context不一致')
    if region == 'end5cm':
        configs = [{key: coverage.get(key, default) for key, default in (
            ('enabled', False), ('min_effective_samples', 1.0),
            ('min_max_mass', 0.05), ('policy', 'interpolate_neutral_edges'))}
            for coverage in coverages]
        if any(config != configs[0] for config in configs[1:]):
            raise ValueError('end5cm跨方向coverage-aware配置不一致')
        block.pop('coverage_aware_weights', None)
        if configs[0]['enabled']:
            block['coverage_aware_weights'] = dict(configs[0], directions={
                str(direct): deepcopy(coverage)
                for direct, coverage in zip(REQUIRED_DIRECTIONS, coverages)
            })
    block['calibration_objective'] = contexts[0].get('calibration_objective', 'geometry')
    block['calibration_geometry'] = deepcopy(expected_geometry)
    runtime = package['shared_parameters']['runtime_control_parameters']
    runtime[f'{region}_point_calib'] = block['calibration_objective'] == 'real_points'
    if region == 'end5cm':
        coverage = block.get('coverage_aware_weights', {})
        runtime['end5cm_coverage_aware_weights'] = bool(coverage.get('enabled', False))
        runtime['end5cm_min_weight_effective_samples'] = float(coverage.get('min_effective_samples', 1.0))
        runtime['end5cm_min_weight_max_mass'] = float(coverage.get('min_max_mass', 0.05))
        runtime['end5cm_uncovered_weight_policy'] = coverage.get('policy', 'interpolate_neutral_edges')
    references = []
    for direct in REQUIRED_DIRECTIONS:
        key = str(direct)
        pair = [package['regions'][name]['phase_reference'][key] for name in ('end15cm', 'end5cm')]
        if any(pair) and not all(pair):
            raise ValueError(f'{direct} 局部固定相位模式不一致；end15cm/end5cm必须配套优化')
        if all(pair):
            references.append(direct)
    multi = package['multi_region']
    multi['phase_reference_directions'] = references
    multi['use_full_transported_phase'] = bool(references)
    runtime['use_full_transported_phase'] = bool(references)
    provenance = package['provenance']
    provenance.setdefault('source_results', []).extend(
        _project_relative_path(reports[direct].get('_source_path'))
        for direct in REQUIRED_DIRECTIONS if reports[direct].get('_source_path')
    )
    provenance.setdefault('region_merges', []).append({
        'region': region,
        'base_package': _project_relative_path(base_source) if base_source else None,
        'results': [_project_relative_path(reports[direct].get('_source_path'))
                    for direct in REQUIRED_DIRECTIONS],
    })
    provenance.pop('full_geometry_validation', None)
    multi['deployment_ready'] = False
    multi['available_deployment_directions'] = []
    multi.setdefault('shared_quality_gates', {})['score_thresholds_verified'] = False
    for direct in REQUIRED_DIRECTIONS:
        key = str(direct)
        stages = {name: {'optimization': block['optimization'][key]}
                  for name, block in package['regions'].items()}
        failures = _stage_failures({'direct': direct, 'regions': stages})
        failures += [f'{direct}/end15cm transported phase is unverified',
                     f'{direct}/full geometry reconstruction is unverified']
        multi['direction_deployment'][key] = {
            'deployment_ready': False,
            'quality_gates': {
                'optimization_usable': len(failures) == 2,
                'end15cm_phase_verified': False,
                'full_geometry_verified': False,
            },
            'failures': failures,
        }
    return _native(package)


def build_single_direction_demo_package(
    base_package, override_result, *, direction=0, base_source=None,
    override_source=None,
):
    """Create an auditable one-direction demo package.

    The base package remains authoritative for ``full`` and ``end15cm``.  The
    supplied result must contain only a complete ``end5cm`` report for the
    selected direction.  The package schema still carries all three direction
    slots because the existing multi-region assembler validates that topology;
    runtime ``exp_directs`` and demo direction selection are restricted to the
    selected direction, while unavailable end5cm slots are schema-only copies
    of the selected group-mean parameters.
    """
    if direction not in REQUIRED_DIRECTIONS:
        raise ValueError(f'单方向demo direction必须属于 {REQUIRED_DIRECTIONS}: {direction}')
    package = deepcopy(base_package)
    if package.get('format_version') != FORMAT_VERSION:
        raise ValueError('base package format_version 不受支持')
    if override_result.get('sensor_id') != package.get('sensor_id'):
        raise ValueError('override result 与 base package 的 sensor_id 不一致')
    if override_result.get('direct') != direction:
        raise ValueError(f'override result 必须是 direct={direction}')
    if set(override_result.get('regions', {})) != {'end5cm'}:
        raise ValueError('override result must contain only end5cm')
    entry = override_result['regions']['end5cm']
    if entry.get('status') != 'complete':
        raise ValueError('override result 的 end5cm 必须 status=complete')

    block = package.get('regions', {}).get('end5cm')
    if block is None:
        raise ValueError('base package 缺少 end5cm')
    context = entry.get('context', {})
    parameters = entry.get('parameters', {})
    if context.get('weight_score_mode', 'spatial_window') != 'group_mean':
        raise ValueError('override result 必须使用 weight_score_mode=group_mean')
    groups = context.get('weight_group_ids', block.get('weight_group_ids'))
    if groups != block.get('weight_group_ids'):
        raise ValueError('override result 的 weight_group_ids 与 base package 不一致')
    if groups is None:
        raise ValueError('single-direction end5 demo 需要 weight_group_ids')

    levels = len(block.get('thresholds', ())) + 1
    expected_weight_count = levels * (max(groups) + 1)
    segmentation = block.get('local_segmentation', ())
    expected_slope_shape = (levels, len(segmentation))
    direct_key = str(direction)
    weights = parameters.get('weights', {}).get(direct_key, parameters.get('weights', {}).get(direction))
    slopes = parameters.get('slopes', {}).get(direct_key, parameters.get('slopes', {}).get(direction))
    weight_array = np.asarray(weights, dtype=float) if weights is not None else np.asarray([])
    slope_array = np.asarray(slopes, dtype=float) if slopes is not None else np.asarray([])
    if weight_array.shape != (expected_weight_count,) or not np.all(np.isfinite(weight_array)):
        raise ValueError(
            f'override end5cm weights shape 应为 {(expected_weight_count,)}，收到 {weight_array.shape}'
        )
    if slope_array.shape != expected_slope_shape or not np.all(np.isfinite(slope_array)):
        raise ValueError(
            f'override end5cm slopes shape 应为 {expected_slope_shape}，收到 {slope_array.shape}'
        )
    phase = parameters.get('global_phases_set')
    if phase is None or not np.isfinite(float(phase)):
        raise ValueError('override end5cm 缺少有限 global_phases_set')

    end5 = package['regions']['end5cm']
    end5['weight_group_ids'] = list(groups)
    end5['weight_score_mode'] = 'group_mean'
    coverage = parameters.get('coverage_aware_weights')
    if isinstance(coverage, dict) and coverage.get('enabled', False):
        end5['coverage_aware_weights'] = deepcopy(coverage)
    for direct in REQUIRED_DIRECTIONS:
        key = str(direct)
        end5['weights'][key] = weight_array.tolist()
        end5['slopes'][key] = slope_array.tolist()
    end5['optimization'][direct_key] = deepcopy(entry.get('optimization', {}))
    end5['errors'][direct_key] = deepcopy(entry.get('errors', {}))
    end5['phase_reference'][direct_key] = deepcopy(parameters.get('phase_reference'))

    runtime = package['shared_parameters']['runtime_control_parameters']
    runtime['multi_region_calib'] = True
    runtime['optimization_region'] = 'full'
    runtime['end5cm_coverage_aware_weights'] = bool(
        end5.get('coverage_aware_weights', {}).get('enabled', False))
    runtime['end5cm_min_weight_effective_samples'] = float(
        end5.get('coverage_aware_weights', {}).get('min_effective_samples', 1.0))
    runtime['end5cm_min_weight_max_mass'] = float(
        end5.get('coverage_aware_weights', {}).get('min_max_mass', 0.05))
    runtime['end5cm_uncovered_weight_policy'] = end5.get(
        'coverage_aware_weights', {}).get('policy', 'interpolate_neutral_edges')
    package['shared_parameters']['calibration_experiment_parameters']['exp_directs'] = [direction]
    display = package['shared_parameters']['dynamic_display_parameters']
    display['direction_blend_enabled'] = False
    display['direction_reference_direct'] = direction

    local_phases = package.setdefault('provenance', {}).setdefault(
        'local_global_phases_set', {}
    )
    local_phases.setdefault('full', {})
    local_phases.setdefault('end15cm', {})
    local_phases.setdefault('end5cm', {})
    local_phases['end5cm'] = {
        str(direct): (float(phase) if direct == direction else None)
        for direct in REQUIRED_DIRECTIONS
    }
    single_demo = {
        'mode': 'single_direction_dynamic_demo',
        'runtime_directions': [direction],
        'direction_reference_direct': direction,
        'unavailable_directions': [d for d in REQUIRED_DIRECTIONS if d != direction],
        'schema_only_end5_directions': [d for d in REQUIRED_DIRECTIONS if d != direction],
        'note': '仅用于0度动态实验；120/240度未取得同配置end5cm结果，不得用于部署或方向混合。',
        'base_package': _project_relative_path(base_source) if base_source else None,
        'override_result': _project_relative_path(override_source) if override_source else None,
    }
    package['provenance']['single_direction_demo'] = single_demo
    if override_source:
        package['provenance'].setdefault('source_results', []).append(
            _project_relative_path(override_source)
        )

    multi = package['multi_region']
    multi['deployment_ready'] = False
    multi['available_deployment_directions'] = []
    multi.setdefault('shared_quality_gates', {})['score_thresholds_verified'] = False
    for direct in REQUIRED_DIRECTIONS:
        state = multi.setdefault('direction_deployment', {}).setdefault(str(direct), {
            'deployment_ready': False, 'quality_gates': {}, 'failures': [],
        })
        state['deployment_ready'] = False
        state.setdefault('quality_gates', {})['optimization_usable'] = False
        state.setdefault('quality_gates', {})['end15cm_phase_verified'] = False
        state.setdefault('quality_gates', {})['full_geometry_verified'] = False
        message = 'single-direction demo package 仅允许 direction=0 实验'
        if message not in state.setdefault('failures', []):
            state['failures'].append(message)
    return _native(package)


def package_parameter_destinations(package):
    """按参数包分组顺序返回所有可回填 argparse 的参数名。"""
    names = []
    for values in package['shared_parameters'].values():
        names.extend(values)
    names.extend(SPECIAL_DESTINATIONS)
    names.extend(TRANSIENT_DESTINATIONS)
    return names


def _direction_keyed(values):
    """把 JSON 对象中的数值方向键恢复为整数 0、120、240。"""
    if not isinstance(values, dict):
        return deepcopy(values)
    converted = {}
    for key, value in values.items():
        try:
            direct = int(key)
        except (TypeError, ValueError):
            direct = key
        converted[direct] = deepcopy(value)
    return converted


def package_parser_defaults(package):
    """Flatten one validated package into argparse defaults.

    Region blocks are converted back to the existing ``calibration_regions``
    schema. JSON direction keys become literal integer angles so the unchanged
    optimizer and reconstructor can index them with 0/120/240.
    """
    defaults = {}
    for group in package['shared_parameters'].values():
        group = deepcopy(group)
        # Old packages used the pre-canonical runtime key.  Normalize it before
        # argparse sees defaults; the old key is added back below only for callers
        # that inspect compatibility defaults directly.
        if 'end5cm_groupwise_weight_score' in group and 'end5cm_independent_weight_score' not in group:
            group['end5cm_independent_weight_score'] = group.pop('end5cm_groupwise_weight_score')
        defaults.update(group)
    defaults['sensor_id'] = package['sensor_id']
    defaults['global_phases_set'] = package['multi_region']['global_phases_set']
    defaults['rot_ang'] = package['multi_region']['rot_ang']
    # Region metadata is authoritative; missing fields in old packages disable the new objective.
    defaults['full_point_calib'] = package['regions'].get('full', {}).get(
        'calibration_objective', 'geometry') == 'real_points'
    defaults['end15cm_point_calib'] = package['regions'].get('end15cm', {}).get(
        'calibration_objective', 'geometry') == 'real_points'
    defaults['end5cm_point_calib'] = package['regions'].get('end5cm', {}).get(
        'calibration_objective', 'geometry') == 'real_points'
    defaults['end5cm_independent_weights'] = package['regions'].get('end5cm', {}).get('weight_group_ids') is not None
    defaults['end5cm_independent_weight_score'] = package['regions'].get('end5cm', {}).get(
        'weight_score_mode', 'spatial_window') == 'group_mean'
    coverage = package['regions'].get('end5cm', {}).get('coverage_aware_weights', {})
    defaults['end5cm_coverage_aware_weights'] = bool(coverage.get('enabled', False))
    defaults['end5cm_min_weight_effective_samples'] = float(
        coverage.get('min_effective_samples', 1.0))
    defaults['end5cm_min_weight_max_mass'] = float(
        coverage.get('min_max_mass', 0.05))
    defaults['end5cm_uncovered_weight_policy'] = coverage.get(
        'policy', 'interpolate_neutral_edges')
    # Compatibility readback for code that used the old flattened key.
    defaults['end5cm_groupwise_weight_score'] = defaults['end5cm_independent_weight_score']
    # This is a per-run optimization control, never inherited from a package.
    defaults['optim_weights_only'] = False
    defaults['end15cm_assembly_loss'] = False
    defaults['end15cm_assembly_loss_weight'] = 1.0
    defaults['rot_dir'] = _direction_keyed(defaults.get('rot_dir'))
    defaults['sensing_ranges'] = _direction_keyed(defaults.get('sensing_ranges'))
    # Packages created before the continuity guard remain valid and use the
    # parser's safe default when this optional field is absent.
    defaults.setdefault('wavelength_jump_guard_enabled', True)
    defaults.setdefault('wavelength_jump_threshold_pm', 12000.0)

    profiles = {}
    for region, block in package['regions'].items():
        profiles[region] = {
            'calibration_objective': block.get('calibration_objective', 'geometry'),
            'weight_group_ids': deepcopy(block.get('weight_group_ids')),
            'weight_score_mode': deepcopy(block.get('weight_score_mode', 'spatial_window')),
            'length_m': deepcopy(block.get('length_m')),
            'folder_path': deepcopy(block.get('folder_path')),
            'radii': deepcopy(block.get('radii')),
            'thresholds': deepcopy(block['thresholds']),
            'end_weights': deepcopy(block.get('end_weights', False)),
            'end_start': deepcopy(block.get('end_start', -5)),
            'segmentation': deepcopy(block['local_segmentation']),
            'sharpness': deepcopy(block.get('sharpness')),
            'score_window': deepcopy(block.get('score_window')),
            'score_boundary_mode': deepcopy(block.get('score_boundary_mode', 'constant')),
            'weights': _direction_keyed(block['weights']),
            'slopes': _direction_keyed(block['slopes']),
            'global_point_ids': deepcopy(block.get('support_point_ids')),
            'global_segment_ids': deepcopy(block.get('global_segment_ids')),
            'owned_point_ids': deepcopy(block.get('owned_point_ids')),
            'coverage_aware_weights': deepcopy(block.get('coverage_aware_weights', {
                'enabled': False,
                'min_effective_samples': 1.0,
                'min_max_mass': 0.05,
                'policy': 'interpolate_neutral_edges',
            })),
        }
    defaults['calibration_regions'] = profiles
    return defaults


def render_calibration_comparison(reports):
    """以完整传感器长度百分比比较各区域误差，不修改原始结果。"""
    reports = sorted(reports, key=lambda item: item['direct'])
    full_lengths = {}
    for report in reports:
        value = report['regions']['full']['context'].get('ideal_len')
        try:
            length = float(value)
        except (TypeError, ValueError):
            raise ValueError('comparison 的 full context ideal_len 必须为有限正数 (m)') from None
        if not np.isfinite(length) or length <= 0:
            raise ValueError('comparison 的 full context ideal_len 必须为有限正数 (m)')
        full_lengths[report['direct']] = length
    lines = [
        '# Multi-region calibration result comparison', '',
        'Error (%) = error (m) / full sensor length (m) × 100. '
        'All regions use the full sensor length, including end15cm and end5cm. '
        'Weighted loss is scaled by the same full length.', '',
        '| direct | region | weighted loss (% full length) | point error (% full length) | end error (% full length) | weight score mode | slopes | weights |',
        '|---:|---|---:|---:|---:|---|---|---|',
    ]
    for report in reports:
        direct = report['direct']
        percent_scale = 100.0 / full_lengths[direct]
        for region in REGION_ORDER:
            entry = report['regions'][region]
            errors = entry['errors']
            stages = entry.get('optimization', {}).get('stages', {})
            slope_status = stages.get('slopes', {}).get('status', 'missing')
            weight_status = stages.get('weights', {}).get('status', 'missing')
            slope_status = 'diverged' if slope_status == 'diverge' else slope_status
            weight_status = 'diverged' if weight_status == 'diverge' else weight_status
            score_mode = entry.get('context', {}).get('weight_score_mode', 'spatial_window')
            lines.append(
                f'| {direct} | {region} | {percent_scale * errors["normal_weighted_loss"]:.3f} | '
                f'{percent_scale * errors["avg_point_err"]["calib"]:.3f} | '
                f'{percent_scale * errors["avg_end_err"]["calib"]:.3f} | '
                f'{score_mode} | {slope_status} | {weight_status} |'
            )
    lines.extend(['', '## Parameters and per-radius errors', ''])
    for report in reports:
        direct = report['direct']
        percent_scale = 100.0 / full_lengths[direct]
        lines.extend([f'### Direction {direct}', '',
                      f'- full sensor length: `{full_lengths[direct]:.6f} m`', ''])
        for region in REGION_ORDER:
            entry = report['regions'][region]
            params = entry['parameters']
            key = str(direct)
            point = entry['errors'].get('point_errors_by_sample', {}).get('circ', {})
            end = entry['errors'].get('end_errors_by_sample', {}).get('circ', {})
            point_percent = {radius: percent_scale * value for radius, value in point.items()}
            end_percent = {radius: percent_scale * value for radius, value in end.items()}
            radius_lines = []
            for radius, point_error in point.items():
                end_error = end.get(str(radius), end.get(radius))
                if end_error is not None:
                    radius_lines.append(
                        f'- radius {radius}: point={percent_scale * point_error:.3f}% full length, '
                        f'end={percent_scale * end_error:.3f}% full length'
                    )
            lines.extend([
                f'#### {region}', '',
                f'- calibration objective: `{entry["context"].get("calibration_objective", "geometry")}`',
                f'- real-point weight groups: `{json.dumps(entry["context"].get("weight_group_ids"))}`',
                f'- optimization loss definitions: `{json.dumps(entry.get("optimization", {}).get("loss_definitions", {}), ensure_ascii=False)}`',
                f'- thresholds: `{json.dumps(entry["context"]["thresholds"])}`',
                f'- local global phase: `{params.get("global_phases_set")}`',
                f'- local rot_ang: `{params.get("rot_ang")}`',
                f'- weights: `{json.dumps(params["weights"][key])}`',
                f'- slopes: `{json.dumps(params["slopes"][key])}`',
                f'- point errors (% full length): `{json.dumps(point_percent, ensure_ascii=False)}`',
                f'- end errors (% full length): `{json.dumps(end_percent, ensure_ascii=False)}`',
                *radius_lines,
                '',
            ])
    return '\n'.join(lines).rstrip() + '\n'


def write_sensor_package(package, path):
    """创建父目录并原子写入严格 JSON 参数包。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(_native(package), ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        encoding='utf-8',
    )
    temporary.replace(path)


def load_sensor_package(path, expected_sensor_id=None, *, require_deployable=False):
    """读取参数包并校验格式版本、传感器编号及可选部署状态。"""
    package = json.loads(Path(path).read_text(encoding='utf-8'))
    if package.get('format_version') != FORMAT_VERSION:
        raise ValueError(f'不支持的参数包 format_version={package.get("format_version")}')
    if expected_sensor_id is not None and package.get('sensor_id') != expected_sensor_id:
        raise ValueError(
            f'sensor_id 不一致: expected={expected_sensor_id}, actual={package.get("sensor_id")}'
        )
    if require_deployable and not package_deployment_ready(package):
        failures = []
        for state in package.get('multi_region', {}).get('direction_deployment', {}).values():
            failures.extend(state.get('failures', []))
        raise ValueError(f'parameter package is not deployment ready: {failures}')
    return package


def apply_validation_results(package, validation):
    """Attach immutable validation evidence and refresh per-direction gates."""
    package = deepcopy(package)
    validation = deepcopy(validation)
    score_evidence = validation.get('score_evidence', {})
    if score_evidence.get('source_path') is not None:
        score_evidence['source_path'] = _project_relative_path(
            score_evidence['source_path'], require_relative=True,
        )
    multi = package['multi_region']
    validation_directions = validation.get('directions', {})
    missing = [str(d) for d in multi['directions'] if str(d) not in validation_directions]
    if missing:
        raise ValueError(f'validation 缺少方向: {missing}')
    score_verified = bool(validation.get('shared_quality_gates', {}).get(
        'score_thresholds_verified', False
    ))
    multi['shared_quality_gates'] = deepcopy(validation.get('shared_quality_gates', {}))
    multi['shared_quality_gates']['score_thresholds_verified'] = score_verified
    available = []
    for direct in multi['directions']:
        key = str(direct)
        state = multi['direction_deployment'][key]
        evidence = validation_directions[key]
        evidence_gates = evidence.get('quality_gates', {})
        gates = state['quality_gates']
        gates['end15cm_phase_verified'] = bool(
            evidence_gates.get('end15cm_phase_verified', False)
        )
        gates['full_geometry_verified'] = bool(
            evidence_gates.get('full_geometry_verified', False)
        )
        state['phase_transport'] = deepcopy(evidence.get('phase_transport', {}))
        state['full_geometry'] = deepcopy(evidence.get('full_geometry', {}))
        optimization_failures = [
            item for item in state.get('failures', [])
            if 'transported phase is unverified' not in item
            and 'full geometry reconstruction is unverified' not in item
        ]
        state['failures'] = optimization_failures + list(evidence.get('failures', []))
        state['deployment_ready'] = (
            score_verified
            and all(gates.get(name) is True for name in (
                'optimization_usable', 'end15cm_phase_verified',
                'full_geometry_verified',
            ))
        )
        if state['deployment_ready']:
            available.append(direct)
    multi['available_deployment_directions'] = available
    multi['deployment_ready'] = package_deployment_ready(package)
    package['provenance']['full_geometry_validation'] = deepcopy(validation)
    return _native(package)


def main(argv=None):
    """从三个方向的 results.json 导出参数包及可选对比文档。"""
    import argparse
    from datetime import datetime, timezone
    import subprocess

    cli = argparse.ArgumentParser(description='Merge 0/120/240 regional calibration results')
    cli.add_argument('--results', nargs=3, required=True, metavar=('DIRECT0', 'DIRECT120', 'DIRECT240'))
    cli.add_argument('--base_results', nargs='+',
                     help='一个已有参数包，或旧的完整0/120/240结果；results仅包含新end15cm或end5cm')
    cli.add_argument('--output', required=True)
    cli.add_argument('--comparison')
    args = cli.parse_args(argv)
    from main import build_argument_parser

    reports = load_calibration_results(args.results)
    base_package = None
    if args.base_results:
        if len(args.base_results) == 1:
            if Path(args.base_results[0]).resolve() == Path(args.output).resolve():
                raise ValueError('output不能覆盖base_results参数包；请使用新文件名')
            base_package = load_sensor_package(args.base_results[0])
        elif len(args.base_results) == 3:
            reports = merge_region_results(load_calibration_results(args.base_results), reports)
        else:
            cli.error('--base_results需要一个参数包或三个完整results.json')
    try:
        source_commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True, encoding='utf-8',
        ).strip()
    except (OSError, subprocess.SubprocessError):
        source_commit = None
    if base_package is None:
        package = build_sensor_package(
            build_argument_parser(), reports, source_commit=source_commit,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    else:
        if args.comparison:
            cli.error('参数包作base_results时不能生成comparison；请先完成新的重构验证')
        package = merge_region_into_package(
            base_package, reports, base_source=args.base_results[0],
        )
        package['provenance']['source_commit'] = source_commit
        package['provenance']['generated_at'] = datetime.now(timezone.utc).isoformat()
    write_sensor_package(package, args.output)
    if args.comparison:
        Path(args.comparison).write_text(
            render_calibration_comparison(reports), encoding='utf-8',
        )


if __name__ == '__main__':
    main()
