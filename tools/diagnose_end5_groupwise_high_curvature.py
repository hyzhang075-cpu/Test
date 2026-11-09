"""Read-only diagnosis of high-curvature end5cm weight support and replay behavior."""

import argparse
import json
import pickle
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.replay_end5cm_groupwise import (
    _make_reconstructor,
    curvature_tail_metrics,
)
from tools.sensor_parameter_package import load_sensor_package


def _static_analysis(package, score_path):
    score_report = json.loads(Path(score_path).read_text(encoding='utf-8'))
    entry = score_report['regions']['end5cm']
    block = package['regions']['end5cm']
    distribution = entry['score_distribution']
    thresholds = np.asarray(block['thresholds'], dtype=float)
    sharpness = float(block['sharpness'])
    width = float(2.0 * np.log(9.0) / sharpness)
    weights = np.asarray(block['weights']['0'], dtype=float).reshape(3, 10)
    groups = np.asarray(block['weight_group_ids'], dtype=int)
    samples = distribution['samples']
    if score_report['direct'] != 0:
        raise ValueError('static score report must be direct=0')
    if distribution['thresholds'] != block['thresholds']:
        raise ValueError('static score thresholds do not match parameter package')
    if distribution['sharpness'] != sharpness or distribution['score_window'] != block['score_window']:
        raise ValueError('static score configuration does not match parameter package')

    rows = []
    base_all = []
    radius_all = []
    for sample in samples:
        base = np.asarray(sample['score_magnitude'], dtype=float)
        masses = np.asarray(sample['masses'], dtype=float)
        if base.shape != (4,) or masses.shape != (10, 4):
            raise ValueError(f"unexpected static sample shape: {sample['keys']}")
        point_weights = weights[groups].T
        effective = np.sum(masses * point_weights, axis=0)
        radius = sample['keys'][0]
        rows.append({
            'radius_mm': radius,
            'theoretical_curvature_m_inv': sample['theoretical_curvature_m_inv'],
            'base_magnitude': base.tolist(),
            'weight_masses_point21': masses[:, 2].tolist(),
            'weight_masses_point22': masses[:, 3].tolist(),
            'effective_weight_point21': float(effective[2]),
            'effective_weight_point22': float(effective[3]),
            'weighted_magnitude_point21': float(base[2] * effective[2]),
            'weighted_magnitude_point22': float(base[3] * effective[3]),
        })
        base_all.append(base)
        radius_all.append(radius)
    base_all = np.asarray(base_all, dtype=float)

    coverage = []
    for level, threshold in enumerate(thresholds, start=1):
        above = base_all > threshold
        coverage.append({
            'level': level,
            'threshold_m_inv': float(threshold),
            'soft_transition_10_to_90_m_inv': [
                float(threshold - width / 2.0), float(threshold + width / 2.0),
            ],
            'sample_count_base_above_threshold_by_point': above.sum(axis=0).tolist(),
            'radii_with_any_point_above_threshold_mm': [
                radius_all[i] for i in np.flatnonzero(above.any(axis=1))
            ],
            'point21_radii_above_threshold_mm': [
                radius_all[i] for i in np.flatnonzero(above[:, 2])
            ],
            'point22_radii_above_threshold_mm': [
                radius_all[i] for i in np.flatnonzero(above[:, 3])
            ],
        })

    return {
        'source_score_report': str(score_path),
        'direction': 0,
        'point_ids': [19, 20, 21, 22],
        'thresholds_m_inv': thresholds.tolist(),
        'sharpness': sharpness,
        'score_window': int(block['score_window']),
        'sigmoid_10_to_90_width_m_inv': width,
        'weights_by_group': {
            f'group{group}': [
                {'level': level, 'weight': float(value),
                 'lower_threshold_m_inv': (None if level == 0 else float(thresholds[level - 1]))}
                for level, value in enumerate(weights[group])
            ]
            for group in range(3)
        },
        'samples_point21_point22': rows,
        'level_coverage': coverage,
        'max_base_magnitude_by_point': base_all.max(axis=0).tolist(),
        'max_base_radius_by_point': {
            str(point): radius_all[int(np.argmax(base_all[:, index]))]
            for index, point in enumerate([19, 20, 21, 22])
        },
        'high_curvature_coverage': {
            'threshold_35': next(item for item in coverage if item['threshold_m_inv'] == 35.0),
            'threshold_45': next(item for item in coverage if item['threshold_m_inv'] == 45.0),
        },
    }


