"""Independently switchable position and tangent anchoring for fibre curves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.spatial.transform import Rotation, Slerp


@dataclass(frozen=True)
class AnchorConstraintResult:
    """One frame of anchor output plus diagnostics used by live and replay paths."""

    curve_m: np.ndarray
    applied: bool
    anchor_m: Optional[np.ndarray]
    source_point_m: Optional[np.ndarray]
    anchored_point_m: Optional[np.ndarray]
    translation_m: np.ndarray
    rotation_matrix: np.ndarray
    anchor_frame: Optional[np.ndarray]
    source_frame: Optional[np.ndarray]
    relative_insert_mm: float
    requested_distance_m: float
    used_distance_m: float
    clamped: bool


class EntranceAnchorConstraint:
    """Optionally stabilize a curve's entrance position, tangent, or both."""

    def __init__(
        self,
        enabled=None,
        entrance_offset_m: float = 0.06,
        translation_enabled=None,
        rotation_enabled=None,
    ):
        """
        创建入口锚定器并初始化一段新的锚定会话。

        `entrance_offset_m` 是从光纤末端沿中心线反向量取的入口距离（m）。
        `translation_enabled` 与 `rotation_enabled` 可分别控制入口位置固定和
        切向固定；旧参数 `enabled` 仅用于同时控制两者。
        """
        entrance_offset_m = float(entrance_offset_m)
        if not np.isfinite(entrance_offset_m) or entrance_offset_m < 0.0:
            raise ValueError("entrance_offset_m must be a finite nonnegative value")

        legacy_enabled = False if enabled is None else bool(enabled)
        self.translation_enabled = (
            legacy_enabled
            if translation_enabled is None
            else bool(translation_enabled)
        )
        self.rotation_enabled = (
            legacy_enabled
            if rotation_enabled is None
            else bool(rotation_enabled)
        )
        self.entrance_offset_m = entrance_offset_m
        self.anchor_m = None
        self.anchor_frame = None
        self.anchor_tangent = None
        self.insertion_baseline_mm = None
        self.last_relative_insert_mm = 0.0

    @property
    def enabled(self):
        """返回兼容性总开关：平移或旋转任一启用即视为已启用锚定。"""
        return self.translation_enabled or self.rotation_enabled

    @enabled.setter
    def enabled(self, value):
        """兼容旧接口，用同一个布尔值同时设置平移锚定和旋转锚定。"""
        value = bool(value)
        self.translation_enabled = value
        self.rotation_enabled = value

    def configure(
        self,
        enabled=None,
        entrance_offset_m=None,
        reset=True,
        translation_enabled=None,
        rotation_enabled=None,
    ):
        """
        原子更新运行时开关及入口距离，并可清空已捕获的锚定状态。

        所有新值先完成转换和校验，再统一写回，避免无效入口距离造成部分配置
        已生效。`reset=True` 时会清除固定入口、参考切向和推进量基线，使下一帧
        重新捕获锚定参考。
        """
        new_translation_enabled = self.translation_enabled
        new_rotation_enabled = self.rotation_enabled
        if enabled is not None:
            new_translation_enabled = bool(enabled)
            new_rotation_enabled = bool(enabled)
        if translation_enabled is not None:
            new_translation_enabled = bool(translation_enabled)
        if rotation_enabled is not None:
            new_rotation_enabled = bool(rotation_enabled)
        new_offset_m = self.entrance_offset_m
        if entrance_offset_m is not None:
            new_offset_m = float(entrance_offset_m)
            if not np.isfinite(new_offset_m) or new_offset_m < 0.0:
                raise ValueError("entrance_offset_m must be a finite nonnegative value")

        self.translation_enabled = new_translation_enabled
        self.rotation_enabled = new_rotation_enabled
        self.entrance_offset_m = new_offset_m
        if reset:
            self.anchor_m = None
            self.anchor_frame = None
            self.anchor_tangent = None
            self.insertion_baseline_mm = None
            self.last_relative_insert_mm = 0.0

    @staticmethod
    def _validate_curve(curve_m):
        """将输入转换为浮点曲线，并验证其为至少两个有限三维点。"""
        curve = np.asarray(curve_m, dtype=float)
        if curve.ndim != 2 or curve.shape[1] != 3 or len(curve) < 2:
            raise ValueError(f"curve_m must have shape (N, 3) with N >= 2, got {curve.shape}")
        if not np.all(np.isfinite(curve)):
            raise ValueError("curve_m must contain only finite values")
        return curve

    @staticmethod
    def _next_insertion_state(insert_value_mm, baseline_mm, last_relative_mm):
        """
        根据机械臂绝对推进量更新本会话的相对推进状态。

        缺失、非有限或零值均沿用上一有效相对推进量；会话中首个非零值只用作
        基线，因此返回的相对推进量为 0 mm。后续值减去该基线得到相对推进量。
        """
        if insert_value_mm is None:
            # 没有新测量时冻结上一状态，避免锚点因通信空帧跳动。
            return last_relative_mm, baseline_mm, last_relative_mm

        values = np.asarray(insert_value_mm, dtype=float).reshape(-1)
        if values.size != 1 or not np.isfinite(values[0]):
            return last_relative_mm, baseline_mm, last_relative_mm

        current_mm = float(values[0])
        if abs(current_mm) <= np.finfo(float).eps:
            # 设备以 0 表示尚未获得有效推进量，不能用它覆盖已建立的基线。
            return last_relative_mm, baseline_mm, last_relative_mm

        if baseline_mm is None:
            # 首个非零绝对读数定义本次锚定会话的零推进位置。
            return 0.0, current_mm, 0.0
        relative_mm = current_mm - baseline_mm
        return relative_mm, baseline_mm, relative_mm

    @staticmethod
    def _point_from_tip(curve, requested_distance_m):
        """
        沿折线中心线从末端反向查找指定弧长处的三维点。

        返回入口点、所在段索引、从该段末端量起的比例、实际使用距离及是否因
        超出总长而截断。零长度线段会跳过，超过曲线总长时固定到首点。
        """
        segment_vectors = np.diff(curve, axis=0)
        segment_lengths = np.linalg.norm(segment_vectors, axis=1)
        total_length = float(np.sum(segment_lengths))
        # 将请求距离限制在真实曲线长度内，保证后续反向遍历一定可定位。
        used_distance = float(np.clip(requested_distance_m, 0.0, total_length))
        remaining = used_distance

        if remaining <= np.finfo(float).eps:
            return (
                curve[-1].copy(),
                len(curve) - 2,
                0.0,
                used_distance,
                requested_distance_m > total_length,
            )

        for segment_index in range(len(segment_lengths) - 1, -1, -1):
            segment_length = float(segment_lengths[segment_index])
            if segment_length <= np.finfo(float).eps:
                continue
            if remaining <= segment_length:
                end = curve[segment_index + 1]
                start = curve[segment_index]
                fraction_from_end = remaining / segment_length
                # 在命中的折线段内按弧长比例线性插值得到真实入口坐标。
                point = end + fraction_from_end * (start - end)
                return (
                    point,
                    segment_index,
                    fraction_from_end,
                    used_distance,
                    requested_distance_m > total_length,
                )
            remaining -= segment_length

        return curve[0].copy(), 0, 1.0, used_distance, requested_distance_m > total_length

    @staticmethod
    def _validate_frames(curve, T, Y, Z):
        """
        校验逐点局部 T/Y/Z 标架与曲线形状一致且数值有限。

        三个方向必须同时提供；全部省略表示当前调用不进行旋转锚定。
        """
        if T is None and Y is None and Z is None:
            return None
        if T is None or Y is None or Z is None:
            raise ValueError("T, Y and Z must be provided together")

        frames = tuple(np.asarray(axis, dtype=float) for axis in (T, Y, Z))
        for name, axis in zip(("T", "Y", "Z"), frames):
            if axis.shape != curve.shape:
                raise ValueError(f"{name} must have shape {curve.shape}, got {axis.shape}")
            if not np.all(np.isfinite(axis)):
                raise ValueError(f"{name} must contain only finite values")
        return frames

    @staticmethod
    def _project_to_rotation(matrix):
        """
        用 SVD 将带有数值误差的局部标架投影到最近的右手正交旋转矩阵。

        奇异或左手标架没有稳定、物理有效的旋转含义，因此直接拒绝。
        """
        u, singular_values, vt = np.linalg.svd(matrix)
        scale = max(float(singular_values[0]), 1.0)
        if singular_values[-1] <= 1e-6 * scale or np.linalg.det(matrix) <= 0.0:
            raise ValueError("local T/Y/Z frame is degenerate or left-handed")
        correction = np.eye(3)
        correction[-1, -1] = np.linalg.det(u @ vt)
        # 最后一轴的符号修正确保结果行列式为 +1，即属于 SO(3)。
        return u @ correction @ vt

    @classmethod
    def _frame_at_location(cls, frames, segment_index, fraction_from_end):
        """在入口所在折线段两端标架之间做 SO(3) 球面插值。"""
        T, Y, Z = frames
        start_frame = np.column_stack(
            (T[segment_index], Y[segment_index], Z[segment_index])
        )
        end_frame = np.column_stack(
            (T[segment_index + 1], Y[segment_index + 1], Z[segment_index + 1])
        )
        start_frame = cls._project_to_rotation(start_frame)
        end_frame = cls._project_to_rotation(end_frame)
        rotations = Rotation.from_matrix(np.stack((start_frame, end_frame)))
        fraction_from_start = 1.0 - fraction_from_end
        # Slerp 在旋转群上插值，避免逐轴线性插值破坏正交性。
        return Slerp([0.0, 1.0], rotations)([fraction_from_start]).as_matrix()[0]

    @staticmethod
    def _tangent_at_location(T, segment_index, fraction_from_end):
        """在入口所在折线段对 T 做球面插值，仅让切向数据参与旋转锚定。"""
        start = np.asarray(T[segment_index], dtype=float)
        end = np.asarray(T[segment_index + 1], dtype=float)
        start_norm = float(np.linalg.norm(start))
        end_norm = float(np.linalg.norm(end))
        if start_norm <= np.finfo(float).eps or end_norm <= np.finfo(float).eps:
            raise ValueError("entrance segment tangents must be non-zero")
        start /= start_norm
        end /= end_norm

        fraction_from_start = 1.0 - fraction_from_end
        dot = float(np.clip(np.dot(start, end), -1.0, 1.0))
        if dot < -1.0 + 1e-12:
            # 相反切向之间没有唯一的最短插值路径，不能凭 Y/Z 人为决定滚转方向。
            raise ValueError("entrance segment tangents are antiparallel")
        if dot > 1.0 - 1e-12:
            tangent = fraction_from_end * start + fraction_from_start * end
        else:
            angle = float(np.arccos(dot))
            sin_angle = float(np.sin(angle))
            tangent = (
                np.sin(fraction_from_end * angle) / sin_angle * start
                + np.sin(fraction_from_start * angle) / sin_angle * end
            )
        norm = float(np.linalg.norm(tangent))
        if norm <= np.finfo(float).eps:
            raise ValueError("interpolated entrance tangent is degenerate")
        return tangent / norm

    @staticmethod
    def _rotation_aligning_tangents(source_tangent, anchor_tangent):
        """
        构造将当前 T 对齐到参考 T 的最小旋转，不施加任何绕 T 的滚转。

        一般情况使用 Rodrigues 公式，旋转轴为两个切向的叉积；平行时不旋转。
        反平行时最小旋转轴不唯一，因此从全局坐标轴中确定性选择一个与 T
        最垂直的方向来构造 180 度旋转，避免帧间随机跳变。
        """
        source = np.asarray(source_tangent, dtype=float)
        target = np.asarray(anchor_tangent, dtype=float)
        if source.shape != (3,) or target.shape != (3,):
            raise ValueError("source_tangent and anchor_tangent must have shape (3,)")
        if not np.all(np.isfinite(source)) or not np.all(np.isfinite(target)):
            raise ValueError("source_tangent and anchor_tangent must be finite")

        source_norm = float(np.linalg.norm(source))
        target_norm = float(np.linalg.norm(target))
        if source_norm <= np.finfo(float).eps or target_norm <= np.finfo(float).eps:
            raise ValueError("source_tangent and anchor_tangent must be non-zero")
        source = source / source_norm
        target = target / target_norm

        cross = np.cross(source, target)
        sin_angle = float(np.linalg.norm(cross))
        cos_angle = float(np.clip(np.dot(source, target), -1.0, 1.0))
        tolerance = 1e-12
        if sin_angle > tolerance:
            # 这里的 skew(cross) 已包含 sin(theta)，可直接使用 Rodrigues 公式。
            skew = np.array(
                [
                    [0.0, -cross[2], cross[1]],
                    [cross[2], 0.0, -cross[0]],
                    [-cross[1], cross[0], 0.0],
                ]
            )
            return (
                np.eye(3)
                + skew
                + (skew @ skew) * ((1.0 - cos_angle) / (sin_angle ** 2))
            )
        if cos_angle > 0.0:
            return np.eye(3, dtype=float)

        basis = np.zeros(3, dtype=float)
        basis[int(np.argmin(np.abs(source)))] = 1.0
        axis = np.cross(source, basis)
        axis /= np.linalg.norm(axis)
        # 180 度时 Rodrigues 公式化简为 2*a*a^T-I，轴 a 始终垂直于 T。
        return 2.0 * np.outer(axis, axis) - np.eye(3)

    def apply(self, curve_m, insert_value_mm=None, T=None, Y=None, Z=None):
        """
        对单帧曲线实施入口位置锚定、切向锚定或二者组合。

        曲线和入口距离使用 m，`insert_value_mm` 使用 mm。首次有效帧会捕获固定
        入口/切向；后续帧先把当前入口平移到固定入口，再绕入口作无滚转的
        最小旋转，将当前 T 对齐到固定 T。
        返回结果同时包含变换后的曲线和本帧诊断量，不会原地修改输入曲线。
        """
        curve = self._validate_curve(curve_m)
        if not self.enabled:
            return AnchorConstraintResult(
                curve_m=curve.copy(),
                applied=False,
                anchor_m=None,
                source_point_m=None,
                anchored_point_m=None,
                translation_m=np.zeros(3, dtype=float),
                rotation_matrix=np.eye(3, dtype=float),
                anchor_frame=None,
                source_frame=None,
                relative_insert_mm=0.0,
                requested_distance_m=0.0,
                used_distance_m=0.0,
                clamped=False,
            )

        frames = (
            self._validate_frames(curve, T, Y, Z)
            if self.rotation_enabled
            else None
        )
        recapture_joint_session = (
            frames is not None
            and self.translation_enabled
            and self.anchor_m is not None
            and self.anchor_tangent is None
        )
        # 从“仅平移”切换到联合锚定时重新捕获成套参考，避免位置与切向来自不同帧。
        anchor_m = None if recapture_joint_session else self.anchor_m
        anchor_frame = None if recapture_joint_session else self.anchor_frame
        anchor_tangent = None if recapture_joint_session else self.anchor_tangent
        baseline_mm = None if recapture_joint_session else self.insertion_baseline_mm
        last_relative_mm = 0.0 if recapture_joint_session else self.last_relative_insert_mm

        (
            relative_insert_mm,
            baseline_mm,
            last_relative_mm,
        ) = self._next_insertion_state(
            insert_value_mm,
            baseline_mm,
            last_relative_mm,
        )
        requested_distance_m = max(
            0.0,
            self.entrance_offset_m + relative_insert_mm / 1000.0,
        )
        (
            source_point_m,
            segment_index,
            fraction_from_end,
            used_distance_m,
            clamped,
        ) = self._point_from_tip(
            curve,
            requested_distance_m,
        )
        if self.translation_enabled and anchor_m is None:
            # 第一帧固定入口必须落在真实光纤中心线上：复用反向三维弧长
            # 插值得到的入口点，而不是假设光纤始终沿全局 X 方向延伸。
            anchor_m = source_point_m.copy()
        if not self.translation_enabled:
            anchor_m = None

        source_frame = None
        rotation_matrix = np.eye(3, dtype=float)
        if frames is not None:
            source_frame = self._frame_at_location(
                frames,
                segment_index,
                fraction_from_end,
            )
            source_tangent = self._tangent_at_location(
                frames[0],
                segment_index,
                fraction_from_end,
            )
            if anchor_frame is None:
                # 保留完整标架只用于现有状态/诊断接口；旋转只使用其 T 列。
                anchor_frame = source_frame.copy()
            if anchor_tangent is None:
                # 参考 T 独立保存，确保非正交或滚转变化的 Y/Z 不会污染锚定方向。
                anchor_tangent = source_tangent.copy()
            rotation_matrix = self._rotation_aligning_tangents(
                source_tangent,
                anchor_tangent,
            )

        # 平移量把当前入口送到固定入口；未启用平移时保持零向量。
        translation_m = (
            anchor_m - source_point_m
            if self.translation_enabled
            else np.zeros(3, dtype=float)
        )
        translated_curve = curve + translation_m
        # 联合锚定绕固定入口旋转；仅旋转模式则绕当前入口旋转，入口位置不移动。
        rotation_pivot_m = anchor_m if self.translation_enabled else source_point_m
        anchored_curve = (
            (translated_curve - rotation_pivot_m) @ rotation_matrix.T
            + rotation_pivot_m
        )
        anchored_point_m = (
            (source_point_m + translation_m - rotation_pivot_m) @ rotation_matrix.T
            + rotation_pivot_m
        )

        # 只有整帧几何计算成功后才提交会话状态，异常帧不会留下半更新状态。
        self.anchor_m = anchor_m
        self.anchor_frame = anchor_frame
        self.anchor_tangent = anchor_tangent
        self.insertion_baseline_mm = baseline_mm
        self.last_relative_insert_mm = last_relative_mm

        return AnchorConstraintResult(
            curve_m=anchored_curve,
            applied=True,
            anchor_m=None if anchor_m is None else anchor_m.copy(),
            source_point_m=source_point_m,
            anchored_point_m=anchored_point_m,
            translation_m=translation_m,
            rotation_matrix=rotation_matrix,
            anchor_frame=None if anchor_frame is None else anchor_frame.copy(),
            source_frame=None if source_frame is None else source_frame.copy(),
            relative_insert_mm=relative_insert_mm,
            requested_distance_m=requested_distance_m,
            used_distance_m=used_distance_m,
            clamped=clamped,
        )


def apply_entrance_anchor(constraint, curve_m, insert_value_mm=None, T=None, Y=None, Z=None):
    """
    调用共享入口锚定阶段，并为旧调用方仅返回变换后的曲线数组。

    未提供 T/Y/Z 时走仅曲线的兼容调用；提供标架时三个方向必须成套传入，
    具体校验与状态更新由 `EntranceAnchorConstraint.apply` 完成。
    """
    if not isinstance(constraint, EntranceAnchorConstraint):
        raise TypeError("constraint must be an EntranceAnchorConstraint")
    if T is None and Y is None and Z is None:
        return constraint.apply(curve_m, insert_value_mm).curve_m
    return constraint.apply(curve_m, insert_value_mm, T, Y, Z).curve_m
