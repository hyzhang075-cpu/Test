"""按区域执行独立定标，保存结果，并诊断实际用于选档的基础曲率。"""

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import pprint
import re
from uuid import uuid4

import numpy as np

from tools.end5_weight_coverage import compute_groupwise_weight_coverage


# 这些参数控制任务/界面/输出，不属于 Optimiser/Sensor 的构造参数。
CONTROL_KEYS = {
    'end15cm_assembly_loss', 'end15cm_assembly_loss_weight', 'phase_output',
    'full_point_calib', 'full_absolute_direction', 'full_preserve_first_point', 'end15cm_point_calib',
    'end5cm_independent_weights', 'end5cm_groupwise_weight_score',
    'end5cm_independent_weight_score', 'optim_weights_only',
    'end5cm_coverage_aware_weights', 'end5cm_min_weight_effective_samples',
    'end5cm_min_weight_max_mass', 'end5cm_uncovered_weight_policy',
    '_resolved_weight_group_ids',
    'use_full_transported_phase', '_phase_source_jobs',
    'task', 'sensor_params', '_sensor_package', '_explicit_cli_parameters',
    'ang_step', 'ang_range', 'multi_region_calib', 'optimization_region',
    'optimization_regions', 'full_segmentation', 'calibration_regions',
    'calibration_data_root', 'calibration_output_dir', '_explicit_seed_parameters',
    '_full_segmentation_explicit',
    'total_scale', 'imu', 'imu_com', 'imu_maxlen', 'demo_recorder', 'unwrap_threshold',
    'align_threshold', 'direction_blend_enabled', 'direction_reference_direct',
    'direction_min_curvature', 'direction_min_consecutive', 'direction_consistency_threshold',
    'direction_smooth_alpha', 'demo_kalman_enabled', 'demo_kalman_Rk', 'demo_kalman_Bk',
    'anchor_constraint_enabled', 'anchor_translation_enabled', 'anchor_rotation_enabled',
    'anchor_offset_m',
}


def optimizer_parameters(args):
    """复制可传给 Optimiser 的参数，排除任务调度、界面和输出控制项。"""
    parameters = {key: deepcopy(value) for key, value in vars(args).items() if key not in CONTROL_KEYS}
    parameters['end5cm_point_calib'] = bool(
        getattr(args, 'end5cm_point_calib', False) and args.optimization_region == 'end5cm')
    parameters['real_point_calib'] = bool(
        (getattr(args, 'full_point_calib', False) and args.optimization_region == 'full')
        or (getattr(args, 'end15cm_point_calib', False) and args.optimization_region == 'end15cm')
        or parameters['end5cm_point_calib'])
    parameters['real_point_absolute_direction'] = bool(
        getattr(args, 'full_absolute_direction', False) and args.optimization_region == 'full')
    parameters['preserve_first_point'] = bool(
        getattr(args, 'full_preserve_first_point', False) and args.optimization_region == 'full')
    parameters['end5cm_independent_weight_score'] = bool(
        getattr(args, 'end5cm_independent_weight_score', False)
        and args.optimization_region == 'end5cm')
    parameters['optim_weights_only'] = bool(getattr(args, 'optim_weights_only', False))
    parameters['end5cm_coverage_aware_weights'] = bool(
        getattr(args, 'end5cm_coverage_aware_weights', False)
        and (args.optimization_region == 'end5cm' or args.task in ('recon', 'demo')))
    parameters['end5cm_min_weight_effective_samples'] = float(
        getattr(args, 'end5cm_min_weight_effective_samples', 1.0))
    parameters['end5cm_min_weight_max_mass'] = float(
        getattr(args, 'end5cm_min_weight_max_mass', 0.05))
    parameters['end5cm_uncovered_weight_policy'] = getattr(
        args, 'end5cm_uncovered_weight_policy', 'interpolate_neutral_edges')
    parameters['source_sensor_params'] = getattr(args, 'sensor_params', None)
    parameters['weight_group_ids'] = deepcopy(getattr(args, '_resolved_weight_group_ids', None))
    return parameters


