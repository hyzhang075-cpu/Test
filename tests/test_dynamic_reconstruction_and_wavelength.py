import numpy as np
import pytest
import struct
import queue
from collections import deque
from types import SimpleNamespace


def test_wavelength_guard_rejects_one_frame_jump_then_discards_it(capsys):
    from sensor import WavelengthContinuityGuard

    guard = WavelengthContinuityGuard(threshold_nm=0.3)

    assert guard.filter(1001, 1550.0) == pytest.approx(1550.0)
    assert guard.filter(1001, 1550.8) == pytest.approx(1550.0)
    assert guard.filter(1001, 1550.1) == pytest.approx(1550.1)

    output = capsys.readouterr().out
    assert "波长跳变提醒" in output
    assert "sensor_id=1001" in output
    assert "旧值=1550.000000" in output
    assert "新值=1550.800000" in output
    assert "变化量=0.800000" in output


def test_wavelength_guard_accepts_persistent_change_and_is_independent_per_fbg():
    from sensor import WavelengthContinuityGuard

    guard = WavelengthContinuityGuard(threshold_nm=0.3)
    assert guard.filter(1001, 1550.0) == pytest.approx(1550.0)
    assert guard.filter(1002, 1560.0) == pytest.approx(1560.0)

    assert guard.filter(1001, 1550.8) == pytest.approx(1550.0)
    assert guard.filter(1002, 1560.1) == pytest.approx(1560.1)
    assert guard.filter(1001, 1551.6) == pytest.approx(1550.0)
    assert guard.filter(1001, 1551.7) == pytest.approx(1551.7)
    assert guard.filter(1002, 1560.2) == pytest.approx(1560.2)


def test_wavelength_guard_accepts_exact_threshold_and_preserves_last_on_nonfinite():
    from sensor import WavelengthContinuityGuard

    guard = WavelengthContinuityGuard(threshold_nm=0.3)
    assert guard.filter(1001, 1550.0) == pytest.approx(1550.0)
    assert guard.filter(1001, 1550.3) == pytest.approx(1550.3)
    assert guard.filter(1001, float("nan")) == pytest.approx(1550.3)
    assert guard.filter(1001, float("inf")) == pytest.approx(1550.3)


def test_process_buffer_writes_only_guarded_absolute_wavelengths():
    from sensor import Sensor, WavelengthContinuityGuard

    def packet(*samples):
        body = bytearray(struct.pack("<H", len(samples)))
        for sensor_id, wavelength in samples:
            block = bytearray(20)
            struct.pack_into("<H", block, 2, sensor_id)
            struct.pack_into("<f", block, 16, wavelength)
            body.extend(block)
        return bytearray(struct.pack("<I", len(body)) + body)

    sensor = Sensor.__new__(Sensor)
    sensor.buffer = packet((1001, 1550.0), (2001, 1560.0))
    sensor.active_channels = {1: 0, 2: 1}
    sensor.raw_trim_idx = 0
    sensor.total_points = 1
    sensor.current_snapshot = np.zeros((1, 2))
    sensor.zero_points = {1: [None], 2: [None]}
    sensor.is_zero_set = {1: False, 2: False}
    sensor._wavelength_guard = WavelengthContinuityGuard(threshold_nm=0.3)
    sensor.wavelength_jump_guard_enabled = True
    sensor._process_buffer()
    np.testing.assert_allclose(sensor.current_snapshot, [[1550.0, 1560.0]])

    sensor.buffer = packet((1001, 1550.8), (2001, 1560.8))
    sensor._process_buffer()
    np.testing.assert_allclose(sensor.current_snapshot, [[1550.0, 1560.0]])

    sensor.buffer = packet((1001, 1550.1), (2001, 1560.8))
    sensor._process_buffer()
    np.testing.assert_allclose(sensor.current_snapshot, [[1550.1, 1560.8]])


def test_wavelength_jump_threshold_is_a_parser_and_package_compatible_parameter():
    import main
    from tools.sensor_parameter_package import package_parser_defaults

    args = main.parse_main_args([
        "--task", "demo",
        "--wavelength_jump_threshold_pm", "450",
        "--wavelength_jump_guard_enabled", "false",
    ])
    assert args.wavelength_jump_threshold_pm == pytest.approx(450.0)
    assert args.wavelength_jump_guard_enabled is False

    default_args = main.parse_main_args(["--task", "demo"])
    assert default_args.wavelength_jump_threshold_pm == pytest.approx(12000.0)
    assert default_args.wavelength_jump_guard_enabled is True

    package = {
        "shared_parameters": {
            "hardware_parameters": {},
            "calibration_experiment_parameters": {},
            "dynamic_display_parameters": {},
            "reconstruction_parameters": {},
            "initialization_parameters": {},
            "angle_optimization_parameters": {},
            "runtime_control_parameters": {},
        },
        "sensor_id": "legacy",
        "multi_region": {"global_phases_set": 0.0, "rot_ang": 0.0},
        "regions": {},
    }
    defaults = package_parser_defaults(package)
    assert defaults["wavelength_jump_threshold_pm"] == pytest.approx(12000.0)
    assert defaults["wavelength_jump_guard_enabled"] is True


