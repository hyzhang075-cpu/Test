import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime

SAVE_RAW_XLSX = False

times = [1028, 1108, 1119, 1129, 1155, 1220, 1230, 1448, 1526, 1812]
# times = [1129]

n_points_expected = 16
axis_names = ["c1", "c2", "c3"]

# 统计结果输出路径
output_dir = "Shenyang_data_16pt"
summary_xlsx = os.path.join(output_dir, "summary_stats_16pts.xlsx")
range_plot_path = os.path.join(output_dir, "range_by_channel.png")
max_range_plot_path = os.path.join(output_dir, "max_range_by_point.png")

# ------------------------------------------------------------------
# 全局统计矩阵
# shape = (16, 3)
# 行: p1~p16
# 列: c1, c2, c3
# ------------------------------------------------------------------
global_max = np.full((n_points_expected, 3), -np.inf, dtype=float)
global_min = np.full((n_points_expected, 3),  np.inf, dtype=float)

# ------------------------------------------------------------------
# 遍历所有 pkl 文件
# ------------------------------------------------------------------
for time in times:
    pkl_path = f"Shenyang_data_16pt/realtime_data_20260228_{time}.pkl"

    if not os.path.exists(pkl_path):
        print(f"Skip (not found): {pkl_path}")
        continue

    # 原始数据 xlsx 输出路径
    base, _ = os.path.splitext(pkl_path)
    raw_xlsx_path = base + ".xlsx"

    # 只有在需要时才收集原始展开数据
    raw_rows = [] if SAVE_RAW_XLSX else None

    with open(pkl_path, "rb") as f:
        while True:
            try:
                frame = pickle.load(f)
            except EOFError:
                break

            pts = np.asarray(frame["raw_data"], dtype=float)

            if np.isnan(pts).any() or np.nanmax(np.abs(pts)) > 7000:
                continue

            if pts.ndim != 2 or pts.shape[1] != 3:
                raise ValueError(f"raw_data shape 异常: {pts.shape}, 期望 (N, 3)")

            # ----------------------------------------------------------
            # 更新统计：只统计前 16 个点
            # ----------------------------------------------------------
            valid_n = min(pts.shape[0], n_points_expected)
            pts_valid = pts[:valid_n, :]   # shape: (valid_n, 3)

            for i in range(valid_n):
                for j in range(3):
                    val = pts_valid[i, j]
                    if not np.isnan(val):
                        global_max[i, j] = max(global_max[i, j], val)
                        global_min[i, j] = min(global_min[i, j], val)

            # ----------------------------------------------------------
            # 可选：保存原始展开数据到每个 pkl 对应的 xlsx
            # ----------------------------------------------------------
            if SAVE_RAW_XLSX:
                ts = frame.get("timestamp_ms", None)

                if ts is None:
                    ts_str = ""
                else:
                    now_seconds = ts / 1000
                    dt_object = datetime.fromtimestamp(now_seconds)
                    ts_str = dt_object.strftime("%H:%M:%S") + f".{int((now_seconds % 1) * 1000):03d}"

                # 补齐/截断到 16 点，便于导出
                if pts.shape[0] >= n_points_expected:
                    pts_export = pts[:n_points_expected, :]
                else:
                    pad = np.full((n_points_expected - pts.shape[0], 3), np.nan, dtype=float)
                    pts_export = np.vstack([pts, pad])

                xyz = pts_export.T  # shape: (3, 16)

                for axis_i, axis_name in enumerate(axis_names):
                    row = {"timestamp_ms": ts_str if axis_i == 0 else "", "channel": axis_name}
                    for j in range(n_points_expected):
                        row[f"p{j+1}"] = xyz[axis_i, j]
                    raw_rows.append(row)

    # --------------------------------------------------------------
    # 按开关决定是否保存每个 pkl 的原始数据 xlsx
    # --------------------------------------------------------------
    if SAVE_RAW_XLSX:
        df_raw = pd.DataFrame(
            raw_rows,
            columns=["timestamp_ms", "channel"] + [f"p{i}" for i in range(1, n_points_expected + 1)]
        )

        with pd.ExcelWriter(raw_xlsx_path, engine="openpyxl") as writer:
            df_raw.to_excel(writer, sheet_name="data", index=False)

        print(f"Saved raw xlsx: {raw_xlsx_path}")

