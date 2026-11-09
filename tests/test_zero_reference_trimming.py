import json

import numpy as np
import pytest

from sensor import Sensor


def _sensor_with_one_pre_zero_point():
    sensor = Sensor.__new__(Sensor)
    sensor.interrogator = 'FiberTecc'
    sensor.ideal_len = 1.0
    sensor.sensor_id = '08B5_NeTi'
    sensor.active_channels = {1: 0, 2: 1}
    sensor.generate_samp_dist(
        reverse=False, start_value=-5, end_value=5, straight_trim=0.0,
        samp_dist_preset=list(range(0, 220, 10)),
        samp_dist_preset_sub=None, interlaced_grating=False,
    )
    sensor.total_points = len(sensor.samp_dist)
    sensor.zero_points = {channel: [None] * sensor.total_points for channel in sensor.active_channels}
    sensor.is_zero_set = {channel: False for channel in sensor.active_channels}
    return sensor


def _write_reference(path, point_count):
    path.write_text(json.dumps({
        'format_version': 1,
        'sensor_id': '08B5_NeTi',
        'active_channels': [1, 2],
        'point_count': point_count,
        'channels': {
            '1': {'wavelengths_nm': (1500 + np.arange(point_count)).tolist()},
            '2': {'wavelengths_nm': (1600 + np.arange(point_count)).tolist()},
        },
    }), encoding='utf-8')


def test_raw_22_point_zero_reference_uses_same_prefix_crop_as_sensor(tmp_path):
    sensor = _sensor_with_one_pre_zero_point()
    reference_path = tmp_path / 'zero.json'
    _write_reference(reference_path, 22)

    assert sensor.raw_trim_idx == 1
    assert sensor.total_points == 21
    sensor._configure_zero_reference(True, reference_path)

    assert sensor.zero_points[1] == list(range(1501, 1522))
    assert sensor.zero_points[2] == list(range(1601, 1622))
    assert sensor.is_zero_set == {1: True, 2: True}


def test_already_trimmed_zero_reference_is_not_trimmed_twice(tmp_path):
    sensor = _sensor_with_one_pre_zero_point()
    reference_path = tmp_path / 'zero.json'
    _write_reference(reference_path, 21)

    sensor._configure_zero_reference(True, reference_path)

    assert sensor.zero_points[1] == list(range(1500, 1521))


def test_zero_reference_rejects_unrelated_point_count(tmp_path):
    sensor = _sensor_with_one_pre_zero_point()
    reference_path = tmp_path / 'zero.json'
    _write_reference(reference_path, 23)

    with pytest.raises(ValueError, match='零状态栅点数量不一致'):
        sensor._configure_zero_reference(True, reference_path)
