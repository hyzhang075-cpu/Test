"""Offline full-geometry validation for a merged multi-region package."""

from copy import deepcopy
import json
from pathlib import Path
import sys

# 直接执行tools脚本时也从项目根目录导入主程序和其他模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, "") and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np


REGION_ORDER = ('full', 'end15cm', 'end5cm')
DEFAULT_VALIDATION_POLICY = {
    'full_mean_error_percent_max': 1.0,
    'full_regression_percentage_points_max': 0.2,
    'tail_improvement_percent_min': 10.0,
    'tip_position_percent_max': 1.0,
    'tip_tangent_error_deg_max': 10.0,
    'boundary_curvature_angle_jump_deg_max': 30.0,
    'end15cm_phase_error_deg_max': 30.0,
}


def circular_angle_error_deg(actual, expected):
    """Smallest absolute angular difference between two radian phases."""
    delta = float(actual) - float(expected)
    return float(abs(np.degrees(np.arctan2(np.sin(delta), np.cos(delta)))))


def integrate_phase_to_point(global_phase, distances, slope_map, point_index):
    """Reproduce Initialiser's discrete twist integration through one point."""
    distances = np.asarray(distances, dtype=float)
    slope_map = np.asarray(slope_map, dtype=float)
    point_index = int(point_index)
    if distances.ndim != 1 or slope_map.shape != distances.shape:
        raise ValueError('distances 和 slope_map 必须是相同长度的一维数组')
    if point_index < 0 or point_index >= len(distances):
        raise ValueError(f'point_index 越界: {point_index}')
    if not np.all(np.isfinite(distances)) or not np.all(np.isfinite(slope_map)):
        raise ValueError('phase transport 输入必须为有限数值')
    increments = slope_map[1:point_index + 1] * np.diff(distances[:point_index + 1])
    return float(global_phase + np.sum(increments))


def build_phase_transport_evidence(global_phase, distances, slope_map,
                                   local_phases, start_indices, *, tolerance_deg=30.0):
    """Compare transported full phase with regional local phase references."""
    result = {}
    for region in ('end15cm', 'end5cm'):
        predicted = integrate_phase_to_point(
            global_phase, distances, slope_map, start_indices[region],
        )
        local = float(local_phases[region])
        error = circular_angle_error_deg(predicted, local)
        result[region] = {
            'predicted_phase_rad': predicted,
            'local_phase_rad': local,
            'phase_error_deg': error,
            'tolerance_deg': float(tolerance_deg),
            'within_30_deg': bool(error <= tolerance_deg),
            'blocking': region == 'end15cm',
        }
    return result


def validate_score_evidence(package, score_report, source_path):
    """Validate one shared score report against regional package thresholds."""
    failures = []
    if score_report.get('sensor_id') != package.get('sensor_id'):
        failures.append(
            f'sensor_id 不一致: {score_report.get("sensor_id")} != {package.get("sensor_id")}'
        )
    if score_report.get('task') != 'score':
        failures.append(f'task 必须为 score，收到 {score_report.get("task")}')
    report_regions = score_report.get('regions', {})
    summaries = {}
    for region in REGION_ORDER:
        entry = report_regions.get(region)
        if not isinstance(entry, dict):
            failures.append(f'score 缺少区域 {region}')
            continue
        if entry.get('status') != 'complete':
            failures.append(f'{region} score 未完成')
        distribution = entry.get('score_distribution', {})
        expected = [float(v) for v in package.get('regions', {}).get(region, {}).get('thresholds', [])]
        actual = [float(v) for v in distribution.get('thresholds', [])]
        if actual != expected:
            failures.append(f'{region} thresholds 不一致: {actual} != {expected}')
        width = distribution.get('sigmoid_10_90_width_m_inv')
        samples = distribution.get('samples', [])
        values = []
        sample_summaries = []
        for sample in samples:
            magnitude = np.asarray(sample.get('score_magnitude', []), dtype=float)
            if magnitude.size:
                values.extend(magnitude.tolist())
            sample_summaries.append({
                'keys': deepcopy(sample.get('keys')),
                'theoretical_curvature_m_inv': sample.get('theoretical_curvature_m_inv'),
                'quantiles': deepcopy(sample.get('quantiles', {})),
            })
        numeric = np.asarray(values, dtype=float)
        if width is None or not np.isfinite(float(width)) or numeric.size == 0 or not np.all(np.isfinite(numeric)):
            failures.append(f'{region} score 包含非有限数值或空分布')
            observed_min = observed_max = None
        else:
            observed_min = float(np.min(numeric))
            observed_max = float(np.max(numeric))
            for threshold in expected:
                if not observed_min <= threshold <= observed_max:
                    failures.append(
                        f'{region} threshold {threshold} m^-1 未被实测分布跨越 '
                        f'[{observed_min}, {observed_max}]'
                    )
        summaries[region] = {
            'thresholds': actual,
            'sigmoid_10_90_width_m_inv': width,
            'observed_min_m_inv': observed_min,
            'observed_max_m_inv': observed_max,
            'samples': sample_summaries,
        }
    return {
        'score_thresholds_verified': not failures,
        'source_path': str(source_path),
        'source_direct': score_report.get('direct'),
        'regions': summaries,
        'failures': failures,
    }