def test_wavelength_guard_default_accepts_12000_pm_boundary_and_rejects_larger_jump():
    from sensor import WavelengthContinuityGuard

    guard = WavelengthContinuityGuard()

    assert guard.filter(1001, 1550.0) == pytest.approx(1550.0)
    assert guard.filter(1001, 1562.0) == pytest.approx(1562.0)
    assert guard.filter(1001, 1574.01) == pytest.approx(1562.0)


def test_sensor_can_disable_wavelength_guard_and_pass_large_jump_unchanged(capsys):
    from sensor import Sensor

    def packet(sensor_id, wavelength):
        body = bytearray(struct.pack("<H", 1))
        block = bytearray(20)
        struct.pack_into("<H", block, 2, sensor_id)
        struct.pack_into("<f", block, 16, wavelength)
        body.extend(block)
        return bytearray(struct.pack("<I", len(body)) + body)

    sensor = Sensor.__new__(Sensor)
    sensor.buffer = packet(1001, 1550.0)
    sensor.active_channels = {1: 0}
    sensor.raw_trim_idx = 0
    sensor.total_points = 1
    sensor.current_snapshot = np.zeros((1, 1))
    sensor.zero_points = {1: [1550.0]}
    sensor.is_zero_set = {1: True}
    sensor.wavelength_jump_guard_enabled = False
    sensor._process_buffer()

    sensor.buffer = packet(1001, 1565.0)
    sensor._process_buffer()

    np.testing.assert_allclose(sensor.current_snapshot, [[1565.0]])
    assert "波长跳变提醒" not in capsys.readouterr().out


def test_dynamic_kalman_filters_local_curvature_vector_components():
    from demonstrator import Demonstrator

    demo = Demonstrator.__new__(Demonstrator)
    demo.demo_kalman_Rk = 1e-4
    demo.demo_kalman_Bk = 1e-5
    demo.kalman_x = None
    demo.kalman_p = None

    first_cur = np.array([1.0, 1.0])
    first_ang = np.zeros(2)
    Demonstrator._apply_curvature_vector_kalman(demo, first_cur, first_ang)
    filtered_cur, filtered_ang = Demonstrator._apply_curvature_vector_kalman(
        demo,
        np.array([2.0, 2.0]), first_ang
    )

    assert demo.kalman_x.shape == (2, 2)
    assert np.all(filtered_cur > 1.0)
    assert np.all(filtered_cur < 2.0)
    np.testing.assert_allclose(filtered_ang, 0.0)


def test_reconstruct_from_filtered_curvature_produces_one_consistent_frame():
    from reconstructor import Reconstructor

    recon = Reconstructor.__new__(Reconstructor)
    recon.frame_rule = "TNN"

    cur_interp = np.array([1.0, 1.2, 1.4])
    ang_interp = np.array([0.0, 0.2, 0.4])
    interp_dist = np.array([0.0, 0.01, 0.02])
    init_t = np.array([1.0, 0.0, 0.0])

    r, t, y, z = recon._reconstruct_from_interpolated_curvature(
        cur_interp, ang_interp, interp_dist, init_t
    )
    expected = recon._parallel_frame(
        kappa=cur_interp,
        angles=ang_interp,
        ss=np.diff(interp_dist),
        init_T=init_t,
        init_N=np.array([0.0, np.cos(ang_interp[0]), np.sin(ang_interp[0])]),
        return_principal_frame=True,
    )

    np.testing.assert_allclose(r, expected[0])
    np.testing.assert_allclose(t, expected[1])
    np.testing.assert_allclose(y, expected[2])
    np.testing.assert_allclose(z, expected[3])

    end_pose = recon._build_end_pose(
        t, y, z, rot_matrix=np.eye(3), rot_ang_deg=0.0
    )
    np.testing.assert_allclose(end_pose, np.vstack((t[-1], y[-1], z[-1])))