def prepare_calibration_jobs(args, configure):
    """先校验全部任务，再优化；每个任务从原始 parser 配置独立复制。

不将上一个区域解析后的 folder_path、裁剪或最优参数带入下一个区域。
多区域运行的差异参数应放在各区域字典中，避免单个覆盖值误用于全部长度。
"""
    regions = args.optimization_regions if args.multi_region_calib else [args.optimization_region]
    if (not isinstance(regions, list) or not regions or
            any(not isinstance(region, str) for region in regions) or len(set(regions)) != len(regions)):
        raise ValueError('optimization_regions 必须是非空、无重复的区域名称列表')
    if len(regions) > 1:
        for key in ('folder_path', 'radii', 'thresholds', 'segmentation', 'straight_trim', 'weights', 'slopes', 'end_weights', 'end_start'):
            if getattr(args, key) is not None:
                raise ValueError(f'批量任务不能共用单个 {key} 覆盖值；请写入 calibration_regions 各区域配置')
    jobs = []
    phase_enabled = bool(getattr(args, 'use_full_transported_phase', False))
    if phase_enabled and args.task == 'optim':
        if args.reverse:
            raise ValueError('固定上游相位模式目前仅支持正向传感器点位')
        for region in regions:
            dependency = {'end15cm':'full', 'end5cm':'end15cm'}.get(region)
            if dependency and dependency not in regions[:regions.index(region)] and getattr(args, '_sensor_package', None) is None:
                raise ValueError('固定相位局部优化需要按full/end15cm/end5cm顺序运行，或提供sensor_params来源包')
    for region in regions:
        job = deepcopy(args)
        job.optimization_region = region
        context = configure(job)
        if not Path(job.folder_path).is_dir():
            raise ValueError(f'{region} 数据目录不存在: {job.folder_path}')
        jobs.append((job, context))
        if phase_enabled and args.task == 'optim' and region != 'full':
            source_jobs = {}
            for source_region in ('full', 'end15cm'):
                source = deepcopy(args)
                source.multi_region_calib = False
                source.optimization_region = source_region
                source.weights = source.slopes = None
                source._explicit_seed_parameters = []
                source_context = configure(source)
                source_jobs[source_region] = (source, source_context)
            job._phase_source_jobs = source_jobs
    return jobs


