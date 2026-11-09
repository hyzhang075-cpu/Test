"""Build a one-direction dynamic-demo package from a base package and end5 result."""

from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.sensor_parameter_package import (
    build_single_direction_demo_package, load_sensor_package, write_sensor_package,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build a single-direction demo parameter package')
    parser.add_argument('--base-package', required=True)
    parser.add_argument('--override-result', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--direction', type=int, default=0, choices=[0, 120, 240])
    args = parser.parse_args(argv)
    base_path = Path(args.base_package)
    result_path = Path(args.override_result)
    base = load_sensor_package(base_path)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    package = build_single_direction_demo_package(
        base, result, direction=args.direction,
        base_source=str(base_path), override_source=str(result_path),
    )
    write_sensor_package(package, args.output)
    return package


if __name__ == '__main__':
    main()