def _unit(vector):
    """返回三维向量的单位方向；拒绝零向量和非有限输入。"""
    vector = np.asarray(vector, dtype=float)
    norm = np.linalg.norm(vector)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError('tangent vector must be finite and nonzero')
    return vector / norm


def compute_curve_metrics(result, ideal, *, result_tangent, ideal_tangent,
                          distances=None, evaluation_start_m=None,
                          full_length_m=None):
    """计算曲线点位、末端位置和末端切向误差。

    坐标输入使用 m；输出同时保留 mm，并以完整传感器长度为分母给出百分比。
    ``evaluation_start_m`` 用于单独统计末端区域，但百分比仍相对全长。
    """
    result = np.asarray(result, dtype=float)
    ideal = np.asarray(ideal, dtype=float)
    if result.shape != ideal.shape or result.ndim != 2 or result.shape[1] != 3:
        raise ValueError(f'curve shapes must match as (points, 3): {result.shape}, {ideal.shape}')
    errors = np.linalg.norm(result - ideal, axis=1)
    result_tangent = _unit(result_tangent)
    ideal_tangent = _unit(ideal_tangent)
    tangent_rad = float(np.arccos(np.clip(np.dot(result_tangent, ideal_tangent), -1.0, 1.0)))
    tip_mm = float(errors[-1] * 1000)
    length_m = max(float(np.sum(np.linalg.norm(np.diff(ideal, axis=0), axis=1))), 1e-12)
    denominator_m = float(full_length_m) if full_length_m is not None else length_m
    if not np.isfinite(denominator_m) or denominator_m <= 0:
        raise ValueError('full_length_m 必须为正的有限值')
    metrics = {
        'mean_point_error_mm': float(np.mean(errors) * 1000),
        'max_point_error_mm': float(np.max(errors) * 1000),
        'tip_position_error_mm': tip_mm,
        'mean_point_error_percent_full_length': float(np.mean(errors) / denominator_m * 100),
        'max_point_error_percent_full_length': float(np.max(errors) / denominator_m * 100),
        'tip_position_error_percent_full_length': float(errors[-1] / denominator_m * 100),
        'tip_tangent_error_deg': float(np.degrees(tangent_rad)),
        'pose_error_mm': float(np.hypot(tip_mm, 1000 * length_m * tangent_rad)),
    }
    if distances is not None and evaluation_start_m is not None:
        mask = np.asarray(distances, dtype=float) >= float(evaluation_start_m) - 1e-12
        metrics['evaluated_region_point_error_mm'] = float(np.mean(errors[mask]) * 1000)
        metrics['evaluated_region_point_error_percent_full_length'] = float(
            np.mean(errors[mask]) / denominator_m * 100
        )
    return metrics