def _native(value):
    """将 NumPy 结果转成可复制的 Python/JSON 值；缺失指标以 null 表示。"""
    if isinstance(value, np.ndarray):
        return _native(value.tolist())
    if isinstance(value, np.generic):
        return _native(value.item())
    if isinstance(value, dict):
        return {key: _native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _save_report(path, report):
    """以临时文件原子写入 JSON 报告，避免中断时留下半写文件。"""
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(_native(report), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def _report_relative_folder(value, calibration_data_root):
    """Store a calibration folder relative to the configured data root."""
    if value is None:
        return None
    path = Path(value)
    root = Path(calibration_data_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    if not path.is_absolute():
        return path.as_posix().removeprefix('./')
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def collect_calibration_result(optim, stages):
    """收集当前方向最优参数与最终正常模式误差，不将 slope 阶段 loss 当作验收误差。"""
    normal_loss = (optim.k_point * optim.avg_point_err['calib']
                   + optim.k_end * optim.avg_end_err['calib']
                   + optim.k_pitch * optim.avg_pitch_err + optim.k_radius * optim.avg_radius_err)
    weight_bounds = optim.weight_bounds[0] if (
        isinstance(optim.weight_bounds, list) and len(optim.weight_bounds) == 1
    ) else optim.weight_bounds
    optimization = deepcopy(stages)
    coverage_enabled = bool(getattr(optim, 'end5cm_coverage_aware_weights', False))
    free_indices = None
    derived_indices = None
    coverage_info = None
    if coverage_enabled:
        ensure_support = getattr(optim, '_ensure_coverage_support_map', None)
        support_map = deepcopy(
            ensure_support() if ensure_support is not None
            else getattr(optim, '_coverage_support_map', None)
        )
        if support_map is None:
            raise ValueError('coverage-aware weights 已启用但缺少 support map')
        free_indices = np.asarray(optim._get_weight_optim_indices(), dtype=int)
        all_indices = np.arange(np.asarray(optim.weights[optim.direct]).size, dtype=int)
        derived_indices = np.setdiff1d(all_indices, free_indices)
        coverage_info = {
            'enabled': True,
            'min_effective_samples': float(optim.end5cm_min_weight_effective_samples),
            'min_max_mass': float(optim.end5cm_min_weight_max_mass),
            'policy': getattr(optim, 'end5cm_uncovered_weight_policy', 'interpolate_neutral_edges'),
            'free_parameter_count': int(free_indices.size),
            'derived_parameter_count': int(derived_indices.size),
            'support_map': support_map,
        }
    optimization['parameter_bounds'] = diagnose_parameter_bounds(
        weights=optim.weights[optim.direct],
        slopes=optim.slopes[optim.direct],
        weight_bounds=weight_bounds,
        slope_upper_bound=optim.slope_upper_bound,
        free_weight_indices=free_indices,
        derived_weight_indices=derived_indices,
    )
    if coverage_info is not None:
        optimization['coverage_aware_weights'] = coverage_info
    calibration_context = getattr(optim, 'calibration_context', None) or {}
    return _native({
        'parameters': {
            'weights': {optim.direct: optim.weights[optim.direct]},
            'slopes': {optim.direct: optim.slopes[optim.direct]},
            'end_weights': bool(getattr(optim, 'end_weights', False)),
            'end_start': getattr(optim, 'end_start', (getattr(optim, 'calibration_context', None) or {}).get('end_start', -5)),
            'global_phases_set': optim.global_phases_set,
            'rot_ang': optim.rot_ang,
            'phase_reference': getattr(optim, 'phase_reference', None),
            'calibration_objective': ('real_points' if (
                getattr(optim, 'real_point_calib', False)
                or getattr(optim, 'end5cm_point_calib', False))
                                      else 'geometry'),
            'weight_group_ids': getattr(optim, 'weight_group_ids', None),
            'weight_score_mode': calibration_context.get(
                'weight_score_mode',
                'group_mean' if getattr(optim, 'end5cm_independent_weight_score', False)
                else 'spatial_window',
            ),
            'source_sensor_params': getattr(optim, 'source_sensor_params', None),
            'coverage_aware_weights': coverage_info or {'enabled': False},
        },
        'optimized_directions': [optim.direct],
        'errors': {
            'normal_weighted_loss': normal_loss,
            'avg_point_err': optim.avg_point_err, 'avg_end_err': optim.avg_end_err,
            'avg_pitch_err': optim.avg_pitch_err, 'avg_radius_err': optim.avg_radius_err,
            'point_errors_by_sample': optim.point_errors_avg,
            'end_errors_by_sample': optim.end_errors,
        },
        'optimization': optimization,
    })


def diagnose_parameter_bounds(weights, slopes, weight_bounds, slope_upper_bound, *,
                              free_weight_indices=None, derived_weight_indices=None,
                              free_indices=None, derived_indices=None, atol=1e-4):
    """记录最终参数的边界命中；边界命中与优化阶段状态分别报告。"""
    if free_weight_indices is None:
        free_weight_indices = free_indices
    if derived_weight_indices is None:
        derived_weight_indices = derived_indices
    weights = np.asarray(weights, dtype=float).reshape(-1)
    slopes = np.asarray(slopes, dtype=float).reshape(-1)
    lower, upper = (float(value) for value in weight_bounds)
    configured_slope_bound = float(slope_upper_bound)
    max_abs_slope = float(np.max(np.abs(slopes))) if slopes.size else 0.0
    effective_slope_bound = max(configured_slope_bound, max_abs_slope)
    result = {
        'weights': {
            'configured_bounds': [lower, upper],
            'lower_bound_hits': int(np.isclose(weights, lower, rtol=0, atol=atol).sum()),
            'upper_bound_hits': int(np.isclose(weights, upper, rtol=0, atol=atol).sum()),
            'total': int(weights.size),
        },
        'slopes': {
            'configured_abs_upper_bound': configured_slope_bound,
            'effective_abs_upper_bound': effective_slope_bound,
            'configured_bound_exceedances': int((np.abs(slopes) > configured_slope_bound + atol).sum()),
            'effective_bound_hits': int(np.isclose(np.abs(slopes), effective_slope_bound, rtol=0, atol=atol).sum()),
            'total': int(slopes.size),
        },
    }
    if free_weight_indices is not None or derived_weight_indices is not None:
        free = np.asarray(free_weight_indices if free_weight_indices is not None else [], dtype=int)
        derived = np.asarray(derived_weight_indices if derived_weight_indices is not None else [], dtype=int)
        if (np.any(free < 0) or np.any(free >= weights.size)
                or np.any(derived < 0) or np.any(derived >= weights.size)):
            raise ValueError('coverage-aware weight diagnostics indices are out of range')
        free_values = weights[free]
        derived_values = weights[derived]
        free_lower = int(np.isclose(free_values, lower, rtol=0, atol=atol).sum())
        free_upper = int(np.isclose(free_values, upper, rtol=0, atol=atol).sum())
        derived_lower = int(np.isclose(derived_values, lower, rtol=0, atol=atol).sum())
        derived_upper = int(np.isclose(derived_values, upper, rtol=0, atol=atol).sum())
        result['weights'].update({
            'free_parameter_count': int(free.size),
            'derived_parameter_count': int(derived.size),
            'derived_lower_bound_hits': derived_lower,
            'derived_upper_bound_hits': derived_upper,
        })
        result['weights']['lower_bound_hits'] = free_lower
        result['weights']['upper_bound_hits'] = free_upper
        result['weights']['total'] = int(free.size)
        result['weights']['free'] = {
            'lower_bound_hits': free_lower, 'upper_bound_hits': free_upper,
            'total': int(free.size), 'indices': free.tolist(),
        }
        result['weights']['derived'] = {
            'lower_bound_hits': derived_lower, 'upper_bound_hits': derived_upper,
            'total': int(derived.size), 'indices': derived.tolist(),
        }
    return _native(result)


def diagnose_score_distribution(optim):
    """使用生产 _get_base/_get_scores/_alloc_mass 检查选档输入和空间边界。

对应静态运行的 magnitude_ratio=1.0；不使用补偿后的 magnitude、理想曲率
替换或 Kalman 输出。processed_Data 是每个定标状态的均值，因此统计反映
空间点/定标状态差异，不代表原始帧噪声或独立重复采集分布。
"""
    if not optim.soft:
        raise ValueError('task score 当前诊断 sigmoid 软分级，请设置 soft=True')
    report = {
        'basis': 'strain base magnitude before weights; magnitude_ratio=1.0',
        'sample_semantics': 'per-calibration-state mean strain, not independent raw frames',
        'thresholds': list(optim.thresholds), 'sharpness': optim.sharpness,
        'score_window': optim.min_consecutive, 'boundary_mode': 'constant',
        'score_mode': (
            'group_mean' if getattr(optim, 'end5cm_independent_weight_score', False)
            and getattr(optim, 'weight_group_ids', None) is not None else 'spatial_window'
        ),
        'weight_score_mode': (
            'group_mean' if getattr(optim, 'end5cm_independent_weight_score', False)
            and getattr(optim, 'weight_group_ids', None) is not None else 'spatial_window'
        ),
        'sigmoid_10_90_width_m_inv': float(2*np.log(9)/optim.sharpness) if optim.sharpness > 0 else None,
        'samples': [],
    }

    def leaves(data, path=()):
        """递归列出嵌套标定数据中的叶节点键路径。"""
        if isinstance(data, dict):
            for key, value in data.items():
                yield from leaves(value, path + (key,))
        else:
            yield path

    for shape in optim.calib_shapes:
        data = optim.processed_Data[shape][optim.direct]
        allowed = optim.radii[optim.direct][shape]
        for path in leaves(data):
            if path[0] not in allowed:
                continue
            if len(path) == 2 and path[1] not in allowed[path[0]]:
                continue
            _, magnitude, _, _ = optim._get_base(
                keys=list(path), calib_Data=data,
                base_slopes=optim.slopes[optim.direct][0], verbose=False,
            )
            magnitude = np.asarray(magnitude, dtype=float)
            if not np.all(np.isfinite(magnitude)):
                raise ValueError(f'{shape}/{path} 基础评分曲率包含非有限值')
            slope_scores = optim._get_scores(magnitude)
            slope_masses = optim._alloc_mass(slope_scores)
            if report['weight_score_mode'] == 'group_mean':
                weight_scores, group_base_magnitude = optim._get_groupwise_weight_scores(
                    magnitude, optim.weight_group_ids,
                )
                weight_masses = optim._alloc_mass(weight_scores)
            else:
                weight_scores, weight_masses = slope_scores, slope_masses
                group_base_magnitude = None
            theoretical = (0.0 if path[0] == 0 else 1000.0/path[0]) if shape in ('circ', 'S') else None
            report['samples'].append({
                'shape': shape, 'keys': list(path), 'direct': optim.direct,
                'theoretical_curvature_m_inv': theoretical,
                'global_point_ids': optim.global_point_ids.tolist(),
                'score_magnitude': magnitude.tolist(),
                'scores': slope_scores.tolist(), 'masses': slope_masses.tolist(),
                'slope_scores': slope_scores.tolist(), 'slope_masses': slope_masses.tolist(),
                'weight_scores': weight_scores.tolist(), 'weight_masses': weight_masses.tolist(),
                'group_base_magnitude': group_base_magnitude,
                'quantiles': dict(zip(('min', 'p10', 'median', 'p90', 'max'), np.quantile(magnitude, [0,.1,.5,.9,1]).tolist())),
                'mean_level_mass': weight_masses.mean(axis=1).tolist(),
                'tip_level_mass': weight_masses[:, -1].tolist(),
            })
    if not report['samples']:
        raise ValueError('没有可用于评分诊断的定标样本')
    if report['weight_score_mode'] == 'group_mean':
        bounds = optim.weight_bounds[0] if (
            isinstance(optim.weight_bounds, list) and len(optim.weight_bounds) == 1
        ) else optim.weight_bounds
        report['weight_coverage'] = compute_groupwise_weight_coverage(
            report['samples'], thresholds=optim.thresholds,
            weights=optim.weights[optim.direct], weight_bounds=bounds,
            group_ids=optim.weight_group_ids, mass_threshold=0.05,
        )
    return report


def summarize_score_runs(reports):
    """Combine score reports without replacing measured values by theory."""
    reports = sorted(reports, key=lambda report: report.get('direct', -1))
    directions = [report.get('direct') for report in reports]
    if directions != [0, 120, 240]:
        raise ValueError(f'score direct 必须恰好为 0、120、240；收到 {directions}')
    region_names = list(reports[0].get('regions', {}))
    summary = {'directions': directions, 'regions': {}}
    metadata_fields = (
        'basis', 'thresholds', 'sharpness', 'score_window',
        'boundary_mode', 'weight_score_mode', 'sigmoid_10_90_width_m_inv',
    )
    for region in region_names:
        distributions = []
        for report in reports:
            entry = report.get('regions', {}).get(region, {})
            if entry.get('status') != 'complete' or 'score_distribution' not in entry:
                raise ValueError(f'{report["direct"]}/{region} score 未完成')
            distributions.append(entry['score_distribution'])
        metadata = {name: deepcopy(distributions[0].get(name)) for name in metadata_fields}
        for distribution in distributions[1:]:
            for name in metadata_fields:
                if distribution.get(name) != metadata[name]:
                    raise ValueError(f'{region} 跨方向 score {name} 不一致')
        region_summary = {**metadata, 'directions': {}}
        for direct, distribution in zip(directions, distributions):
            rows = []
            for measured in distribution['samples']:
                keys = measured.get('keys', [])
                radius = keys[0] if keys else None
                rows.append({
                    'shape': measured.get('shape'),
                    'keys': deepcopy(keys),
                    'radius_mm': radius,
                    'theoretical_curvature_m_inv': measured.get('theoretical_curvature_m_inv'),
                    'global_point_ids': deepcopy(measured.get('global_point_ids')),
                    'score_magnitude': deepcopy(measured.get('score_magnitude')),
                    'quantiles': deepcopy(measured.get('quantiles')),
                    'mean_level_mass': deepcopy(measured.get('mean_level_mass')),
                    'tip_level_mass': deepcopy(measured.get('tip_level_mass')),
                })
            high = sorted(
                (row for row in rows if row['shape'] == 'circ'
                 and isinstance(row['radius_mm'], (int, float))
                 and 0 < row['radius_mm'] <= 30),
                key=lambda row: row['radius_mm'], reverse=True,
            )
            dominant = [int(np.argmax(row['mean_level_mass'])) for row in high]
            separable = len(high) < 2 or all(
                left != right for left, right in zip(dominant, dominant[1:])
            )
            region_summary['directions'][str(direct)] = {
                'samples': rows,
                'high_curvature_radii_mm': [row['radius_mm'] for row in high],
                'dominant_levels': dominant,
                'high_curvature_separable': separable,
            }
        summary['regions'][region] = region_summary
    return _native(summary)


def _plot_scores(report, path):
    """将实测基础曲率和各等级平均权重保存为无界面的诊断图。"""
    # 科学图独立保存，避免初始化 GUI 或阻塞批量任务。
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(12, 6), tight_layout=True)
    FigureCanvasAgg(fig)
    ax, bx = fig.subplots(1, 2)
    for index, sample in enumerate(report['samples']):
        values = sample['score_magnitude']
        ax.scatter([index]*len(values), values, s=12)
    for threshold in report['thresholds']:
        ax.axhline(threshold, color='gray', linestyle='--', linewidth=.6)
    labels = [str(sample['keys']) for sample in report['samples']]
    ax.set(xticks=range(len(labels)), xticklabels=labels, xlabel='Calibration keys (radius in mm)', ylabel='Base curvature (1/m)')
    ax.tick_params(axis='x', rotation=90)
    means = np.array([sample['mean_level_mass'] for sample in report['samples']])
    bottom = np.zeros(len(means))
    for level in range(means.shape[1]):
        bx.bar(range(len(means)), means[:, level], bottom=bottom, label=f'level {level}')
        bottom += means[:, level]
    bx.set(xticks=range(len(labels)), xticklabels=labels, ylim=(0,1), ylabel='Mean actual level mass')
    bx.tick_params(axis='x', rotation=90)
    bx.legend(fontsize='small')
    fig.savefig(path, dpi=150)


def run_calibration_jobs(jobs, optimizer_factory, *, output_root):
    """逐区域执行并立即落盘。异常时保留已完成项并标记失败项，然后停止。

每次启动使用独立目录，防止覆盖另一方向的定标结果。导出的参数只标记
本次 --direct 为已优化，不把其他方向的初始化值冒充最优参数。
"""
    first = jobs[0][0]
    sensor = re.sub(r'[^\w.-]+', '_', first.sensor_id).strip('.') or 'sensor'
    run_id = (datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z')
              + f'-direct{first.direct}-' + uuid4().hex[:6])
    output = Path(output_root) / f'{sensor}-{run_id}'
    output.mkdir(parents=True, exist_ok=False)
    report = {'sensor_id': first.sensor_id, 'task': first.task, 'direct': first.direct,
              'regions': {args.optimization_region: {'status': 'pending'} for args, _ in jobs}}
    print(f'区域结果目录: {output}')
    completed_optimizers = {}
    for index, (args, context) in enumerate(jobs):
        region = args.optimization_region
        entry = report['regions'][region]
        configuration = {key: value for key, value in vars(args).items()
                         if key != '_phase_source_jobs'}
        configuration['folder_path'] = _report_relative_folder(
            configuration.get('folder_path'), args.calibration_data_root,
        )
        stored_context = deepcopy(context)
        stored_context['folder_path'] = _report_relative_folder(
            stored_context.get('folder_path'), args.calibration_data_root,
        )
        entry.update(configuration=_native(configuration), context=_native(stored_context), status='running')
        _save_report(output / 'results.json', report)
        try:
            print(f'========== {index+1}/{len(jobs)} 区域: {region}; 方向: {args.direct} ==========')
            reference = None
            if args.task == 'optim' and region != 'full' and getattr(args, 'use_full_transported_phase', False):
                from calibration_phase_reference import build_assembled_phase_references
                full = completed_optimizers.get('full')
                if full is None:
                    source_args, _ = args._phase_source_jobs['full']
                    if source_args.weights is None or source_args.slopes is None:
                        raise ValueError('来源参数包缺少full已优化weights/slopes')
                    full = optimizer_factory(**optimizer_parameters(source_args))
                upstream = full
                if region == 'end5cm':
                    upstream = completed_optimizers.get('end15cm')
                    if upstream is None:
                        source_args, source_context = args._phase_source_jobs['end15cm']
                        if source_args.weights is None or source_args.slopes is None:
                            raise ValueError('来源参数包缺少end15cm已优化weights/slopes')
                        saved = args._sensor_package['regions']['end15cm'].get(
                            'phase_reference', {}).get(str(args.direct))
                        if not saved:
                            raise ValueError('独立end5cm固定相位优化需要先导出同方向固定相位end15cm结果')
                        source_args.global_phases_set = saved['phase_at_first_point_rad']
                        upstream = optimizer_factory(**optimizer_parameters(source_args))
                reference = build_assembled_phase_references(full, upstream, context, args.direct)
                reference['source_kind'] = ('current_batch' if upstream in completed_optimizers.values()
                                            else 'sensor_package')
                reference['source_sensor_params'] = getattr(args, 'sensor_params', None)
                args.global_phases_set = reference['phase_at_first_point_rad']
                entry['configuration']['global_phases_set'] = args.global_phases_set
            optim = optimizer_factory(**optimizer_parameters(args))
            optim.phase_reference = reference
            optim.calibration_context = context
            if reference is not None:
                optim.assembled_phase_context = (full, upstream)
            if args.task in ('optim', 'score'):
                validator = getattr(optim, 'validate_calibration_data_radii', None)
                if validator is not None:
                    validator()
            if args.task == 'score':
                entry['score_distribution'] = diagnose_score_distribution(optim)
                _plot_scores(entry['score_distribution'], output / f'score-{index+1}.png')
            else:
                stages = optim.optim_coeff(verbose=True)
                entry.update(collect_calibration_result(optim, stages))
            completed_optimizers[region] = optim
            entry['status'] = 'complete'
        except Exception as exc:
            entry.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            _save_report(output / 'results.json', report)
            print(f'{region} 失败，已完成区域结果保留在 {output}')
            raise
        _save_report(output / 'results.json', report)
        completed = {key: value['parameters'] for key, value in report['regions'].items()
                     if value['status'] == 'complete' and 'parameters' in value}
        (output / 'parameters.py').write_text(
            '# 仅包含本次 direct 的优化结果；其他方向需分别运行并补齐。\n'
            '# 以下区域相位仍是各自局部参考，不能直接当作全段部署参数包。\n'
            'region_parameters = ' + pprint.pformat(completed, width=110, sort_dicts=False) + '\n',
            encoding='utf-8',
        )
    print('========== 区域汇总 ==========')
    for region, entry in report['regions'].items():
        if 'parameters' in entry:
            print(region, 'weights=', entry['parameters']['weights'], 'slopes=', entry['parameters']['slopes'])
            print('正常重构误差:', entry['errors'])
        else:
            print(region, '评分样本数:', len(entry['score_distribution']['samples']))
    return output, report
