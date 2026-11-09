"""读取末端定标原始CSV，追踪通道、清洗、差分应变和曲率选档幅值。"""
import argparse
import ast
from itertools import permutations
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calibration_regions import compute_fbg_geometry
from reconstructor import Reconstructor


def valid_rows(values, threshold=9000, half_window=5):
    """向量化复现build_valid_row_mask的邻行比较，同时排除非有限值。"""
    valid = np.all(np.isfinite(values), axis=1)
    for offset in range(1, half_window + 1):
        left, right = values[:-offset], values[offset:]
        different = np.abs(left-right) > threshold
        valid[:-offset] &= ~np.any(different & (np.abs(left) >= np.abs(right)), axis=1)
        valid[offset:] &= ~np.any(different & (np.abs(right) >= np.abs(left)), axis=1)
    return valid


def curvature_microstrain(outer, radius_m):
    """等间隔三外围通道的曲率模；去除共模后与相位及通道置换无关。"""
    deviator = outer - np.mean(outer, axis=-1, keepdims=True)
    return np.sqrt(2/3*np.sum(deviator**2, axis=-1))*1e-6/radius_m


def read_sample(folder, channels, count):
    """读取实际物理通道CSV，保存全局行号/硬件标签及清洗前后的均值。"""
    clean, raw, records, series = [], [], [], []
    for channel in channels:
        paths = sorted(folder.glob(f'*_{channel}_*.csv'))
        frames = [(path, pd.read_csv(path).dropna(axis=1, how='all')) for path in paths]
        path, frame = next((p, f) for p, f in frames if not f.empty)
        values = frame.iloc[:, 2:].apply(pd.to_numeric, errors='coerce').to_numpy(float)
        if values.shape[1] != count:
            raise ValueError(f'{path}: expected {count} FBG columns')
        mask = valid_rows(values)
        if not np.any(mask):
            raise ValueError(f'{path}: no valid rows')
        raw.append(np.nanmean(values, axis=0))
        clean.append(np.mean(values[mask], axis=0))
        series.append((frame.iloc[:, 0].to_numpy(), values, mask))
        records.append({'physical_channel': channel, 'path': './'+path.relative_to(ROOT).as_posix(),
                        'rows': len(frame), 'kept': int(mask.sum()),
                        'hardware_sensor_ids': ast.literal_eval(str(frame.iloc[0, 1])),
                        'fbg_columns': list(frame.columns[2:])})
    return np.stack(clean, axis=-1), np.stack(raw, axis=-1), records, series


