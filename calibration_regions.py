"""定标区域的几何与配置解析，不依赖 GUI、硬件或优化器。

局部数据使用局部坐标重构，但保留全局真实数据行号及全局空间段编号，
供后续区域参数对齐使用。这里的行号不是解调仪提供的硬件 FBG 标签。
"""

from copy import deepcopy
import warnings

import numpy as np


def validate_weight_group_ids(groups, point_count):
    """Validate explicit group indices for real support points; None is legacy layout."""
    if groups is None:
        return None
    values = np.asarray(groups)
    if (values.shape != (point_count,) or values.dtype.kind not in 'iu'
            or np.any(values < 0) or sorted(set(values.tolist())) != list(range(int(values.max())+1))):
        raise ValueError('weight_group_ids必须对应每个真实点，使用从0开始连续的整数分组')
    return values.astype(int).tolist()


def validate_end_weight_config(enabled, start, point_count):
    """校验区域末端权重开关与负索引；索引只包含真实support点。"""
    if not isinstance(enabled, (bool, np.bool_)):
        raise ValueError('end_weights 必须是布尔值')
    if isinstance(start, bool) or not isinstance(start, (int, np.integer)) or start >= 0:
        raise ValueError('end_start 必须是负整数')
    if enabled and -start > point_count:
        raise ValueError('end_start 超出区域真实点数量')
    return bool(enabled), int(start)


def compute_fbg_geometry(start_value, end_value, samp_dist_preset):
    """mm 输入，返回全长(m)和未裁剪真实采样坐标(m)。

沿用 Sensor 的点序约定：预设位置的间距倒序排列。总长度只取一次
首末预设跨度，加上近端、远端两个无传感点间隙，虚拟点不计入点数。
"""
    preset = np.asarray(samp_dist_preset, dtype=float)
    gaps = np.asarray([start_value, end_value], dtype=float)
    if (preset.ndim != 1 or preset.size < 2 or not np.all(np.isfinite(preset))
            or not np.all(np.diff(preset) > 0)):
        raise ValueError('samp_dist_preset 必须包含至少两个有限、严格递增的 mm 位置')
    if not np.all(np.isfinite(gaps)) or end_value < 0:
        raise ValueError('start_value 必须是有限 mm 数值，end_value 必须是有限非负 mm 数值')
    ideal_len = float((gaps.sum() + preset[-1] - preset[0]) / 1000.0)
    positions = (gaps[0] + np.r_[0.0, np.cumsum(np.diff(preset)[::-1])]) / 1000.0
    if ideal_len <= 0 or not np.any(positions >= 0):
        raise ValueError('传感器有效长度必须为正，且至少有一个传感点位于零点或其后')
    return ideal_len, positions


def _validate_partition(segmentation, point_count, label):
    """拒绝会被旧 _calculate_segments 静默截断或补长的空间分段。"""
    values = np.asarray(segmentation, dtype=float)
    if (values.ndim != 1 or not values.size or not np.all(np.isfinite(values))
            or np.any(values <= 0) or np.any(values != np.floor(values))
            or np.sum(values) != point_count):
        raise ValueError(f'{label}分段必须为正整数列表且总和等于 {point_count} 个真实点；收到 {segmentation}')
    return values.astype(int).tolist()


def _trim_partition_prefix(segmentation, removed_points):
    """从分段头部移除真实点，并保留剩余点所属的原始分段编号。"""
    remaining = int(removed_points)
    trimmed = []
    segment_ids = []
    for segment_id, count in enumerate(segmentation):
        kept = int(count)
        if remaining:
            consumed = min(remaining, kept)
            kept -= consumed
            remaining -= consumed
        if kept:
            trimmed.append(kept)
            segment_ids.append(segment_id)
    if remaining:
        raise ValueError('裁切点数超出全长分段定义')
    return trimmed, segment_ids