def evaluate_direction_gates(direction_report, optimization_usable,
                             score_verified, policy=None):
    """Apply explicit replay limits to one literal calibration direction."""
    policy = dict(DEFAULT_VALIDATION_POLICY if policy is None else policy)
    failures = []
    replay = direction_report.get('replay', {})
    for radius, row in replay.get('full', {}).items():
        baseline = row['baseline']['mean_point_error_percent_full_length']
        candidate = row['candidate']['mean_point_error_percent_full_length']
        if candidate > policy['full_mean_error_percent_max']:
            failures.append(f'full mean point error at radius {radius} is {candidate:.6g}%')
        regression = candidate - baseline
        if regression > policy['full_regression_percentage_points_max']:
            failures.append(f'full regression at radius {radius} is {regression:.6g} percentage points')
    for radius in ('30', '20', '15'):
        row = replay.get('end5cm', {}).get(radius)
        if row is None:
            failures.append(f'tail improvement missing for radius {radius}')
        elif row.get('tail_improvement_percent', float('-inf')) < policy['tail_improvement_percent_min']:
            failures.append(
                f'tail improvement at radius {radius} is '
                f'{row.get("tail_improvement_percent", float("nan")):.6g}%'
            )
    for region, rows in replay.items():
        for radius, row in rows.items():
            metrics = row['candidate']
            tip = metrics['tip_position_error_percent_full_length']
            tangent = metrics['tip_tangent_error_deg']
            if tip > policy['tip_position_percent_max']:
                failures.append(f'tip position at {region}/{radius} is {tip:.6g}%')
            if tangent > policy['tip_tangent_error_deg_max']:
                failures.append(f'tip tangent at {region}/{radius} is {tangent:.6g} deg')
    boundary = direction_report.get('max_boundary_curvature_angle_jump_deg', float('inf'))
    if boundary > policy['boundary_curvature_angle_jump_deg_max']:
        failures.append(f'boundary curvature angle jump is {boundary:.6g} deg')
    phase = direction_report.get('phase_transport', {}).get('end15cm', {})
    phase_ok = bool(phase.get('within_30_deg', False))
    if not phase_ok:
        failures.append(
            f'end15cm phase error is {phase.get("max_phase_error_deg", float("nan")):.6g} deg'
        )
    geometry_failures = [failure for failure in failures if not failure.startswith('end15cm phase')]
    gates = {
        'optimization_usable': bool(optimization_usable),
        'end15cm_phase_verified': phase_ok,
        'full_geometry_verified': not geometry_failures,
    }
    if not optimization_usable:
        failures.insert(0, 'optimization stages are not usable')
    if not score_verified:
        failures.insert(0, 'shared score thresholds are not verified')
    return {
        'deployment_ready': bool(score_verified and all(gates.values())),
        'quality_gates': gates,
        'failures': failures,
    }


def straight_prefix_circular_tail(distances, bend_start_m, radius_m):
    """生成直线前段加圆弧末段的理想曲线及末端单位切向量，长度单位为 m。"""
    distances = np.asarray(distances, dtype=float)
    if radius_m <= 0:
        curve = np.column_stack((distances, np.zeros((len(distances), 2))))
        return curve, np.array([1.0, 0.0, 0.0])
    curve = np.zeros((len(distances), 3), dtype=float)
    before = distances <= bend_start_m
    curve[before, 0] = distances[before]
    arc = np.maximum(0.0, distances[~before] - bend_start_m)
    curve[~before, 0] = bend_start_m + radius_m * np.sin(arc / radius_m)
    curve[~before, 1] = radius_m * (1.0 - np.cos(arc / radius_m))
    tip_arc = max(0.0, float(distances[-1] - bend_start_m))
    tangent = np.array([np.cos(tip_arc / radius_m), np.sin(tip_arc / radius_m), 0.0])
    return curve, tangent


def boundary_diagnostics(diagnostics, left_point_ids=(15, 18)):
    """计算指定相邻全局点之间的权重、slope、相位和曲率跳变。"""
    weights = np.asarray(diagnostics['final_weight'], dtype=float)
    slopes = np.asarray(diagnostics['slope_map'], dtype=float)
    base = np.asarray(diagnostics['base_magnitude'], dtype=float)
    magnitude = np.asarray(diagnostics['final_magnitude'], dtype=float)
    angle = np.asarray(diagnostics['final_angle'], dtype=float)
    theta = np.asarray(diagnostics['final_theta_dynamic'], dtype=float)
    vectors = magnitude[:, None] * np.column_stack((np.cos(angle), np.sin(angle)))
    result = {}
    for left_id in left_point_ids:
        left = int(left_id) - 1
        right = left + 1
        if right >= len(weights):
            raise ValueError(f'boundary {left_id}->{left_id + 1} is outside point arrays')
        result[f'{left_id}->{left_id + 1}'] = {
            'weight_jump': float(abs(weights[right] - weights[left])),
            'slope_jump': float(abs(slopes[right] - slopes[left])),
            'base_curvature_jump_m_inv': float(abs(base[right] - base[left])),
            'phase_jump_rad': float(np.max(np.abs(theta[:, right] - theta[:, left]))),
            'curvature_angle_jump_deg': circular_angle_error_deg(angle[right], angle[left]),
            'curvature_vector_jump_m_inv': float(np.linalg.norm(vectors[right] - vectors[left])),
        }
    return result


