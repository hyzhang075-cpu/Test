"""Build, save, and validate absolute-wavelength zero references."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


FORMAT_VERSION = 1


def _normalise_interrogator(interrogator):
    value = str(interrogator).strip().lower()
    if value == "fibertecc":
        return "FiberTecc"
    if value == "hippo":
        return "Hippo"
    raise ValueError(f"不支持的解调仪类型: {interrogator!r}")


def _discover_channel_files(input_dir, interrogator):
    root = Path(input_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"零状态原始数据目录不存在: {root}")
    if interrogator == "FiberTecc":
        pattern = re.compile(r"^channel_(\d+)_.*\.csv$", re.IGNORECASE)
        to_physical = lambda channel: channel
    else:
        pattern = re.compile(r"^ch(\d+)_.*\.csv$", re.IGNORECASE)
        to_physical = lambda channel: channel + 1
    files_by_channel = {}
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        match = pattern.match(path.name)
        if match is not None:
            files_by_channel.setdefault(to_physical(int(match.group(1))), []).append(path)
    if not files_by_channel:
        raise ValueError(f"目录中未找到 {interrogator} 格式的通道 CSV: {root}")
    return files_by_channel


def _wavelength_columns(frame):
    named = [column for column in frame.columns if re.match(r"^WL_\d+\(nm\)$", str(column), re.IGNORECASE)]
    if named:
        return named
    if frame.shape[1] <= 2:
        raise ValueError("CSV 不包含波长列")
    return list(frame.columns[2:])


def _mean_channel_files(paths):
    valid_blocks = []
    point_count = None
    for path in paths:
        frame = pd.read_csv(path)
        values = frame.loc[:, _wavelength_columns(frame)].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        if point_count is None:
            point_count = values.shape[1]
        elif values.shape[1] != point_count:
            raise ValueError(f"同一通道 CSV 的栅点数不一致: {path} 有 {values.shape[1]} 点，预期 {point_count} 点")
        valid_rows = values[np.isfinite(values).all(axis=1)]
        if len(valid_rows):
            valid_blocks.append(valid_rows)
    if not valid_blocks:
        raise ValueError(f"通道 CSV 清洗后无完整有限值行: {[str(path) for path in paths]}")
    combined = np.vstack(valid_blocks)
    means = combined.mean(axis=0)
    if not np.isfinite(means).all():
        raise ValueError("通道平均波长包含非有限值")
    return means, len(combined)


def build_zero_reference(input_dir, sensor_id, interrogator, active_channels):
    """Average raw interrogator CSVs into the unified zero-reference schema."""
    interrogator = _normalise_interrogator(interrogator)
    active_channels = [int(channel) for channel in active_channels]
    if not sensor_id or not str(sensor_id).strip():
        raise ValueError("SensorID 不能为空")
    if not active_channels or len(set(active_channels)) != len(active_channels):
        raise ValueError(f"active_channels 必须是非空且不重复的物理通道序列: {active_channels}")
    files_by_channel = _discover_channel_files(input_dir, interrogator)
    if set(files_by_channel) != set(active_channels):
        raise ValueError("原始零状态数据通道与 active_channels 不一致: " f"数据通道={sorted(files_by_channel)}, active_channels={active_channels}")
    channels = {}
    common_point_count = None
    for physical_channel in active_channels:
        means, valid_row_count = _mean_channel_files(files_by_channel[physical_channel])
        if common_point_count is None:
            common_point_count = len(means)
        elif len(means) != common_point_count:
            raise ValueError(f"通道 {physical_channel} 的栅点数为 {len(means)}，预期 {common_point_count}")
        channels[str(physical_channel)] = {
            "wavelengths_nm": means.tolist(),
            "valid_row_count": int(valid_row_count),
            "source_files": [path.name for path in files_by_channel[physical_channel]],
        }
    return {
        "format_version": FORMAT_VERSION,
        "sensor_id": str(sensor_id),
        "source_interrogator": interrogator,
        "active_channels": active_channels,
        "point_count": int(common_point_count),
        "channels": channels,
        "source_directory": str(Path(input_dir).resolve()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def save_zero_reference(reference, output_path):
    """Write a reference as UTF-8 JSON, rejecting non-standard NaN values."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reference, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def load_zero_reference(path, sensor_id, active_channels, total_points, raw_trim_idx=0):
    """Load a zero reference in raw or already-trimmed point order."""
    reference_path = Path(path)
    if not reference_path.is_file():
        raise FileNotFoundError(f"零状态文件不存在: {reference_path}")
    try:
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取零状态 JSON {reference_path}: {exc}") from exc
    if reference.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"零状态格式版本不支持: {reference.get('format_version')!r}，预期 {FORMAT_VERSION}")
    if reference.get("sensor_id") != str(sensor_id):
        raise ValueError(f"零状态 SensorID 不一致: 文件={reference.get('sensor_id')!r}, 当前={sensor_id!r}")
    expected_channels = [int(channel) for channel in active_channels]
    if reference.get("active_channels") != expected_channels:
        raise ValueError(f"零状态 active_channels 不一致: 文件={reference.get('active_channels')!r}, 当前={expected_channels!r}")
    if (isinstance(raw_trim_idx, bool) or not isinstance(raw_trim_idx, (int, np.integer))
            or raw_trim_idx < 0):
        raise ValueError(f"raw_trim_idx 必须是非负整数: {raw_trim_idx!r}")
    trim_idx = int(raw_trim_idx)
    file_point_count = reference.get("point_count")
    raw_point_count = int(total_points) + trim_idx
    if file_point_count not in (int(total_points), raw_point_count):
        raise ValueError(
            f"零状态栅点数量不一致: 文件={file_point_count!r}, "
            f"当前={int(total_points)}, 原始={raw_point_count}"
        )
    needs_trim = trim_idx > 0 and file_point_count == raw_point_count
    channel_payload = reference.get("channels")
    if not isinstance(channel_payload, dict):
        raise ValueError("零状态 channels 必须是通道字典")
    expected_channel_names = {str(channel) for channel in expected_channels}
    if set(channel_payload) != expected_channel_names:
        raise ValueError(f"零状态通道名称或数量不一致: 文件={sorted(channel_payload)}, 当前={expected_channels}")
    loaded = {}
    for channel in expected_channels:
        payload = channel_payload[str(channel)]
        if not isinstance(payload, dict) or "wavelengths_nm" not in payload:
            raise ValueError(f"零状态通道 {channel} 缺少 wavelengths_nm")
        values = np.asarray(payload["wavelengths_nm"], dtype=float)
        if values.shape != (file_point_count,):
            raise ValueError(f"零状态通道 {channel} 栅点数量不一致: 文件={values.shape}, 声明={file_point_count}")
        if not np.isfinite(values).all():
            raise ValueError(f"零状态通道 {channel} 包含非有限波长")
        loaded[channel] = values[trim_idx:].copy() if needs_trim else values.copy()
    return loaded