def resolve_calibration_region(*, start_value, end_value, samp_dist_preset,
                               full_segmentation, profiles,
                               optimization_region, multi_region_calib):
    """在读取数据前生成单次定标配置，严格保持局部和全局空间段一致。

    multi_region_calib=False 选择一个区域独立定标或重构。
    True 允许批量选择嵌套定标长度；一次仍优化一个数据集，并不代表已联合优化。
每个局部区域必须由若干完整的全长空间段组成；不自动拆段或合并段。
"""
    ideal_len, raw_positions = compute_fbg_geometry(start_value, end_value, samp_dist_preset)
    raw_point_count = len(raw_positions)
    raw_full_segments = _validate_partition(full_segmentation, raw_point_count, '全长')
    # 固定件内部的传感点不参与定标/重构。保留原始点号，并同步裁切首段计数。
    zero_start_index = int(np.searchsorted(raw_positions, -1e-12, side='left'))
    positions = raw_positions[zero_start_index:]
    full_segments, full_segment_ids = _trim_partition_prefix(
        raw_full_segments, zero_start_index,
    )
    if optimization_region not in profiles:
        raise ValueError(f'未知 optimization_region={optimization_region!r}；可选 {list(profiles)}')
    if (optimization_region == 'full' and zero_start_index > 0
            and full_segments and full_segments[0] < 2):
        suggested = list(full_segments)
        if len(suggested) > 1 and suggested[1] > 2:
            suggested[0] += 1
            suggested[1] -= 1
        elif len(suggested) > 1:
            suggested = [suggested[0] + suggested[1], *suggested[2:]]
        warnings.warn(
            f'start_value={start_value} mm 裁掉 {zero_start_index} 个零点前传感点后，'
            f'全段 segmentation 从 {raw_full_segments} 变为 {full_segments}；'
            f'首段仅剩 {full_segments[0]} 个点，无法可靠进行分段拟合。'
            f'请重新分段并重新标定；可参考裁切后分段 {suggested}，'
            '不要直接沿用现有 slopes。',
            RuntimeWarning,
            stacklevel=2,
        )
    profile = deepcopy(profiles[optimization_region])
    length = profile['length_m']
    if optimization_region == 'full':
        if length is not None:
            raise ValueError('full 的 length_m 必须为 None，长度由传感器几何计算')
        crop_start = 0.0
        start_index = 0
    else:
        if length is None or not np.isfinite(length) or not 0 < length <= ideal_len:
            raise ValueError(f'{optimization_region} 的 length_m 必须在 (0, {ideal_len}] m 内')
        crop_start = ideal_len - float(length)
        # 只吸收浮点舍入误差，恰好在区域边界上的真实点应被保留。
        start_index = int(np.searchsorted(positions, crop_start - 1e-12))
        if start_index == len(positions):
            raise ValueError(f'{optimization_region} 内没有真实传感点')

    boundaries = np.r_[0, np.cumsum(full_segments)]
    matches = np.flatnonzero(boundaries[:-1] == start_index)
    if not len(matches):
        raise ValueError(
            f'{optimization_region} 从全局第 {start_index + 1} 个真实点开始，切入全长分段；'
            f'全长分段={full_segments}，必须在该点之前设置独立分段边界'
        )
    first_segment = int(matches[0])
    expected_segments = full_segments[first_segment:]
    if optimization_region == 'full':
        raw_local_segments = _validate_partition(
            profile['segmentation'], raw_point_count, optimization_region,
        )
        local_segments, _ = _trim_partition_prefix(raw_local_segments, zero_start_index)
    else:
        local_segments = _validate_partition(
            profile['segmentation'], len(positions) - start_index, optimization_region,
        )
    if local_segments != expected_segments:
        raise ValueError(
            f'{optimization_region} 分段 {local_segments} 与全长对应分段 {expected_segments} 不一致；'
            '请同步修改全长与局部分段，不允许仅按相同点数拼接'
        )
    thresholds = np.asarray(profile['thresholds'], dtype=float)
    if (thresholds.ndim != 1 or not np.all(np.isfinite(thresholds))
            or np.any(thresholds <= 0) or np.any(np.diff(thresholds) <= 0)):
        raise ValueError(f'{optimization_region} thresholds 必须是有限、正值、严格递增列表')
    if not profile['radii'] or not profile['folder_path']:
        raise ValueError(f'{optimization_region} 缺少 radii 或 folder_path')

    samples = positions[start_index:] - crop_start
    profile['end_weights'], profile['end_start'] = validate_end_weight_config(
        profile.get('end_weights', False), profile.get('end_start', -5), len(samples))
    samples[np.abs(samples) < 1e-12] = 0.0
    profile.update(
        ideal_len=ideal_len,
        straight_trim=0.0 if optimization_region == 'full' else -float(length),
        segmentation=local_segments,
        thresholds=thresholds.tolist(),
        optimization_region=optimization_region,
        global_point_ids=list(range(zero_start_index + start_index + 1, raw_point_count + 1)),
        global_segment_ids=full_segment_ids[first_segment:],
        global_sample_dist_m=positions[start_index:].tolist(),
        sample_dist_m=samples.tolist(),
        crop_origin_m=crop_start,
        reconstruction_length_m=ideal_len if optimization_region == 'full' else float(length),
    )
    return profile


def validate_calibration_parameters(weights, slopes, thresholds, segmentation,
                                    directions, *, end_weights=False, s_shape=False, weight_group_ids=None):
    """预载参数必须匹配所选区域，防止旧 5 cm 数组被误用于新全长定标。

    None 表示让现有初始化器生成初值；此处不猜测或重采样已定标参数。
    返回独立的 NumPy 数组字典，支持重构中的 slope[level, segment] 索引，
    同时不修改 CLI/配置字典中的原始列表。
"""
    levels = len(thresholds) + 1
    groups = validate_weight_group_ids(weight_group_ids, sum(segmentation))
    group_count = max(groups)+1 if groups is not None else (2 if end_weights else 1)
    expected = {
        'weights': (levels * group_count,),
        'slopes': (levels, len(segmentation) * (2 if s_shape else 1)),
    }
    normalized = []
    for name, parameters in [('weights', weights), ('slopes', slopes)]:
        if parameters is None:
            normalized.append(None)
            continue
        if not isinstance(parameters, dict):
            raise ValueError(f'{name} 必须是方向到参数数组的字典或 None')
        result = {}
        for direct in directions:
            if direct not in parameters:
                raise ValueError(f'{name} 缺少方向 {direct}')
            values = np.asarray(parameters[direct], dtype=float)
            if values.shape != expected[name] or not np.all(np.isfinite(values)):
                raise ValueError(f'{name}[{direct}] 需为有限的 {expected[name]} 数组，收到 {values.shape}；'
                                 '请提供所选区域参数或使用 None 重新初始化')
            result[direct] = values.copy()
        normalized.append(result)
    return tuple(normalized)
