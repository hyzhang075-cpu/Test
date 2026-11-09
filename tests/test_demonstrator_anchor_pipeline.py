import argparse
import io
import queue
import threading
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace

import numpy as np
import vtk

import demonstrator as demonstrator_module
from entrance_anchor import EntranceAnchorConstraint, apply_entrance_anchor
from demonstrator import DataRecorder, Demonstrator, _build_anchor_marker_segments
from main import add_anchor_arguments


class DemonstratorAnchorPipelineTests(unittest.TestCase):
    def test_anchor_rotation_is_applied_after_end_pose_roll_compensation(self):
        compensated_end_pose = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0],
                [0.0, 1.0, 0.0],
            ]
        )
        anchor_rotation = np.array(
            [
                [0.0, -1.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )

        anchored_end_pose = demonstrator_module._rotate_end_pose_for_anchor(
            compensated_end_pose,
            anchor_rotation,
        )

        np.testing.assert_allclose(
            anchored_end_pose,
            [[0.0, 1.0, 0.0], [0.0, 0.0, -1.0], [-1.0, 0.0, 0.0]],
            atol=1e-12,
        )

    def test_software_shape_removes_positive_x_insertion_only_when_anchor_enabled(self):
        """Anchored JSON output must undo the insertion that receiving software adds."""
        shape_mm = np.array([[200.0, 10.0, -5.0], [250.0, 20.0, -4.0]])

        adjusted = demonstrator_module._shape_for_software_send(
            shape_mm,
            anchor_enabled=True,
            insert_value_mm=156.8,
        )

        np.testing.assert_allclose(adjusted, [[43.2, 10.0, -5.0], [93.2, 20.0, -4.0]])
        np.testing.assert_array_equal(shape_mm, [[200.0, 10.0, -5.0], [250.0, 20.0, -4.0]])

    def test_software_shape_is_unchanged_when_anchor_disabled(self):
        """Existing non-anchored JSON coordinates must remain backward compatible."""
        shape_mm = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]])

        adjusted = demonstrator_module._shape_for_software_send(
            shape_mm,
            anchor_enabled=False,
            insert_value_mm=12.5,
        )

        np.testing.assert_array_equal(adjusted, shape_mm)

    def test_software_shape_ignores_missing_or_invalid_insertion(self):
        """UDP startup and malformed samples must not corrupt outgoing coordinates."""
        shape_mm = np.array([[10.0, 20.0, 30.0]])

        for invalid in (None, np.nan, [1.0, 2.0]):
            with self.subTest(invalid=invalid):
                adjusted = demonstrator_module._shape_for_software_send(
                    shape_mm,
                    anchor_enabled=True,
                    insert_value_mm=invalid,
                )
                np.testing.assert_array_equal(adjusted, shape_mm)

    def test_anchor_point_uses_same_software_coordinates_as_anchored_shape(self):
        anchor_point_m = np.array([0.2, 0.01, -0.005])

        converted = demonstrator_module._anchor_point_for_software_send(
            anchor_point_m,
            anchor_enabled=True,
            insert_value_mm=156.8,
        )

        np.testing.assert_allclose(converted, [43.2, 10.0, -5.0])

    def test_anchor_point_is_absent_without_active_anchor_or_valid_insertion(self):
        anchor_point_m = np.array([0.2, 0.01, -0.005])

        for enabled, insert_value in (
            (False, 156.8),
            (True, None),
            (True, np.nan),
        ):
            with self.subTest(enabled=enabled, insert_value=insert_value):
                self.assertIsNone(
                    demonstrator_module._anchor_point_for_software_send(
                        anchor_point_m,
                        anchor_enabled=enabled,
                        insert_value_mm=insert_value,
                    )
                )

    def test_send_object_includes_software_anchor_point(self):
        intermediates = {
            "magnitude": np.array([1.0]),
            "angle": [0.1],
            "cur_kal": np.array([2.0]),
            "ang_filter": np.array([0.2]),
            "cur_interp": np.array([3.0]),
            "ang_interp": np.array([0.3]),
        }

        send_obj = demonstrator_module._build_send_obj(
            np.eye(3),
            np.zeros((2, 3)),
            np.array([4.0]),
            intermediates,
            anchor_point_mm=np.array([43.2, 10.0, -5.0]),
        )

        self.assertEqual(send_obj["anchor_point"], [43.2, 10.0, -5.0])

    def test_data_recorder_copies_before_after_anchor_curves_and_anchor_point(self):
        recorder = DataRecorder.__new__(DataRecorder)
        recorder.running = True
        recorder.queue = queue.Queue()
        before_anchor = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])
        after_anchor = np.array([[0.2, 0.0, 0.0], [0.3, 0.0, 0.0]])
        anchor_point_m = np.array([0.25, 0.0, 0.0])
        intermediates = {
            "magnitude": np.array([1.0]),
            "angle": [0.1],
            "cur_kal": np.array([2.0]),
            "ang_filter": np.array([0.2]),
            "cur_interp": np.array([3.0]),
            "ang_interp": np.array([0.3]),
        }

        recorder.save(
            timestamp=1.0,
            r_results=after_anchor,
            end_pose=np.eye(3),
            cur_interp=np.array([3.0]),
            raw_data=np.array([4.0]),
            intermediates=intermediates,
            insert_value=156.8,
            r_results_before_anchor=before_anchor,
            anchor_point_m=anchor_point_m,
        )
        packet = recorder.queue.get_nowait()
        before_anchor[:] = -1.0
        after_anchor[:] = -2.0
        anchor_point_m[:] = -3.0

        np.testing.assert_allclose(
            packet["r_results_before_anchor"],
            [[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]],
        )
        np.testing.assert_allclose(
            packet["r_results"],
            [[0.2, 0.0, 0.0], [0.3, 0.0, 0.0]],
        )
        np.testing.assert_allclose(packet["anchor_point_m"], [0.25, 0.0, 0.0])

    def test_anchor_marker_segments_form_four_scaled_3d_diagonals(self):
        segments = _build_anchor_marker_segments(
            anchor_m=np.array([1.0, 2.0, 3.0]),
            scale_factor=10.0,
            half_size=2.0,
        )

        np.testing.assert_array_equal(
            segments,
            np.array(
                [
                    [[8.0, 18.0, 28.0], [12.0, 22.0, 32.0]],
                    [[8.0, 18.0, 32.0], [12.0, 22.0, 28.0]],
                    [[8.0, 22.0, 28.0], [12.0, 18.0, 32.0]],
                    [[8.0, 22.0, 32.0], [12.0, 18.0, 28.0]],
                ]
            ),
        )

    def test_vtk_anchor_marker_tracks_constraint_visibility_and_position(self):
        constraint = EntranceAnchorConstraint(enabled=False)
        harness = SimpleNamespace(
            renderer=vtk.vtkRenderer(),
            entrance_anchor_constraint=constraint,
            entrance_anchor_lock=threading.RLock(),
        )
        Demonstrator.add_anchor_marker(harness)

        self.assertEqual(harness.anchor_marker_actor.GetVisibility(), 0)
        np.testing.assert_allclose(harness.anchor_marker_actor.GetProperty().GetColor(), [1.0, 1.0, 1.0])
        self.assertAlmostEqual(harness.anchor_marker_actor.GetProperty().GetLineWidth(), 3.0)
        self.assertEqual(harness.anchor_marker_points.GetNumberOfPoints(), 8)
        self.assertEqual(harness.anchor_marker_lines.GetNumberOfCells(), 4)

        curve = np.array([[0.0, 0.0, 0.0], [0.20, 0.0, 0.0]])
        Demonstrator._update_anchor_marker(harness, scale_factor=100.0)
        self.assertEqual(harness.anchor_marker_actor.GetVisibility(), 0)

        constraint.configure(enabled=True, entrance_offset_m=0.07)
        constraint.apply(curve, 156.8)
        Demonstrator._update_anchor_marker(harness, scale_factor=100.0)

        self.assertEqual(harness.anchor_marker_actor.GetVisibility(), 1)
        rendered_points = np.array(
            [harness.anchor_marker_points.GetPoint(index) for index in range(8)]
        )
        np.testing.assert_allclose(np.mean(rendered_points, axis=0), [13.0, 0.0, 0.0])

        constraint.configure(enabled=False)
        Demonstrator._update_anchor_marker(harness, scale_factor=100.0)
        self.assertEqual(harness.anchor_marker_actor.GetVisibility(), 0)

    def test_stage_is_noop_when_disabled_and_translates_when_enabled(self):
        curve = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])

        disabled = apply_entrance_anchor(
            EntranceAnchorConstraint(enabled=False),
            curve,
            166.8,
        )
        enabled_state = EntranceAnchorConstraint(enabled=True)
        apply_entrance_anchor(enabled_state, curve, 156.8)
        enabled = apply_entrance_anchor(enabled_state, curve, 166.8)

        np.testing.assert_allclose(disabled, curve)
        np.testing.assert_allclose(enabled[:, 0], [0.01, 0.11])
        np.testing.assert_allclose(enabled[:, 1:], 0.0)

    def test_frame_state_separates_translation_from_rotation_for_downstream_output(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(
                translation_enabled=False,
                rotation_enabled=True,
                entrance_offset_m=1.0,
            ),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=156.8,
        )
        curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        T = np.repeat([[1.0, 0.0, 0.0]], 3, axis=0)
        Y = np.repeat([[0.0, 1.0, 0.0]], 3, axis=0)
        Z = np.repeat([[0.0, 0.0, 1.0]], 3, axis=0)

        _, frame_state = Demonstrator._apply_anchor_constraint_for_frame(
            harness, curve, T, Y, Z
        )

        self.assertTrue(frame_state["anchor_enabled"])
        self.assertFalse(frame_state["anchor_translation_enabled"])
        self.assertTrue(frame_state["anchor_rotation_enabled"])
        np.testing.assert_allclose(frame_state["anchor_point_m"], [1.0, 0.0, 0.0])

    def test_main_anchor_arguments_default_to_6cm_and_accept_override(self):
        parser = argparse.ArgumentParser()
        add_anchor_arguments(parser)

        defaults = parser.parse_args([])
        overridden = parser.parse_args(["--anchor_offset_m", "0.085"])

        self.assertFalse(defaults.anchor_constraint_enabled)
        self.assertFalse(defaults.anchor_translation_enabled)
        self.assertFalse(defaults.anchor_rotation_enabled)
        self.assertAlmostEqual(defaults.anchor_offset_m, 0.06)
        self.assertAlmostEqual(overridden.anchor_offset_m, 0.085)

    def test_main_anchor_switches_are_independent_and_legacy_switch_enables_both(self):
        parser = argparse.ArgumentParser()
        add_anchor_arguments(parser)

        translation_only = parser.parse_args(["--anchor_translation_enabled"])
        rotation_only = parser.parse_args(["--anchor_rotation_enabled"])
        legacy = parser.parse_args(["--anchor_constraint_enabled"])

        self.assertTrue(translation_only.anchor_translation_enabled)
        self.assertFalse(translation_only.anchor_rotation_enabled)
        self.assertFalse(rotation_only.anchor_translation_enabled)
        self.assertTrue(rotation_only.anchor_rotation_enabled)
        self.assertTrue(legacy.anchor_translation_enabled)
        self.assertTrue(legacy.anchor_rotation_enabled)

    def test_main_anchor_arguments_reject_invalid_offset_before_runtime_setup(self):
        parser = argparse.ArgumentParser()
        add_anchor_arguments(parser)

        for invalid in ("-0.01", "nan", "inf"):
            with self.subTest(invalid=invalid), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(["--anchor_offset_m", invalid])

    def test_process_interface_reconfigures_and_applies_under_shared_lock(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(enabled=False),
            entrance_anchor_lock=threading.RLock(),
        )
        curve = np.array([[0.0, 0.0, 0.0], [0.30, 0.0, 0.0]])

        Demonstrator.configure_anchor_constraint(
            harness,
            enabled=True,
            entrance_offset_m=0.08,
        )
        first = Demonstrator._apply_anchor_constraint(harness, curve, 0.0)
        Demonstrator._apply_anchor_constraint(harness, curve, 200.0)
        advanced = Demonstrator._apply_anchor_constraint(harness, curve, 210.0)

        np.testing.assert_allclose(first, curve)
        np.testing.assert_allclose(advanced[:, 0], [0.01, 0.31])
        np.testing.assert_allclose(harness.entrance_anchor_constraint.anchor_m, [0.22, 0.0, 0.0])
        self.assertAlmostEqual(harness.entrance_anchor_constraint.insertion_baseline_mm, 200.0)

    def test_configuration_waits_for_inflight_frame_application(self):
        apply_entered = threading.Event()
        release_apply = threading.Event()
        configure_finished = threading.Event()

        class BlockingConstraint(EntranceAnchorConstraint):
            def apply(self, curve_m, insert_value_mm=None):
                apply_entered.set()
                self.assert_released = release_apply.wait(timeout=2.0)
                return super().apply(curve_m, insert_value_mm)

        constraint = BlockingConstraint(enabled=True)
        harness = SimpleNamespace(
            entrance_anchor_constraint=constraint,
            entrance_anchor_lock=threading.RLock(),
        )
        curve = np.array([[0.0, 0.0, 0.0], [0.30, 0.0, 0.0]])

        apply_thread = threading.Thread(
            target=Demonstrator._apply_anchor_constraint,
            args=(harness, curve, 156.8),
        )
        configure_thread = threading.Thread(
            target=lambda: (
                Demonstrator.configure_anchor_constraint(
                    harness,
                    enabled=True,
                    entrance_offset_m=0.08,
                ),
                configure_finished.set(),
            )
        )
        apply_thread.start()
        self.assertTrue(apply_entered.wait(timeout=1.0))
        configure_thread.start()
        self.assertFalse(configure_finished.wait(timeout=0.05))

        release_apply.set()
        apply_thread.join(timeout=2.0)
        configure_thread.join(timeout=2.0)

        self.assertFalse(apply_thread.is_alive())
        self.assertFalse(configure_thread.is_alive())
        self.assertTrue(constraint.assert_released)
        self.assertTrue(configure_finished.is_set())
        self.assertAlmostEqual(constraint.entrance_offset_m, 0.08)
        self.assertIsNone(constraint.anchor_m)

    def test_udp_anchor_configure_resets_session_and_returns_actual_state(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.06)
        curve = np.array([[0.0, 0.0, 0.0], [0.30, 0.0, 0.0]])
        constraint.apply(curve, 100.0)
        constraint.apply(curve, 110.0)
        harness = SimpleNamespace(
            entrance_anchor_constraint=constraint,
            entrance_anchor_lock=threading.RLock(),
            insert_dis=110.0,
        )

        reply = Demonstrator._dispatch_udp_command(
            harness,
            {
                "cmd": "anchor_configure",
                "request_id": "cfg-1",
                "data": {
                    "enabled": True,
                    "entrance_offset_m": 0.08,
                    "reset": True,
                },
            },
        )

        self.assertEqual(reply["request_id"], "cfg-1")
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["cmd"], "anchor_configure")
        self.assertTrue(reply["state"]["enabled"])
        self.assertAlmostEqual(reply["state"]["entrance_offset_m"], 0.08)
        self.assertFalse(reply["state"]["anchor_initialized"])
        self.assertFalse(reply["state"]["anchor_frame_initialized"])
        self.assertIsNone(reply["state"]["anchor_m"])
        self.assertIsNone(reply["state"]["insertion_baseline_mm"])
        self.assertAlmostEqual(reply["state"]["last_relative_insert_mm"], 0.0)
        self.assertAlmostEqual(reply["state"]["insert_value_mm"], 110.0)

    def test_udp_anchor_configure_accepts_offset_from_reconstructed_tip(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(
                enabled=False,
                entrance_offset_m=0.06,
            ),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=None,
        )

        reply = Demonstrator._handle_udp_datagram(
            harness,
            b'{"cmd":"anchor_configure","request_id":"too-short",'
            b'"data":{"enabled":true,"entrance_offset_m":0.009,"reset":true}}',
        )

        self.assertTrue(reply["ok"])
        self.assertTrue(harness.entrance_anchor_constraint.enabled)
        self.assertAlmostEqual(reply["state"]["entrance_offset_m"], 0.009)
        self.assertAlmostEqual(harness.entrance_anchor_constraint.entrance_offset_m, 0.009)

    def test_udp_anchor_reset_keeps_configuration_and_clears_session(self):
        constraint = EntranceAnchorConstraint(enabled=True, entrance_offset_m=0.06)
        curve = np.array([[0.0, 0.0, 0.0], [0.30, 0.0, 0.0]])
        constraint.apply(curve, 100.0)
        harness = SimpleNamespace(
            entrance_anchor_constraint=constraint,
            entrance_anchor_lock=threading.RLock(),
            insert_dis=100.0,
        )

        reply = Demonstrator._dispatch_udp_command(
            harness,
            {"cmd": "anchor_reset", "request_id": "reset-1"},
        )

        self.assertTrue(reply["ok"])
        self.assertTrue(reply["state"]["enabled"])
        self.assertAlmostEqual(reply["state"]["entrance_offset_m"], 0.06)
        self.assertFalse(reply["state"]["anchor_initialized"])
        self.assertFalse(reply["state"]["anchor_frame_initialized"])
        self.assertIsNone(reply["state"]["insertion_baseline_mm"])

    def test_udp_status_datagram_returns_json_serialisable_state(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(enabled=False),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=None,
        )

        reply = Demonstrator._handle_udp_datagram(
            harness,
            b'{"cmd":"anchor_status","request_id":"status-1"}',
        )

        self.assertTrue(reply["ok"])
        self.assertEqual(reply["request_id"], "status-1")
        self.assertFalse(reply["state"]["enabled"])

    def test_malformed_udp_datagram_returns_error_instead_of_stopping_receiver(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(enabled=False),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=None,
        )

        reply = Demonstrator._handle_udp_datagram(harness, b'{invalid json')

        self.assertFalse(reply["ok"])
        self.assertEqual(reply["cmd"], None)
        self.assertIn("JSON", reply["error"])

    def test_udp_config_rejects_string_offset_without_changing_state(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(
                enabled=False,
                entrance_offset_m=0.06,
            ),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=None,
        )

        reply = Demonstrator._handle_udp_datagram(
            harness,
            b'{"cmd":"anchor_configure","request_id":"bad-1",'
            b'"data":{"enabled":true,"entrance_offset_m":"0.07","reset":true}}',
        )

        self.assertFalse(reply["ok"])
        self.assertEqual(reply["request_id"], "bad-1")
        self.assertFalse(harness.entrance_anchor_constraint.enabled)
        self.assertAlmostEqual(harness.entrance_anchor_constraint.entrance_offset_m, 0.06)

    def test_udp_insert_rejects_boolean_and_string_values(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(enabled=False),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=12.0,
        )

        for invalid_datagram in (
            b'{"cmd":"insert_dis","data":true}',
            b'{"cmd":"insert_dis","data":"12.5"}',
        ):
            with self.subTest(invalid_datagram=invalid_datagram):
                reply = Demonstrator._handle_udp_datagram(harness, invalid_datagram)
                self.assertFalse(reply["ok"])
                self.assertEqual(harness.insert_dis, 12.0)

    def test_frame_anchor_snapshot_remains_consistent_after_reconfigure(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(
                enabled=True,
                entrance_offset_m=0.06,
            ),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=100.0,
        )
        curve = np.array([[0.0, 0.0, 0.0], [0.20, 0.0, 0.0]])

        anchored, frame_state = Demonstrator._apply_anchor_constraint_for_frame(
            harness,
            curve,
        )
        Demonstrator._dispatch_udp_command(
            harness,
            {
                "cmd": "anchor_configure",
                "data": {"enabled": False, "reset": True},
            },
        )
        Demonstrator._dispatch_udp_command(
            harness,
            {"cmd": "insert_dis", "data": 200.0},
        )

        np.testing.assert_allclose(anchored, curve)
        self.assertTrue(frame_state["anchor_enabled"])
        self.assertEqual(frame_state["insert_value_mm"], 100.0)
        np.testing.assert_allclose(
            frame_state["anchor_rotation_matrix"],
            np.eye(3),
            atol=1e-12,
        )

    def test_frame_stage_returns_rotation_that_aligns_curve_and_end_pose(self):
        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(
                enabled=True,
                entrance_offset_m=1.0,
            ),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=None,
        )
        reference_curve = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        reference_frames = (
            np.repeat([[1.0, 0.0, 0.0]], 3, axis=0),
            np.repeat([[0.0, 1.0, 0.0]], 3, axis=0),
            np.repeat([[0.0, 0.0, 1.0]], 3, axis=0),
        )
        Demonstrator._apply_anchor_constraint_for_frame(
            harness,
            reference_curve,
            *reference_frames,
        )
        current_curve = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 2.0, 0.0]]
        )
        current_frames = (
            np.repeat([[0.0, 1.0, 0.0]], 3, axis=0),
            np.repeat([[-1.0, 0.0, 0.0]], 3, axis=0),
            np.repeat([[0.0, 0.0, 1.0]], 3, axis=0),
        )

        anchored_curve, frame_state = Demonstrator._apply_anchor_constraint_for_frame(
            harness,
            current_curve,
            *current_frames,
        )

        np.testing.assert_allclose(anchored_curve, reference_curve, atol=1e-12)
        np.testing.assert_allclose(
            frame_state["anchor_rotation_matrix"],
            [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            atol=1e-12,
        )
        state = Demonstrator._get_anchor_constraint_state(harness)
        self.assertTrue(state["anchor_frame_initialized"])
        np.testing.assert_allclose(state["anchor_frame"], np.eye(3), atol=1e-12)

    def test_udp_control_receiver_does_not_send_ack_or_nack_datagrams(self):
        class ReceiveSocket:
            def __init__(self, harness):
                self.harness = harness
                self.recv_count = 0
                self.send_count = 0

            def settimeout(self, timeout):
                pass

            def recvfrom(self, size):
                self.recv_count += 1
                if self.recv_count == 1:
                    return b'{"cmd":"anchor_status","request_id":"status-1"}', ("127.0.0.1", 50001)
                self.harness.udp_running = False
                raise OSError("receiver stopping")

            def sendto(self, data, addr):
                self.send_count += 1

        harness = SimpleNamespace(
            entrance_anchor_constraint=EntranceAnchorConstraint(enabled=False),
            entrance_anchor_lock=threading.RLock(),
            insert_dis=None,
            udp_running=True,
        )
        harness._handle_udp_datagram = lambda data: Demonstrator._handle_udp_datagram(harness, data)
        harness.udp_socket = ReceiveSocket(harness)

        Demonstrator._receive_udp_data(harness)

        self.assertEqual(harness.udp_socket.send_count, 0)

    def test_runtime_shutdown_stops_udp_thread_recorder_and_socket(self):
        class Resource:
            def __init__(self):
                self.stopped = False
                self.closed = False
                self.joined = False

            def stop(self):
                self.stopped = True

            def close(self):
                self.closed = True

            def join(self, timeout=None):
                self.joined = True

        recorder = Resource()
        udp_socket = Resource()
        udp_thread = Resource()
        harness = SimpleNamespace(
            udp_running=True,
            recorder=recorder,
            udp_socket=udp_socket,
            udp_thread=udp_thread,
        )

        Demonstrator._shutdown_runtime_resources(harness)

        self.assertFalse(harness.udp_running)
        self.assertTrue(recorder.stopped)
        self.assertTrue(udp_socket.closed)
        self.assertTrue(udp_thread.joined)


if __name__ == "__main__":
    unittest.main()