def test_demo_kalman_rebuilds_curve_frames_and_anchor_from_filtered_vector():
    from demonstrator import Demonstrator
    from reconstructor import Reconstructor

    class FakeRecon:
        centre_fibre = False
        move_filter = 3
        multi_region_parameters = None
        rot_ang = 0.0
        interp_num = 3
        total_points = 1
        num_channels = 1

        def __init__(self):
            self.data_queue = queue.Queue()
            self.filtered_inputs = None
            self.data_queue.put(np.array([[[0.0]]]))

        def _get_dynamic_parameters(self, calib_Data):
            return None, None

        def _reconstruct_frame(self, **kwargs):
            cur = np.array([1.0, 1.0, 1.0])
            ang = np.zeros(3)
            dist = np.array([0.0, 0.01, 0.02])
            return (
                None,
                None,
                cur,
                dist,
                np.zeros((3, 3)),
                np.tile([1.0, 0.0, 0.0], (3, 1)),
                np.tile([0.0, 1.0, 0.0], (3, 1)),
                np.tile([0.0, 0.0, 1.0], (3, 1)),
                {
                    'magnitude': np.ones(1),
                    'angle': [0.0],
                    'cur_kal': np.ones(1),
                    'ang_filter': np.zeros(1),
                    'cur_interp': cur.copy(),
                    'ang_interp': ang.copy(),
                },
            )

        def _get_rot_x(self, direct=0):
            return np.eye(3)

        def _reconstruct_from_interpolated_curvature(self, cur_interp, ang_interp, interp_dist, init_T):
            self.filtered_inputs = (
                np.asarray(cur_interp).copy(),
                np.asarray(ang_interp).copy(),
            )
            return Reconstructor._reconstruct_from_interpolated_curvature(
                SimpleNamespace(frame_rule='TNN', _parallel_frame=self._parallel_frame),
                cur_interp,
                ang_interp,
                interp_dist,
                init_T,
            )

        def _parallel_frame(self, *args, **kwargs):
            return Reconstructor._parallel_frame(self, *args, **kwargs)

        _build_end_pose = staticmethod(Reconstructor._build_end_pose)

    recon = FakeRecon()
    captured = {}
    demo = SimpleNamespace(
        recon=recon,
        imu=False,
        direction_reference_direct=0,
        unwrap_threshold=0.65,
        align_threshold=0.15,
        angle_prev=None,
        angle_unwrap_prev=None,
        prev_reordered_data=None,
        demo_kalman_enabled=True,
        demo_kalman_Rk=1e-4,
        demo_kalman_Bk=1e-5,
        kalman_x=None,
        kalman_p=None,
        curve_history=deque(maxlen=3),
        recorder=None,
        udp_socket=SimpleNamespace(sendto=lambda *args: None),
    )
    demo._get_dynamic_parameters = recon._get_dynamic_parameters
    demo._apply_curvature_vector_kalman = Demonstrator._apply_curvature_vector_kalman.__get__(demo)
    demo._apply_anchor_constraint_for_frame = lambda curve, t, y, z: (
        captured.update(anchor=(curve.copy(), t.copy(), y.copy(), z.copy())) or
        (curve, {
            'anchor_rotation_matrix': np.eye(3),
            'anchor_enabled': False,
            'insert_value_mm': None,
            'anchor_point_m': None,
        })
    )
    demo._update_frame = lambda curve, end_pose: captured.update(
        displayed=(curve.copy(), end_pose.copy())
    )
    demo._tick_send_stats = lambda: None

    Demonstrator.update_vtk(demo)

    filtered_cur, filtered_ang = recon.filtered_inputs
    expected_r, expected_t, expected_y, expected_z = recon._reconstruct_from_interpolated_curvature(
        filtered_cur,
        filtered_ang,
        np.array([0.0, 0.01, 0.02]),
        np.array([1.0, 0.0, 0.0]),
    )
    expected_end_pose = Reconstructor._build_end_pose(
        expected_t, expected_y, expected_z, np.eye(3), 0.0
    )
    np.testing.assert_allclose(captured['anchor'][0], captured['displayed'][0])
    np.testing.assert_allclose(captured['anchor'][0], expected_r)
    np.testing.assert_allclose(captured['anchor'][1], expected_t)
    np.testing.assert_allclose(captured['anchor'][2], expected_y)
    np.testing.assert_allclose(captured['anchor'][3], expected_z)
    np.testing.assert_allclose(captured['displayed'][1], expected_end_pose)
    np.testing.assert_allclose(demo.recon.cur_interp, filtered_cur)
    np.testing.assert_allclose(demo.kalman_x[:, 0], filtered_cur * np.cos(filtered_ang))


def test_recorder_keeps_filtered_interpolation_as_legacy_fields_and_raw_as_new_fields():
    from demonstrator import DataRecorder

    recorder = DataRecorder.__new__(DataRecorder)
    recorder.running = True
    recorder.queue = queue.Queue()
    filtered_cur = np.array([1.1, 1.2])
    filtered_ang = np.array([0.1, 0.2])
    recorder.save(
        timestamp=1.0,
        r_results=np.zeros((2, 3)),
        end_pose=np.eye(3),
        cur_interp=filtered_cur,
        raw_data=np.zeros((1, 1)),
        intermediates={
            'magnitude': np.ones(1),
            'angle': [0.0],
            'cur_kal': np.ones(1),
            'ang_filter': np.zeros(1),
            'cur_interp': filtered_cur,
            'ang_interp': filtered_ang,
            'cur_interp_raw': np.array([1.0, 1.0]),
            'ang_interp_raw': np.array([0.0, 0.0]),
        },
    )
    packet = recorder.queue.get_nowait()
    assert packet['cur_interp'] == pytest.approx(filtered_cur.tolist())
    assert packet['ang_interp'] == pytest.approx(filtered_ang.tolist())
    assert packet['cur_interp_raw'] == pytest.approx([1.0, 1.0])
    assert packet['ang_interp_raw'] == pytest.approx([0.0, 0.0])
