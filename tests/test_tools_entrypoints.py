"""工具迁移后，脚本和模块入口都应可用，项目路径不应变成tools目录。"""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize('name', ['sensor_parameter_package', 'calibration_validation', 'build_zero_reference'])
@pytest.mark.parametrize('mode', ['script', 'module'])
def test_tools_help_entrypoints(name, mode):
    target = [str(ROOT / 'tools' / f'{name}.py')] if mode == 'script' else ['-m', f'tools.{name}']
    result = subprocess.run([sys.executable, *target, '--help'], cwd=ROOT,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert b'usage:' in result.stdout


def test_export_paths_still_resolve_against_project_root():
    from tools.sensor_parameter_package import PROJECT_ROOT, _project_relative_path
    assert PROJECT_ROOT == ROOT
    assert _project_relative_path(ROOT / 'params' / 'sample.json') == './params/sample.json'