def add_tangent_boundary_diagnostics(boundaries, interp_dist, tangents,
                                     boundary_distances):
    """在区域边界最近的插值位置补充切向增量夹角，角度单位为 deg。"""
    interp_dist = np.asarray(interp_dist, dtype=float)
    tangents = np.asarray(tangents, dtype=float)
    for key, boundary_distance in boundary_distances.items():
        index = int(np.argmin(np.abs(interp_dist - float(boundary_distance))))
        index = min(max(index, 1), len(tangents) - 2)
        left = _unit(tangents[index] - tangents[index - 1])
        right = _unit(tangents[index + 1] - tangents[index])
        boundaries[key]['tangent_increment_jump_deg'] = float(
            np.degrees(np.arccos(np.clip(np.dot(left, right), -1.0, 1.0)))
        )
    return boundaries


def validation_failure_summary(report):
    """汇总旧格式回放报告中的最大误差，供失败信息和人工检查使用。"""
    full_errors = []
    tail_tangent_errors = []
    phase_jumps = []
    for regions in report['directions'].values():
        for region, radii in regions.items():
            for values in radii.values():
                if region == 'full':
                    full_errors.append(values['mean_point_error_mm'])
                else:
                    tail_tangent_errors.append(values['tip_tangent_error_deg'])
                phase_jumps.extend(
                    boundary['phase_jump_rad'] for boundary in values['boundaries'].values()
                )
    return (
        f'max full mean point error={max(full_errors):.3f} mm; '
        f'max local-test tip tangent error={max(tail_tangent_errors):.3f} deg; '
        f'max region-boundary phase jump={max(phase_jumps):.3f} rad; '
        'source optimization gates include divergence and independent pose ground truth is unavailable'
    )


def _ideal_full_circular(distances, radius_m):
    """生成从传感器起点开始弯曲的完整理想圆弧。"""
    return straight_prefix_circular_tail(distances, 0.0, radius_m)


def _reconstruct_frame(full, frame, direct):
    """按指定 0/120/240 方向重构一帧，并统一旋转到误差评估坐标系。"""
    result = full._reconstruct_frame(
        keys=None, calib_shape='circ', calib_Data=frame,
        weight=full.weights[direct], slope=full.slopes[direct],
        magnitude_ratio=1.0, init_T=[1.0, 0.0, 0.0], direct=direct,
        verbose=False,
    )
    _, _, _, interp_dist, curve, tangent, *_ = result
    rot_direction = full.rot_dir[full.calib_shapes.index('circ')]
    rotation = full._get_rot_x(direct=direct, rot_dir=rot_direction)
    diagnostics = deepcopy(getattr(full, 'last_parameter_assembly', None))
    return (np.asarray(interp_dist), curve @ rotation.T, tangent @ rotation.T,
            diagnostics)


def _full_region_slope_map(full, frame, direct):
    """Calculate the full profile's score-blended pointwise slopes."""
    base_slopes = np.asarray(full.slopes[direct][0], dtype=float)
    _, magnitude, _, _ = full._get_base(
        keys=None, calib_Data=frame, base_slopes=base_slopes, verbose=False,
    )
    scores = full._get_scores(magnitude=np.asarray(magnitude, dtype=float))
    masses = full._alloc_mass(scores)
    labels = np.empty(full.total_points, dtype=int)
    for segment, (start, end) in enumerate(full.base_segments):
        labels[start:end] = segment
    slope_vectors = np.asarray(full.slopes[direct], dtype=float)[:, labels]
    return np.sum(masses * slope_vectors, axis=0)


def _tail_improvement_percent(baseline, candidate):
    """计算 multi-region 相对 full 基线的末端平均误差改善百分比。"""
    baseline = float(baseline)
    candidate = float(candidate)
    if baseline <= 0:
        return 0.0 if candidate >= baseline else 100.0
    return float((baseline - candidate) / baseline * 100)