def _process_frame(rec, frame, previous_strain, first_timestamp):
    raw = np.asarray(frame['raw_data'], dtype=float)
    processed = raw[:, 1:] - raw[:, :1]
    bad = ~np.isfinite(processed).all(axis=1)
    if np.any(bad):
        processed[bad] = previous_strain[bad] if previous_strain is not None else 0.0
    strain = processed.T
    magnitude, angle, weights, slope_map, diagnostics = rec._assemble_multiregion_parameters(
        strain, 0,
    )
    node_magnitude = np.r_[magnitude[0], magnitude, magnitude[-1]]
    node_angle = np.r_[angle[0], angle, angle[-1]]
    interp_magnitude, interp_angle, interp_x = rec._interpolate_curvature_vector(
        node_magnitude, np.unwrap(node_angle), method='pchip',
    )
    metrics = curvature_tail_metrics(interp_x, interp_magnitude, interp_angle)
    end5 = diagnostics['end5cm']
    return processed, {
        'elapsed_s': float(frame['timestamp'] - first_timestamp),
        'tail_metrics': metrics,
        'base_magnitude_point21': float(diagnostics['base_magnitude'][20]),
        'base_magnitude_point22': float(diagnostics['base_magnitude'][21]),
        'group_base_magnitude': end5['group_base_magnitude'],
        'weight_scores_point21': np.asarray(end5['weight_scores'])[:, 2].tolist(),
        'weight_scores_point22': np.asarray(end5['weight_scores'])[:, 3].tolist(),
        'weight_masses_point21': np.asarray(end5['weight_masses'])[:, 2].tolist(),
        'weight_masses_point22': np.asarray(end5['weight_masses'])[:, 3].tolist(),
        'effective_weight_point21': float(end5['effective_weights'][2]),
        'effective_weight_point22': float(end5['effective_weights'][3]),
        'slope_masses_point21': np.asarray(end5['slope_masses'])[:, 2].tolist(),
        'slope_masses_point22': np.asarray(end5['slope_masses'])[:, 3].tolist(),
    }


def _dynamic_peak(package, recording):
    rec = _make_reconstructor(package, 'original_weights_slopes')
    first_timestamp = None
    previous_strain = None
    peak = None
    peak_frame = None
    base_peaks = {'point21': None, 'point22': None}
    with Path(recording).open('rb') as stream:
        for frame_index in range(10**9):
            try:
                frame = pickle.load(stream)
            except EOFError:
                break
            timestamp = float(frame['timestamp'])
            first_timestamp = timestamp if first_timestamp is None else first_timestamp
            previous_strain, detail = _process_frame(
                rec, frame, previous_strain, first_timestamp,
            )
            scalar = detail['tail_metrics']['scalar_integral_deg']
            if peak is None or scalar > peak['tail_metrics']['scalar_integral_deg']:
                peak = detail
                peak_frame = frame_index
            for key, field in (
                    ('point21', 'base_magnitude_point21'),
                    ('point22', 'base_magnitude_point22')):
                if base_peaks[key] is None or detail[field] > base_peaks[key][field]:
                    base_peaks[key] = {'frame': int(frame_index), **detail}
    if peak is None:
        raise ValueError(f'empty recording: {recording}')
    return {
        'recording': str(recording),
        'peak_frame_by_scalar_tail_integral': int(peak_frame),
        **peak,
        'peak_by_base_magnitude': base_peaks,
    }


