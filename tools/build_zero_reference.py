"""CLI for building a stored zero reference from raw FBG CSV files."""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.zero_reference import build_zero_reference, save_zero_reference


def _parse_channels(value):
    try:
        channels = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("通道必须是逗号分隔的整数，例如 1,2,3,4") from exc
    if not channels:
        raise argparse.ArgumentTypeError("至少需要一个物理通道")
    return channels


def main():
    parser = argparse.ArgumentParser(description="生成带 SensorID 的绝对波长零状态 JSON")
    parser.add_argument("input_dir", type=Path, help="FiberTecc 或 Hippo 原始 CSV 目录")
    parser.add_argument("--sensor-id", required=True, help="传感器 SensorID")
    parser.add_argument("--interrogator", required=True, choices=["FiberTecc", "Hippo"], help="原始 CSV 格式")
    parser.add_argument("--active-channels", type=_parse_channels, required=True, help="按运行顺序给出的物理通道，例如 1,2,3,4")
    parser.add_argument("--output", type=Path, help="输出路径；默认 params/<SensorID>_zero_reference.json")
    args = parser.parse_args()
    output = args.output or PROJECT_ROOT / "params" / f"{args.sensor_id}_zero_reference.json"
    reference = build_zero_reference(args.input_dir, sensor_id=args.sensor_id, interrogator=args.interrogator, active_channels=args.active_channels)
    path = save_zero_reference(reference, output)
    counts = {channel: payload["valid_row_count"] for channel, payload in reference["channels"].items()}
    print(f"零状态文件已生成: {path.resolve()}")
    print(f"SensorID={reference['sensor_id']}, channels={reference['active_channels']}, point_count={reference['point_count']}, valid_rows={counts}")


if __name__ == "__main__":
    main()