def validate_multiregion_package(package_path, score_results, policy=None):
    """Replay full and local experiments through one 22-point reconstruction."""
    import main
    from calibration_batch import optimizer_parameters
    from optimiser import Optimiser
    from tools.sensor_parameter_package import _project_relative_path

    package_path = str(Path(package_path).resolve())
    package = json.loads(Path(package_path).read_text(encoding='utf-8'))
    score_path = Path(score_results)
    if score_path.is_dir():
        score_path = score_path / 'results.json'
    score_report = json.loads(score_path.read_text(encoding='utf-8'))
    score_evidence = validate_score_evidence(
        package, score_report, _project_relative_path(score_path),
    )
    policy = dict(DEFAULT_VALIDATION_POLICY if policy is None else policy)

    def make(region, merged=False):
        """构造单区域基线或完整多区域回放所需的 Optimiser。"""
        argv = ['--task', 'recon', '--sensor_params', package_path,
                '--optimization_region', region,
                '--exp_directs', '[0,120,240]',
                '--multi_region_calib', 'True' if merged else 'False']
        args = main.parse_main_args(argv)
        # Mirror main(): stored 22-point dynamic zero references are invalid for
        # cropped 7/4-point offline calibration readers.
        args.use_stored_zero = False
        context = main.configure_calibration_args(args)
        optim = Optimiser(**optimizer_parameters(args))
        optim.calibration_context = context
        return optim

    full = make('full', merged=True)
    full_only = make('full', merged=False)
    local = {'end15cm': make('end15cm'), 'end5cm': make('end5cm')}
    report = {
        'basis': 'full 22-point reconstruction with region-owned point parameters',
        'global_phases_set': full.global_phases_set,
        'rot_ang': full.rot_ang,
        'full_length_m': float(full.ideal_len),
        'validation_policy': policy,
        'shared_quality_gates': {
            'score_thresholds_verified': score_evidence['score_thresholds_verified'],
        },
        'score_evidence': score_evidence,
        'directions': {},
    }
    plan = {
        'full': [2000, 1500, 1000, 800, 600, 400, 300, 200],
        'end15cm': [100, 75, 50, 30],
        'end5cm': [30, 20, 15],
    }
    point_index = {int(point): index for index, point in enumerate(full.global_point_ids)}
    global_sample_dist = np.asarray(
        package['regions']['full']['global_sample_dist_m'], dtype=float,
    )
    local_phases = package.get('provenance', {}).get('local_global_phases_set', {})
    start_indices = {
        region: point_index[int(package['regions'][region]['support_point_ids'][0])]
        for region in ('end15cm', 'end5cm')
    }
    boundary_distances = {
        '15->16': float(global_sample_dist[15]),
        '18->19': float(global_sample_dist[18]),
    }
    for direct in (0, 120, 240):
        direction = {'replay': {}, 'phase_transport_samples': {'end15cm': {}, 'end5cm': {}}}
        straight = np.asarray(full.processed_Data['circ'][direct][0]).copy()
        for region, radii in plan.items():
            rows = {}
            for radius in radii:
                if region == 'full':
                    frame = np.asarray(full.processed_Data['circ'][direct][radius])
                    bend_start = 0.0
                else:
                    source = local[region]
                    frame = straight.copy()
                    local_frame = np.asarray(source.processed_Data['circ'][direct][radius])
                    ids = source.global_point_ids.tolist()
                    indices = [point_index[int(point)] for point in ids]
                    frame[indices] = local_frame
                    bend_start = full.ideal_len - (0.15 if region == 'end15cm' else 0.05)
                base_dist, base_curve, base_tangent, _ = _reconstruct_frame(
                    full_only, frame, direct,
                )
                interp_dist, curve, tangent, diagnostics = _reconstruct_frame(full, frame, direct)
                ideal, ideal_tangent = straight_prefix_circular_tail(
                    interp_dist - interp_dist[0], bend_start,
                    0.0 if radius == 0 else radius / 1000.0,
                )
                candidate_metrics = compute_curve_metrics(
                    curve, ideal, result_tangent=tangent[-1], ideal_tangent=ideal_tangent,
                    distances=interp_dist - interp_dist[0], evaluation_start_m=bend_start,
                    full_length_m=full.ideal_len,
                )
                baseline_metrics = compute_curve_metrics(
                    base_curve, ideal, result_tangent=base_tangent[-1], ideal_tangent=ideal_tangent,
                    distances=base_dist - base_dist[0], evaluation_start_m=bend_start,
                    full_length_m=full.ideal_len,
                )
                boundaries = boundary_diagnostics(diagnostics)
                try:
                    add_tangent_boundary_diagnostics(
                        boundaries, interp_dist, tangent, boundary_distances,
                    )
                except ValueError:
                    for values in boundaries.values():
                        values['tangent_increment_jump_deg'] = None
                candidate_metrics['boundaries'] = boundaries
                baseline_tail = baseline_metrics.get(
                    'evaluated_region_point_error_percent_full_length',
                    baseline_metrics['mean_point_error_percent_full_length'],
                )
                candidate_tail = candidate_metrics.get(
                    'evaluated_region_point_error_percent_full_length',
                    candidate_metrics['mean_point_error_percent_full_length'],
                )
                rows[str(radius)] = {
                    'baseline': baseline_metrics,
                    'candidate': candidate_metrics,
                    'tail_improvement_percent': _tail_improvement_percent(
                        baseline_tail, candidate_tail,
                    ),
                }
                if region in ('end15cm', 'end5cm'):
                    slope_map = _full_region_slope_map(full_only, frame, direct)
                    # 新模式验证实际装配后的上游相位：包含end15cm内部slope和full第0档跨界。
                    if diagnostics.get('fixed_full_level0_bridges', False):
                        slope_map = np.asarray(diagnostics['slope_map'], dtype=float)
                    phases = {
                        name: local_phases[name][str(direct)]
                        for name in ('end15cm', 'end5cm')
                    }
                    if diagnostics.get('fixed_full_level0_bridges', False):
                        phases = {
                            name: package['regions'][name]['phase_reference'][str(direct)][
                                'phase_at_first_point_rad']
                            for name in ('end15cm', 'end5cm')
                        }
                    phase_values = build_phase_transport_evidence(
                        full.global_phases_set, global_sample_dist,
                        slope_map, phases, start_indices,
                        tolerance_deg=policy['end15cm_phase_error_deg_max'],
                    )
                    direction['phase_transport_samples'][region][str(radius)] = phase_values[region]
            direction['replay'][region] = rows
        phase_summary = {}
        for region in ('end15cm', 'end5cm'):
            samples = direction['phase_transport_samples'][region]
            maximum = max(value['phase_error_deg'] for value in samples.values())
            phase_summary[region] = {
                'blocking': region == 'end15cm',
                'max_phase_error_deg': maximum,
                'tolerance_deg': policy['end15cm_phase_error_deg_max'],
                'within_30_deg': bool(maximum <= policy['end15cm_phase_error_deg_max']),
                'samples': samples,
            }
        direction['phase_transport'] = phase_summary
        boundary_angles = [
            boundary['curvature_angle_jump_deg']
            for rows in direction['replay'].values()
            for row in rows.values()
            for boundary in row['candidate']['boundaries'].values()
            if np.isfinite(boundary['curvature_angle_jump_deg'])
        ]
        direction['max_boundary_curvature_angle_jump_deg'] = max(boundary_angles)
        optimization_usable = package['multi_region']['direction_deployment'][str(direct)][
            'quality_gates'
        ]['optimization_usable']
        decision = evaluate_direction_gates(
            direction, optimization_usable,
            score_evidence['score_thresholds_verified'], policy,
        )
        direction.update(decision)
        direction['full_geometry'] = {
            'replay': direction['replay'],
            'max_boundary_curvature_angle_jump_deg': direction[
                'max_boundary_curvature_angle_jump_deg'
            ],
        }
        report['directions'][str(direct)] = direction
    return report


