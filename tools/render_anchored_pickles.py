"""Render translation-only bronchial entrance anchored Pickle recordings."""

from __future__ import annotations

import argparse
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from entrance_anchor import EntranceAnchorConstraint


matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"]

from matplotlib import pyplot as plt
from matplotlib.animation import FFMpegWriter
import plotly.graph_objects as go


@dataclass(frozen=True)
class AnchoredPickleData:
    """保存一份 Pickle 经逐帧入口锚定后的曲线、推进量和误差诊断数据。"""

    source_path: Path
    times_s: np.ndarray
    shapes_m: np.ndarray
    raw_inserts_mm: np.ndarray
    relative_inserts_mm: np.ndarray
    anchor_m: np.ndarray
    insertion_baseline_mm: float
    requested_distances_m: np.ndarray
    used_distances_m: np.ndarray
    clamped: np.ndarray
    anchor_residuals_m: np.ndarray


def _scalar_insert_or_none(value, path, frame_index):
    """把单帧推进量规范为有限浮点标量；缺失值保留为 None。"""
    if value is None:
        return None
    values = np.asarray(value, dtype=float).reshape(-1)
    if values.size != 1 or not np.isfinite(values[0]):
        raise ValueError(f"{path} frame {frame_index} insert_value must be a finite scalar or None")
    return float(values[0])


def load_anchored_pickle(path):
    """
    读取一份 Demonstrator Pickle 流并逐帧应用共享的入口平移锚定。

    每帧曲线要求为 N×3（兼容旧的 60 点和当前默认的 120 点）且单位为 m，推进量单位为 mm。返回值包含相对时间、
    锚定曲线、推进量基线、弧长截断标志及入口残差，便于绘图和质量检查。
    """
    path = Path(path)
    # 离线回放与实时流程复用同一约束类，避免两条路径的锚定算法发生偏差。
    constraint = EntranceAnchorConstraint(enabled=True)
    timestamps = []
    shapes = []
    raw_inserts = []
    relative_inserts = []
    requested_distances = []
    used_distances = []
    clamped = []
    residuals = []
    point_count = None

    with path.open("rb") as stream:
        frame_index = 0
        while True:
            try:
                frame = pickle.load(stream)
            except EOFError:
                break
            except Exception as exc:
                raise ValueError(f"{path} frame {frame_index + 1} could not be unpickled: {exc}") from exc

            frame_index += 1
            if not isinstance(frame, dict):
                raise ValueError(f"{path} frame {frame_index} must be a dictionary")
            missing = [key for key in ("timestamp", "r_results", "insert_value") if key not in frame]
            if missing:
                raise ValueError(f"{path} frame {frame_index} missing fields: {', '.join(missing)}")

            timestamp = float(frame["timestamp"])
            if not np.isfinite(timestamp):
                raise ValueError(f"{path} frame {frame_index} timestamp must be finite")
            shape = np.asarray(frame["r_results"], dtype=float)
            if shape.ndim != 2 or shape.shape[1] != 3 or shape.shape[0] < 2:
                raise ValueError(
                    f"{path} frame {frame_index} r_results must have shape (N, 3), got {shape.shape}"
                )
            if point_count is None:
                point_count = shape.shape[0]
            elif shape.shape[0] != point_count:
                raise ValueError(
                    f"{path} frame {frame_index} r_results point count must remain {point_count}, got {shape.shape[0]}"
                )
            if not np.all(np.isfinite(shape)):
                raise ValueError(f"{path} frame {frame_index} r_results contains NaN or inf")

            raw_insert = _scalar_insert_or_none(frame["insert_value"], path, frame_index)
            # 按原始时间顺序调用有状态约束器，使推进量基线和固定入口跨帧延续。
            result = constraint.apply(shape, raw_insert)

            timestamps.append(timestamp)
            shapes.append(result.curve_m)
            raw_inserts.append(np.nan if raw_insert is None else raw_insert)
            relative_inserts.append(result.relative_insert_mm)
            requested_distances.append(result.requested_distance_m)
            used_distances.append(result.used_distance_m)
            clamped.append(result.clamped)
            residuals.append(float(np.linalg.norm(result.anchored_point_m - result.anchor_m)))

    if not shapes:
        raise ValueError(f"no frames found in {path}")
    if constraint.insertion_baseline_mm is None:
        raise ValueError(f"{path} has no finite non-zero insert_value baseline")

    timestamp_array = np.asarray(timestamps, dtype=float)
    # 以首帧为 0 秒，绘图和视频无需依赖记录时使用的绝对时钟原点。
    times_s = timestamp_array - timestamp_array[0]
    if np.any(np.diff(times_s) < 0.0):
        raise ValueError(f"{path} timestamps are not monotonic")

    return AnchoredPickleData(
        source_path=path,
        times_s=times_s,
        shapes_m=np.stack(shapes),
        raw_inserts_mm=np.asarray(raw_inserts, dtype=float),
        relative_inserts_mm=np.asarray(relative_inserts, dtype=float),
        anchor_m=np.asarray(constraint.anchor_m, dtype=float),
        insertion_baseline_mm=float(constraint.insertion_baseline_mm),
        requested_distances_m=np.asarray(requested_distances, dtype=float),
        used_distances_m=np.asarray(used_distances, dtype=float),
        clamped=np.asarray(clamped, dtype=bool),
        anchor_residuals_m=np.asarray(residuals, dtype=float),
    )