# ------------------------------------------------------------------
# 把没有数据的位置转成 NaN
# ------------------------------------------------------------------
global_max[global_max == -np.inf] = np.nan
global_min[global_min ==  np.inf] = np.nan

global_range = global_max - global_min   # shape: (16, 3)

# ------------------------------------------------------------------
# 整理成表1：每个点 × 每个通道 的 max/min/range
# ------------------------------------------------------------------
rows = []
for point_idx in range(n_points_expected):
    for axis_idx, axis_name in enumerate(axis_names):
        max_val = global_max[point_idx, axis_idx]
        min_val = global_min[point_idx, axis_idx]
        range_val = global_range[point_idx, axis_idx]

        rows.append({
            "point": f"p{point_idx + 1}",
            "channel": axis_name,
            "max": max_val,
            "min": min_val,
            "range": range_val
        })

df_stats = pd.DataFrame(rows)

# ------------------------------------------------------------------
# 整理成表2：每个点的最大 range（在 c1/c2/c3 中取最大）
# ------------------------------------------------------------------
point_max_range = np.nanmax(global_range, axis=1)

df_point_max_range = pd.DataFrame({
    "point": [f"p{i+1}" for i in range(n_points_expected)],
    "max_range": point_max_range
})

# ------------------------------------------------------------------
# 再做一个宽表，便于看图和查阅
# ------------------------------------------------------------------
df_range_wide = pd.DataFrame({
    "point_index": np.arange(1, n_points_expected + 1),
    "c1_range": global_range[:, 0],
    "c2_range": global_range[:, 1],
    "c3_range": global_range[:, 2],
    "max_range": point_max_range
})

# ------------------------------------------------------------------
# 输出一个汇总 xlsx（多个 sheet）
# ------------------------------------------------------------------
with pd.ExcelWriter(summary_xlsx, engine="openpyxl") as writer:
    df_stats.to_excel(writer, sheet_name="point_channel_stats", index=False)
    df_point_max_range.to_excel(writer, sheet_name="point_max_range", index=False)
    df_range_wide.to_excel(writer, sheet_name="range_wide", index=False)

print(f"Saved summary xlsx: {summary_xlsx}")

# ------------------------------------------------------------------
# 图1：3 个通道的 range 曲线
# 横轴：点数
# 纵轴：range
# ------------------------------------------------------------------
x = np.arange(1, n_points_expected + 1)

plt.figure(figsize=(10, 6))
for axis_idx, axis_name in enumerate(axis_names):
    plt.plot(x, global_range[:, axis_idx], marker='o', label=axis_name)

plt.xlabel("Point Index")
plt.ylabel("Range")
plt.title("Range of Each Channel Across 16 Points")
plt.xticks(x)
plt.grid(True, linestyle="--", alpha=0.4)
plt.legend()
plt.tight_layout()
plt.savefig(range_plot_path, dpi=300, bbox_inches="tight")
plt.close()

print(f"Saved figure: {range_plot_path}")

# ------------------------------------------------------------------
# 图2：每个点的最大 range 曲线
# 横轴：点数
# 纵轴：max range
# ------------------------------------------------------------------
plt.figure(figsize=(10, 6))
plt.plot(x, point_max_range, marker='o', label="max_range")

plt.xlabel("Point Index")
plt.ylabel("Max Range")
plt.title("Maximum Range of Each Point Across Channels")
plt.xticks(x)
plt.grid(True, linestyle="--", alpha=0.4)
plt.legend()
plt.tight_layout()
plt.savefig(max_range_plot_path, dpi=300, bbox_inches="tight")
plt.close()

print(f"Saved figure: {max_range_plot_path}")