def write_validation_report(report, json_path, markdown_path):
    """原子写入机器可读 JSON 和便于人工复核的 Markdown 验证报告。"""
    json_path = Path(json_path)
    markdown_path = Path(markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_temporary = json_path.with_suffix(json_path.suffix + '.tmp')
    json_temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        encoding='utf-8',
    )
    json_temporary.replace(json_path)
    lines = [
        '# Multi-region full-geometry validation', '',
        f'- unified global phase: `{report["global_phases_set"]}`',
        f'- unified rot_ang: `{report["rot_ang"]}`',
        f'- shared score thresholds verified: `{report["shared_quality_gates"]["score_thresholds_verified"]}`',
        '', '## Direction gates', '',
        '| direct | deployable | optimization | end15 phase | full geometry | failures |',
        '|---:|---:|---:|---:|---:|---|',
    ]
    for direct, direction in report['directions'].items():
        gates = direction['quality_gates']
        lines.append(
            f'| {direct} | {direction["deployment_ready"]} | '
            f'{gates["optimization_usable"]} | {gates["end15cm_phase_verified"]} | '
            f'{gates["full_geometry_verified"]} | '
            f'{"; ".join(direction.get("failures", []))} |'
        )
    lines.extend([
        '', '## Phase transport', '',
        '| direct | region | maximum error (deg) | tolerance (deg) | pass | blocking |',
        '|---:|---|---:|---:|---:|---:|',
    ])
    for direct, direction in report['directions'].items():
        for region, phase in direction['phase_transport'].items():
            lines.append(
                f'| {direct} | {region} | {phase["max_phase_error_deg"]:.3f} | '
                f'{phase["tolerance_deg"]:.3f} | {phase["within_30_deg"]} | '
                f'{phase["blocking"]} |'
            )
    lines.extend([
        '', '## Reconstruction replay', '',
        '| direct | region | radius (mm) | baseline tail (% full) | candidate tail (% full) | improvement (%) | tip position (mm) | tip position (% full) | tip tangent (deg) |',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|',
    ])
    for direct, direction in report['directions'].items():
        for region, radii in direction['replay'].items():
            for radius, row in radii.items():
                baseline = row['baseline']
                candidate = row['candidate']
                baseline_tail = baseline.get(
                    'evaluated_region_point_error_percent_full_length',
                    baseline['mean_point_error_percent_full_length'],
                )
                candidate_tail = candidate.get(
                    'evaluated_region_point_error_percent_full_length',
                    candidate['mean_point_error_percent_full_length'],
                )
                lines.append(
                    f'| {direct} | {region} | {radius} | '
                    f'{baseline_tail:.3f} | {candidate_tail:.3f} | '
                    f'{row["tail_improvement_percent"]:.3f} | '
                    f'{candidate["tip_position_error_mm"]:.3f} | '
                    f'{candidate["tip_position_error_percent_full_length"]:.3f} | '
                    f'{candidate["tip_tangent_error_deg"]:.3f} |'
                )
    lines.extend(['', '## Shared score evidence', '',
                  f'- source: `{report["score_evidence"]["source_path"]}`',
                  f'- failures: `{json.dumps(report["score_evidence"]["failures"], ensure_ascii=False)}`', ''])
    markdown_temporary = markdown_path.with_suffix(markdown_path.suffix + '.tmp')
    markdown_temporary.write_text('\n'.join(lines), encoding='utf-8')
    markdown_temporary.replace(markdown_path)