def output_paths_for(trajectory_output, video_output, source_path):
    """根据源 Pickle 文件名生成互不覆盖的 PNG、HTML、普通视角和俯视 MP4 路径。"""
    stem = Path(source_path).stem
    png_path = Path(trajectory_output) / f"{stem}_anchored_tip_trajectory.png"
    html_path = Path(trajectory_output) / f"{stem}_anchored_tip_trajectory.html"
    video_path = Path(video_output) / stem / f"{stem}_anchored_full.mp4"
    top_video_path = Path(video_output) / stem / f"{stem}_anchored_top_view.mp4"
    return png_path, html_path, video_path, top_video_path


def video_render_specs(video_path, top_video_path):
    """返回普通三维视角和俯视视角各自的输出路径、仰角与方位角。"""
    return (
        (Path(video_path), 20.0, 45.0),
        (Path(top_video_path), 90.0, 0.0),
    )


def _configure_equal_axes(ax, points_mm):
    """按全部毫米坐标的包围盒设置三轴范围和等比例显示，避免形状视觉失真。"""
    points = np.asarray(points_mm, dtype=float).reshape(-1, 3)
    minimum = np.min(points, axis=0)
    maximum = np.max(points, axis=0)
    span = np.maximum(maximum - minimum, 1.0)
    # 每轴至少留 2 mm、或数据跨度 5% 的边距，防止曲线贴住图框。
    padding = np.maximum(2.0, 0.05 * span)
    lower = minimum - padding
    upper = maximum + padding
    ax.set_xlim(lower[0], upper[0])
    ax.set_ylim(lower[1], upper[1])
    ax.set_zlim(lower[2], upper[2])
    ax.set_box_aspect(np.maximum(upper - lower, 1.0))
    ax.set_xlabel("X / mm")
    ax.set_ylabel("Y / mm")
    ax.set_zlabel("Z / mm")
    ax.grid(True, color="lightgrey", linestyle=":", linewidth=0.6)


def render_tip_trajectory_png(data, output_path, title=None):
    """将全部锚定后末端位置和固定入口绘制为静态三维 PNG，并返回输出路径。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 数据内部统一使用 m；绘图统一转换为更直观的 mm。
    tips_mm = data.shapes_m[:, -1, :] * 1000.0
    anchor_mm = data.anchor_m * 1000.0
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection="3d")
    try:
        ax.plot(*tips_mm.T, color="red", linewidth=1.5, label="Anchored tip trajectory")
        ax.scatter(*tips_mm[0], color="green", s=65, label="Start tip")
        ax.scatter(*tips_mm[-1], color="blue", s=65, label="End tip")
        ax.scatter(*anchor_mm, color="black", marker="x", s=100, linewidths=2.5, label="Fixed entrance anchor")
        _configure_equal_axes(ax, np.vstack((tips_mm, anchor_mm)))
        ax.set_title(title or f"{data.source_path.stem} - Anchored Fiber Tip Trajectory")
        ax.legend(loc="upper right")
        ax.view_init(elev=20, azim=45)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    finally:
        plt.close(fig)
    return output_path


def render_tip_trajectory_html(data, output_path, title=None):
    """
    生成可旋转、可悬停检查的自包含 Plotly HTML 末端轨迹。

    悬停信息同时显示相对时间、相对推进量和三维毫米坐标；Plotly 脚本嵌入
    文件，因此结果可脱离 Python 环境单独打开。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tips_mm = data.shapes_m[:, -1, :] * 1000.0
    anchor_mm = data.anchor_m * 1000.0
    # 将时间和推进量绑定到每个轨迹点，供 Plotly 悬停模板读取。
    customdata = np.column_stack((data.times_s, data.relative_inserts_mm))

    figure = go.Figure()
    figure.add_trace(
        go.Scatter3d(
            x=tips_mm[:, 0],
            y=tips_mm[:, 1],
            z=tips_mm[:, 2],
            mode="lines",
            name="Anchored tip trajectory",
            line={"color": "red", "width": 5},
            customdata=customdata,
            hovertemplate=(
                "Time: %{customdata[0]:.2f} s<br>"
                "Relative insertion: %{customdata[1]:.2f} mm<br>"
                "X: %{x:.2f} mm<br>Y: %{y:.2f} mm<br>Z: %{z:.2f} mm<extra></extra>"
            ),
        )
    )
    for point, name, color in (
        (tips_mm[0], "Start tip", "green"),
        (tips_mm[-1], "End tip", "blue"),
        (anchor_mm, "Fixed entrance anchor", "black"),
    ):
        figure.add_trace(
            go.Scatter3d(
                x=[point[0]],
                y=[point[1]],
                z=[point[2]],
                mode="markers",
                name=name,
                marker={"size": 6, "color": color, "symbol": "x" if name.startswith("Fixed") else "circle"},
                hovertemplate=f"{name}<br>X: %{{x:.2f}} mm<br>Y: %{{y:.2f}} mm<br>Z: %{{z:.2f}} mm<extra></extra>",
            )
        )
    figure.update_layout(
        title=title or f"{data.source_path.stem} - Anchored Fiber Tip Trajectory",
        scene={
            "xaxis_title": "X / mm",
            "yaxis_title": "Y / mm",
            "zaxis_title": "Z / mm",
            "aspectmode": "data",
        },
        legend={"x": 0.01, "y": 0.99},
        margin={"l": 0, "r": 0, "b": 0, "t": 50},
    )
    figure.write_html(str(output_path), include_plotlyjs=True, full_html=True)
    return output_path


