from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE_PACKAGE = ROOT / 'params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json'
OVERRIDE_RESULT = ROOT / 'calibration_results/06B6_NeTi_v2_ftube-20260919T192950+0800-direct0-3d3aaf/results.json'


def _inputs():
    base = json.loads(BASE_PACKAGE.read_text(encoding='utf-8'))
    result = json.loads(OVERRIDE_RESULT.read_text(encoding='utf-8'))
    return base, result


def test_single_direction_demo_package_replaces_only_end5_direct0():
    from tools.sensor_parameter_package import build_single_direction_demo_package

    base, result = _inputs()
    full_before = deepcopy(base['regions']['full'])
    end15_before = deepcopy(base['regions']['end15cm'])
    package = build_single_direction_demo_package(
        base, result, base_source=str(BASE_PACKAGE), override_source=str(OVERRIDE_RESULT),
    )

    assert package['regions']['full'] == full_before
    assert package['regions']['end15cm'] == end15_before
    assert package['shared_parameters']['calibration_experiment_parameters']['exp_directs'] == [0]
    runtime = package['shared_parameters']['runtime_control_parameters']
    display = package['shared_parameters']['dynamic_display_parameters']
    assert runtime['multi_region_calib'] is True
    assert display['direction_reference_direct'] == 0
    assert display['direction_blend_enabled'] is False
    assert package['multi_region']['deployment_ready'] is False
    assert package['multi_region']['available_deployment_directions'] == []

    end5 = package['regions']['end5cm']
    override = result['regions']['end5cm']['parameters']
    assert end5['weight_score_mode'] == 'group_mean'
    assert end5['weights']['0'] == override['weights']['0']
    assert end5['slopes']['0'] == override['slopes']['0']
    assert end5['weights']['120'] == end5['weights']['0']
    assert end5['weights']['240'] == end5['weights']['0']
    assert end5['slopes']['120'] == end5['slopes']['0']
    assert end5['slopes']['240'] == end5['slopes']['0']
    assert package['provenance']['local_global_phases_set']['end5cm']['0'] == pytest.approx(
        override['global_phases_set'])
    assert package['provenance']['single_direction_demo']['runtime_directions'] == [0]
    assert package['provenance']['single_direction_demo']['base_package']
    assert package['provenance']['single_direction_demo']['override_result']


@pytest.mark.parametrize('mutator, message', [
    (lambda result: result.update({'direct': 120}), 'direct=0'),
    (lambda result: result['regions']['end5cm'].update({'status': 'failed'}), 'complete'),
    (lambda result: result['regions'].update({'full': {}}), 'only end5cm'),
])
def test_single_direction_demo_package_rejects_unsafe_override(mutator, message):
    from tools.sensor_parameter_package import build_single_direction_demo_package

    base, result = _inputs()
    mutator(result)
    with pytest.raises(ValueError, match=message):
        build_single_direction_demo_package(base, result)


def test_single_direction_demo_package_rejects_override_shape_mismatch():
    from tools.sensor_parameter_package import build_single_direction_demo_package

    base, result = _inputs()
    result['regions']['end5cm']['parameters']['weights']['0'] = [1.0]
    with pytest.raises(ValueError, match='weights shape'):
        build_single_direction_demo_package(base, result)


def test_demo_package_parses_as_single_direction_and_multiregion_assembles(tmp_path):
    import main
    from tools.sensor_parameter_package import (
        build_single_direction_demo_package, load_sensor_package, write_sensor_package,
    )
    from reconstructor import Reconstructor

    base, result = _inputs()
    package = build_single_direction_demo_package(base, result)
    path = tmp_path / 'single-direction-demo.json'
    write_sensor_package(package, path)
    loaded = load_sensor_package(path)
    args = main.parse_main_args(['--task', 'demo', '--sensor_params', str(path)])
    context = main.configure_calibration_args(args)
    params = main.optimizer_parameters(args)

    assert args.multi_region_calib is True
    assert args.exp_directs == [0]
    assert args.direction_reference_direct == 0
    assert params['exp_directs'] == [0]
    assert context['global_point_ids'] == list(range(1, 23))

    recon = Reconstructor.__new__(Reconstructor)
    recon.global_point_ids = np.arange(1, 23)
    recon.total_points = 22
    recon.sharpness = 4.8
    recon.min_consecutive = 3
    normalized = recon._normalise_multiregion_parameters(loaded)
    assert normalized['directions'] == [0, 120, 240]
    assert normalized['regions']['end5cm']['weight_score_mode'] == 'group_mean'


def test_demo_accepts_coverage_aware_end5_weights_with_full_runtime_region(tmp_path):
    import main
    from tools.sensor_parameter_package import (
        build_single_direction_demo_package, write_sensor_package,
    )

    base, result = _inputs()
    result['regions']['end5cm']['parameters']['coverage_aware_weights'] = {
        'enabled': True,
        'min_effective_samples': 1.0,
        'min_max_mass': 0.05,
        'policy': 'interpolate_neutral_edges',
    }
    package = build_single_direction_demo_package(base, result)
    path = tmp_path / 'coverage-aware-single-direction-demo.json'
    write_sensor_package(package, path)

    args = main.parse_main_args(['--task', 'demo', '--sensor_params', str(path)])
    context = main.configure_calibration_args(args)

    assert args.optimization_region == 'full'
    assert args.end5cm_coverage_aware_weights is True
    assert context['end5cm_coverage_aware_weights'] is True