def main(argv=None):
    """运行全长定标回放验证，并输出带逐方向部署状态的新参数包。"""
    import argparse

    cli = argparse.ArgumentParser(description='Replay a multi-region package on full geometry')
    cli.add_argument('--sensor-params', required=True)
    cli.add_argument('--score-results', required=True)
    cli.add_argument('--json-output', default='docs/calibration-multiregion-validation.json')
    cli.add_argument('--markdown-output', default='docs/calibration-multiregion-validation.md')
    cli.add_argument('--package-output', required=True)
    for name, default in DEFAULT_VALIDATION_POLICY.items():
        cli.add_argument('--' + name.replace('_', '-'), type=float, default=default)
    args = cli.parse_args(argv)
    policy = {name: getattr(args, name) for name in DEFAULT_VALIDATION_POLICY}
    report = validate_multiregion_package(
        args.sensor_params, args.score_results, policy=policy,
    )
    write_validation_report(report, args.json_output, args.markdown_output)
    from tools.sensor_parameter_package import (
        apply_validation_results, load_sensor_package, write_sensor_package,
    )
    package = load_sensor_package(args.sensor_params)
    validated = apply_validation_results(package, report)
    write_sensor_package(validated, args.package_output)
    return report, validated


if __name__ == '__main__':
    main()