def _render_markdown(report, path):
    static = report['static_calibration']
    lines = [
        '# direct=0 end5cm groupwise high-curvature diagnosis', '',
        '本报告只读检查现有参数包、静态 score 结果和动态 pickle；未修改生产代码、参数包或旧结果，未运行优化。', '',
        '## 结论先行', '',
        report['assessment']['root_cause'], '',
        report['assessment']['threshold_only'], '',
        '建议：', '',
        f"- 阈值可先保持现有 `{static['thresholds_m_inv']}`，避免用阈值变化掩盖增益回归问题。",
        f"- 若下一轮确实要重排高曲率过渡，建议试验阈值 `{report['assessment']['recommended_thresholds_for_followup']}`；这是实验设计建议，不代表已有数据已经验证该阈值。",
        '- 对 group1/group2 的 35 和 45 m⁻¹ 档增加高曲率锚定/正则，使有效 weight 向 1 回归；推荐先将这四个参数约束在 [0.8, 1.2]，再用动态锚点验证。',
        '- 若必须减少静态外推，可把 35/45 m⁻¹ 作为单一高曲率档（建议过渡中心约 30–35 m⁻¹），但仍需要 weight=1 约束；只改阈值不足。', '',
        '## 三组完整 weights 与软阈值过渡', '',
        '软区间按 sigmoid score 的 10%–90% 定义，宽度为 `2 ln(9) / sharpness`。每组的 level 0 为低于首阈值的基础档。', '',
    ]
    for group, values in static['weights_by_group'].items():
        lines.append(f'### {group}')
        lines.append('')
        lines.append('| level | weight | lower threshold (m⁻¹) | 10–90% transition (m⁻¹) |')
        lines.append('|---:|---:|---:|---|')
        for item in values:
            level = item['level']
            if level == 0:
                interval = f'< {static["thresholds_m_inv"][0]:g}'
            else:
                threshold = static['thresholds_m_inv'][level - 1]
                half = static['sigmoid_10_to_90_width_m_inv'] / 2.0
                interval = f'{threshold-half:.3f}–{threshold+half:.3f}'
            lines.append(f"| {level} | {item['weight']:.6f} | {item['lower_threshold_m_inv'] if item['lower_threshold_m_inv'] is not None else '—'} | {interval} |")
        lines.append('')

    lines.extend([
        '## 静态定标：点21/22', '',
        '| radius (mm) | theory | base21 | base22 | effective weight21 | effective weight22 |',
        '|---:|---:|---:|---:|---:|---:|',
    ])
    for row in static['samples_point21_point22']:
        lines.append(
            f"| {row['radius_mm']} | {row['theoretical_curvature_m_inv']:.3f} | "
            f"{row['base_magnitude'][2]:.3f} | {row['base_magnitude'][3]:.3f} | "
            f"{row['effective_weight_point21']:.6f} | {row['effective_weight_point22']:.6f} |"
        )
    lines.extend(['', '完整 10 档 masses 见 JSON 的 `samples_point21_point22`。', ''])
    lines.extend(['## 静态样本对各档的真实覆盖', '', '| threshold | point19 | point20 | point21 | point22 |', '|---:|---:|---:|---:|---:|'])
    for item in static['level_coverage']:
        counts = item['sample_count_base_above_threshold_by_point']
        lines.append(
            f"| {item['threshold_m_inv']:.1f} | {counts[0]} | {counts[1]} | {counts[2]} | {counts[3]} |"
        )
    lines.extend([
        '',
        f"特别是 35 m⁻¹ 档：点21/22覆盖数为 `{static['high_curvature_coverage']['threshold_35']['sample_count_base_above_threshold_by_point'][2:]}`；45 m⁻¹ 档：`{static['high_curvature_coverage']['threshold_45']['sample_count_base_above_threshold_by_point'][2:]}`。这意味着点21/22的 35/45 高档没有真实静态样本约束。", '',
        '## group_mean 动态峰值：点21/22', '',
        '| recording | overall peak frame | peak scalar integral (deg) | base21 | base22 | effective weight21 | effective weight22 |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ])
    for item in report['dynamic_peaks']:
        lines.append(
            f"| {Path(item['recording']).name} | {item['peak_frame_by_scalar_tail_integral']} | "
            f"{item['tail_metrics']['scalar_integral_deg']:.3f} | "
            f"{item['base_magnitude_point21']:.3f} | {item['base_magnitude_point22']:.3f} | "
            f"{item['effective_weight_point21']:.6f} | {item['effective_weight_point22']:.6f} |"
        )
    lines.extend(['', '动态整体积分峰值帧的完整 scores、masses、group base magnitude 和 slope masses 见 JSON。', '',
                  '| recording | point | own base peak frame | own base peak (m⁻¹) | other point base at that frame | effective weight |',
                  '|---|---|---:|---:|---:|---:|'])
    for item in report['dynamic_peaks']:
        for point, own_field, other_field in (
                ('point21', 'base_magnitude_point21', 'base_magnitude_point22'),
                ('point22', 'base_magnitude_point22', 'base_magnitude_point21')):
            own = item['peak_by_base_magnitude'][point]
            lines.append(
                f"| {Path(item['recording']).name} | {point} | {own['frame']} | "
                f"{own[own_field]:.3f} | {own[other_field]:.3f} | "
                f"{own['effective_weight_'+point]:.6f} |"
            )
    lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parameters', type=Path, required=True)
    parser.add_argument('--static-score', type=Path, required=True)
    parser.add_argument('--recordings', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    package = load_sensor_package(args.parameters)
    static = _static_analysis(package, args.static_score)
    dynamic = [_dynamic_peak(package, recording) for recording in args.recordings]
    report = {
        'scope': {
            'parameters': str(args.parameters),
            'static_score': str(args.static_score),
            'recordings': [str(path) for path in args.recordings],
            'mutations': 'none; read-only diagnosis',
        },
        'static_calibration': static,
        'dynamic_peaks': dynamic,
        'assessment': {
            'root_cause': 'direct=0 点21/22的静态 base_magnitude 没有覆盖 35/45 m⁻¹ 高档，但对应 group1/group2 weights 在这些档位接近 5.0 上界；高档参数因此是边界外推，不是由点21/22高曲率静态样本识别出的增益。动态回放中点21进入 57–65 m⁻¹，点22自身最高约 34.2 m⁻¹，但两者都会落入由静态外推形成的高档权重区。',
            'threshold_only': '仅调整 thresholds 不足：它只能改变动态帧落入哪个档位，不能把已经接近 5.0 的高曲率档增益变成接近 1；若把阈值推高到动态峰值以上，则会得到旧档/低档的另一种外推，且会损失明确的曲率分级语义。',
            'recommended_thresholds_for_followup': [0.8, 1.2, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 45.0],
            'weight_constraint': '优先对 group1/group2 的 level 8/9（35/45 m⁻¹）加入 w≈1 的锚定或窄边界；推荐初始边界 [0.8, 1.2]，同时保留 group0 现有参数作为对照。',
            'dynamic_anchor': '若动态工况确实应在 57–65 m⁻¹ 保持有效 weight≈1，应加入动态或人工确认的高曲率锚点样本；否则静态参数包无法从现有数据证明该结论。',
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'analysis.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8',
    )
    _render_markdown(report, args.output / 'analysis.md')
    print(json.dumps({
        'output': str(args.output),
        'static_samples': len(static['samples_point21_point22']),
        'dynamic_recordings': len(dynamic),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