def run(package_path, output):
    """分析三方向所有end5cm圆弧样本；不改定标数据或生产参数。"""
    package = json.loads(package_path.read_text(encoding='utf-8'))
    shared = {k: v for group in package['shared_parameters'].values() for k, v in group.items()}
    channels = shared['active_channels']
    if shared['interrogator'] != 'FiberTecc' or channels != [1, 2, 3, 4] or shared['channel_change'] or shared['interlaced_grating'] or shared['active_angles'] is not None:
        raise ValueError('本诊断要求当前FiberTecc四通道、等间隔外围角度、无换道/交错配置')
    count = len(shared['samp_dist_preset'])
    length, positions = compute_fbg_geometry(shared['start_value'], shared['end_value'], shared['samp_dist_preset'])
    region = package['regions']['end5cm']
    ids = region['support_point_ids']
    indices = np.asarray(ids)-1
    data_root = ROOT / shared['calibration_data_root'] / region['folder_path']
    score = Reconstructor.__new__(Reconstructor)
    score.soft = True
    score.num_levels = len(region['thresholds'])+1
    score.thresholds = region['thresholds']
    score.sharpness = region['sharpness']
    score.min_consecutive = region['score_window']
    score.total_points = len(ids)
    report = {'sensor_id': package['sensor_id'], 'unit': 'CSV数值按生产代码解释为microstrain；曲率为m^-1',
              'assumption': '实际传感器弯曲半径与radii一致', 'global_point_ids': ids,
              'distance_to_tip_mm': ((length-positions[indices])*1000).tolist(),
              'samples': {}, 'mapping': '列1作为中心物理通道1；外围为物理通道2/3/4；全局行号不等于硬件标签'}
    for direct in (0, 120, 240):
        rows = {}
        zero, _, _, _ = read_sample(data_root/f'{direct}-0', channels, count)
        for radius in region['radii']['circ']:
            clean, raw, records, series = read_sample(data_root/f'{direct}-{radius}', channels, count)
            local = clean[indices]
            differential = local[:, 1:]-local[:, [0]]
            base = curvature_microstrain(local[:, 1:], shared['R'])
            zero_corrected = curvature_microstrain((clean-zero)[indices, 1:], shared['R'])
            masses = score._alloc_mass(score._get_scores(base))
            weights = np.asarray(region['weights'][str(direct)])
            levels = masses.shape[0]
            weight_vectors = np.broadcast_to(weights[:levels, None], masses.shape).copy()
            if region.get('weight_group_ids') is not None:
                weight_vectors = weights.reshape(-1,levels)[np.asarray(region['weight_group_ids'])].T
            elif region.get('end_weights', False):
                weight_vectors[:, region['end_start']:] = weights[levels:, None]
            gain = np.sum(masses*weight_vectors, axis=0)
            raw_base = curvature_microstrain(raw[indices, 1:], shared['R'])
            perm_error = max(float(np.max(np.abs(curvature_microstrain(local[:, list(order)], shared['R'])-base)))
                             for order in permutations((1, 2, 3)))
            aligned = all(np.array_equal(series[0][0], item[0]) for item in series[1:])
            temporal = None
            if aligned:
                mask = np.logical_and.reduce([item[2] for item in series])
                outer = np.stack([item[1][mask][:, indices] for item in series[1:]], axis=-1)
                instantaneous = curvature_microstrain(outer, shared['R'])
                temporal = {'median_curvature': np.median(instantaneous, axis=0).tolist(),
                            'std_curvature': np.std(instantaneous, axis=0).tolist(),
                            'aligned_kept_rows': int(mask.sum())}
            rows[str(radius)] = {'raw_channel_mean_microstrain': local.tolist(),
                'outer_minus_centre_microstrain': differential.tolist(), 'files': records,
                'raw_curvature_before_cleaning': raw_base.tolist(), 'base_curvature': base.tolist(),
                'zero_corrected_curvature': zero_corrected.tolist(),
                'theory_curvature': 1000/radius if radius else 0,
                'mass': masses.tolist(), 'effective_weights': gain.tolist(),
                'weighted_curvature': (base*gain).tolist(),
                'outer_permutation_max_curvature_error': perm_error,
                'centre_subtraction_max_curvature_error': float(np.max(np.abs(curvature_microstrain(differential, shared['R'])-base))),
                'timestamp_aligned': aligned, 'temporal': temporal}
        report['samples'][str(direct)] = rows
    output.mkdir(parents=True, exist_ok=True)
    (output/'strain_traces.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    plot(report, output)
    return report


def plot(report, output):
    """画出点位响应和原始差分应变，并导出末端衰减的数值汇总。"""
    fig, axes = plt.subplots(3, 2, figsize=(13, 13), constrained_layout=True)
    lines = ['# 末端真实点差分应变诊断', '',
             '实际半径与定标radii一致。全局点位距末端(mm)：'+str(report['distance_to_tip_mm']), '',
             '|方向|半径mm|未经weight曲率（末端四点）m⁻¹|有效weight|末点/理论%|末点/第19点%|',
             '|---:|---:|---|---|---:|---:|']
    for row, direct in enumerate((0, 120, 240)):
        for radius in (200, 100, 75, 50, 30, 20, 15):
            values = report['samples'][str(direct)][str(radius)]
            base = np.asarray(values['base_curvature'])
            theory = values['theory_curvature']
            axes[row, 0].plot(report['distance_to_tip_mm'], base/theory, 'o-', label=f'R={radius}mm')
            lines.append(f'|{direct}|{radius}|'+', '.join(f'{x:.3f}' for x in base)+'|'+
                         ', '.join(f'{x:.3f}' for x in values['effective_weights'])+
                         f'|{100*base[-1]/theory:.2f}|{100*base[-1]/base[0]:.2f}|')
        values = report['samples'][str(direct)]['15']
        differential = np.asarray(values['outer_minus_centre_microstrain'])
        for channel in range(3):
            axes[row, 1].plot(report['distance_to_tip_mm'], differential[:, channel], 'o-', label=f'Ch{channel+2}-Ch1')
        axes[row, 0].axhline(1., color='gray', ls='--')
        for column in range(2):
            axes[row, column].invert_xaxis()
            axes[row, column].set_xlabel('Distance to sensor tip (mm)')
            axes[row, column].set_title(f'direct={direct}'+(' raw curvature / theory' if column == 0 else ' R=15mm differential strain'))
            axes[row, column].grid(alpha=.3)
            axes[row, column].legend(fontsize=8)
        axes[row, 0].set_ylabel('Response ratio')
        axes[row, 1].set_ylabel('Microstrain (production unit convention)')
    fig.savefig(output/'tail_strain.png', dpi=160)
    plt.close(fig)
    (output/'summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensor-params', default='params/06B6_NeTi_v2_ftube_multi_region_validated.json')
    parser.add_argument('--output', default='docs/tail-strain-20260916')
    args = parser.parse_args()
    run(ROOT/args.sensor_params, ROOT/args.output)
    print(args.output)