def _frame_indices(frame_count, max_frames):
    """在包含首尾帧的前提下均匀抽取不超过 `max_frames` 个唯一帧索引。"""
    if frame_count <= 0 or max_frames <= 0:
        raise ValueError("frame_count and max_frames must be positive")
    # linspace 保留完整时间跨度，unique 消除整数取整可能产生的重复索引。
    return np.unique(np.linspace(0, frame_count - 1, min(frame_count, max_frames), dtype=int))


def render_shape_video(data, output_path, max_frames=1200, fps=20, dpi=100, elev=20, azim=45):
    """
    将抽样后的完整光纤形状、固定入口和累计末端轨迹编码为 MP4。

    `max_frames` 限制长记录的渲染成本，`fps`/`dpi` 控制输出；`elev` 与
    `azim` 指定固定相机视角。输入曲线由 m 转为 mm 后绘制。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 视频坐标、标注和静态图保持相同的 mm 单位。
    shapes_mm = data.shapes_m * 1000.0
    anchor_mm = data.anchor_m * 1000.0
    indices = _frame_indices(len(shapes_mm), int(max_frames))

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    _configure_equal_axes(ax, np.vstack((shapes_mm.reshape(-1, 3), anchor_mm)))
    ax.view_init(elev=float(elev), azim=float(azim))
    shape_line, = ax.plot([], [], [], color="blue", linewidth=2.0, label="Anchored fibre")
    tip_line, = ax.plot([], [], [], color="red", linewidth=1.0, alpha=0.8, label="Tip trajectory")
    tip_dot = ax.scatter([], [], [], color="red", s=35)
    ax.scatter(*anchor_mm, color="black", marker="x", s=100, linewidths=2.5, label="Fixed entrance anchor")
    time_text = ax.text2D(0.02, 0.95, "", transform=ax.transAxes)
    ax.legend(loc="upper right")
    writer = FFMpegWriter(fps=int(fps), bitrate=8000, metadata={"title": output_path.stem})
    tip_history = []

    try:
        with writer.saving(fig, str(output_path), dpi=int(dpi)):
            for frame_index in indices:
                shape = shapes_mm[frame_index]
                # 逐帧累积末端位置，使视频同时展示已经走过的末端轨迹。
                tip_history.append(shape[-1])
                history = np.asarray(tip_history)
                shape_line.set_data(shape[:, 0], shape[:, 1])
                shape_line.set_3d_properties(shape[:, 2])
                tip_line.set_data(history[:, 0], history[:, 1])
                tip_line.set_3d_properties(history[:, 2])
                tip_dot._offsets3d = ([shape[-1, 0]], [shape[-1, 1]], [shape[-1, 2]])
                time_text.set_text(
                    f"t={data.times_s[frame_index]:.2f} s  "
                    f"relative insertion={data.relative_inserts_mm[frame_index]:.2f} mm"
                )
                writer.grab_frame()
    finally:
        plt.close(fig)
    return output_path


def _capture_hhmm(path):
    """从文件名最后一个下划线后的前四位解析 HHMM；格式不匹配时返回 None。"""
    try:
        return int(Path(path).stem.rsplit("_", 1)[-1][:4])
    except (ValueError, IndexError):
        return None


def discover_pickle_files(input_path, from_time=None, to_time=None):
    """
    发现单个或目录内的 Pickle 文件，并按文件名中的 HHMM 闭区间筛选。

    返回按文件名排序的路径列表；输入不存在或筛选后为空时抛出明确异常。
    """
    input_path = Path(input_path)
    if input_path.is_file():
        candidates = [input_path]
    elif input_path.is_dir():
        candidates = sorted(input_path.glob("*.pkl"))
    else:
        raise FileNotFoundError(f"input path does not exist: {input_path}")

    selected = []
    for path in candidates:
        hhmm = _capture_hhmm(path)
        if from_time is not None and (hhmm is None or hhmm < int(from_time)):
            continue
        if to_time is not None and (hhmm is None or hhmm > int(to_time)):
            continue
        selected.append(path)
    if not selected:
        raise ValueError("no Pickle files matched the requested time range")
    return selected


def _atomic_render(render, final_path):
    """先渲染到同目录临时文件，成功后再原子替换最终文件，并始终清理残留。"""
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = final_path.with_name(f".{final_path.stem}.part{final_path.suffix}")
    # 清除上次异常退出遗留的同名临时文件，避免渲染器误用旧内容。
    temporary.unlink(missing_ok=True)
    try:
        render(temporary)
        # 只有渲染完整成功才替换正式结果，失败时保留已有文件不变。
        temporary.replace(final_path)
    finally:
        temporary.unlink(missing_ok=True)


def process_file(source, trajectory_output, video_output, max_frames, fps, overwrite=False):
    """
    处理单个 Pickle，并按需生成静态轨迹、交互轨迹和两种视角视频。

    `overwrite=False` 时跳过已经齐全的整组结果，也不会重做单个已存在文件；
    返回加载后的锚定数据，整组跳过时返回 None。
    """
    png_path, html_path, video_path, top_video_path = output_paths_for(
        trajectory_output,
        video_output,
        source,
    )
    output_paths = (png_path, html_path, video_path, top_video_path)
    if not overwrite and all(path.exists() for path in output_paths):
        print(f"[skip] outputs already exist for {Path(source).name}")
        return None

    print(f"[load] {source}")
    data = load_anchored_pickle(source)
    # 每种输出独立判断是否存在，支持中断后只补齐缺失产物。
    if overwrite or not png_path.exists():
        _atomic_render(lambda path: render_tip_trajectory_png(data, path), png_path)
    if overwrite or not html_path.exists():
        _atomic_render(lambda path: render_tip_trajectory_html(data, path), html_path)
    for target_path, elev, azim in video_render_specs(video_path, top_video_path):
        if overwrite or not target_path.exists():
            _atomic_render(
                lambda path, elev=elev, azim=azim: render_shape_video(
                    data,
                    path,
                    max_frames=max_frames,
                    fps=fps,
                    elev=elev,
                    azim=azim,
                ),
                target_path,
            )

    # 仅用未发生弧长截断的帧评估入口残差，避免边界截断混入锚定精度指标。
    unclamped = ~data.clamped
    max_residual = float(np.max(data.anchor_residuals_m[unclamped])) if np.any(unclamped) else float("nan")
    print(
        f"[done] {Path(source).name}: frames={len(data.times_s)}, "
        f"baseline={data.insertion_baseline_mm:.6f} mm, clamps={int(np.sum(data.clamped))}, "
        f"max_anchor_residual={max_residual:.3e} m"
    )
    print(f"       PNG={png_path}")
    print(f"       HTML={html_path}")
    print(f"       MP4={video_path}")
    print(f"       TOP_MP4={top_video_path}")
    return data


def main(argv=None):
    """解析命令行参数并批量渲染；任一文件失败则最终返回退出码 1。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="one Demonstrator .pkl or a directory")
    parser.add_argument("--from-time", type=int, help="inclusive HHMM filename filter, e.g. 1922")
    parser.add_argument("--to-time", type=int, help="inclusive HHMM filename filter, e.g. 1956")
    parser.add_argument("--trajectory-output", type=Path, required=True)
    parser.add_argument("--video-output", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=1200)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    files = discover_pickle_files(args.input, args.from_time, args.to_time)
    failures = []
    for index, source in enumerate(files, start=1):
        print(f"[{index}/{len(files)}]")
        try:
            process_file(
                source,
                args.trajectory_output,
                args.video_output,
                args.max_frames,
                args.fps,
                args.overwrite,
            )
        except Exception as exc:
            # 单文件失败不阻断其余文件，批次结束后再用退出码汇总失败状态。
            failures.append((source, exc))
            print(f"[failed] {source}: {exc}")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
