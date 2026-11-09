import os
import re
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# 配置区
# ============================================================
root_dir = "./FBG/0121_01B2重测"   
output_dir = "0121_01B2"

SAVE_RAW_XLSX = False
n_points_expected = 16

# 目录中的 a-b
directs = [0, 120, 240]
radii = [0, 300, 400, 600, 800, 1000, 1500, 2000]

# 输出文件
summary_xlsx = os.path.join(output_dir, "summary_stats_16pts.xlsx")
range_plot_path = os.path.join(output_dir, "range_by_channel.png")
max_range_plot_path = os.path.join(output_dir, "max_range_by_point.png")

# 通道名映射：CH0/1/2 -> c1/c2/c3
channel_name_map = {
    0: "c1",
    1: "c2",
    2: "c3",
}

# ============================================================
# 初始化
# shape = (16, 3)
# 行: p1~p16
# 列: c1, c2, c3
# ============================================================
os.makedirs(output_dir, exist_ok=True)

global_max = np.full((n_points_expected, 3), -np.inf, dtype=float)
global_min = np.full((n_points_expected, 3),  np.inf, dtype=float)

global_max_file = np.full((n_points_expected, 3), "", dtype=object)
global_min_file = np.full((n_points_expected, 3), "", dtype=object)

global_max_row = np.full((n_points_expected, 3), -1, dtype=int)
global_min_row = np.full((n_points_expected, 3), -1, dtype=int)

# 可选：保存所有原始展开数据
all_raw_rows = [] if SAVE_RAW_XLSX else None

# ============================================================
# 辅助函数
# ============================================================
def extract_channel_idx(filename):
    """
    从文件名中提取 CHX 的 X。
    例如: CH0_20260121_152050_zero.csv -> 0
    """
    m = re.search(r"CH(\d+)", filename, flags=re.IGNORECASE)
    if m is None:
        return None
    return int(m.group(1))


def get_fbg_columns(df):
    """
    找出 FBG0 ~ FBG15 这类列，并按编号排序。
    返回 [(idx, col_name), ...]
    """
    fbg_cols = []
    for col in df.columns:
        m = re.fullmatch(r"FBG(\d+)", str(col), flags=re.IGNORECASE)
        if m is not None:
            fbg_idx = int(m.group(1))
            fbg_cols.append((fbg_idx, col))
    fbg_cols.sort(key=lambda x: x[0])
    return fbg_cols

def build_valid_row_mask(df, fbg_cols, threshold=9000, half_window=5):
    """
    对一个 csv 构造“有效行”掩码。

    新规则：
    - 对于某一行 i、某一列 FBGk，检查 [i-half_window, i+half_window] 范围内其他行 j。
    - 如果 |value[i] - value[j]| > threshold，
      则删除 abs(value) 更大的那一行。
    - 只要某行在任意列、任意一次比较中被判为“较大者”，该行即记为无效。
    - NaN 不参与比较。

    参数:
    - df: 当前 csv 的 DataFrame
    - fbg_cols: [(idx, col_name), ...]
    - threshold: 判定异常差值阈值
    - half_window: 半窗口大小，默认前后各看 5 行

    返回:
    - valid_row_mask: shape=(len(df),)，True 表示该行有效
    """
    n_rows = len(df)
    valid_row_mask = np.ones(n_rows, dtype=bool)

    col_names = [col for _, col in fbg_cols]
    values = df[col_names].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

    for i in range(n_rows):
        left = max(0, i - half_window)
        right = min(n_rows, i + half_window + 1)

        for j in range(left, right):
            if j == i:
                continue

            for c in range(values.shape[1]):
                vi = values[i, c]
                vj = values[j, c]

                if np.isnan(vi) or np.isnan(vj):
                    continue

                if abs(vi - vj) > threshold:
                    # 删除 magnitude 更大的那一行
                    if abs(vi) > abs(vj):
                        valid_row_mask[i] = False
                    elif abs(vj) > abs(vi):
                        valid_row_mask[j] = False
                    else:
                        # 如果绝对值完全一样，保守起见两个都删
                        valid_row_mask[i] = False
                        valid_row_mask[j] = False

    return valid_row_mask


# ============================================================
# 遍历所有 a-b 目录和其中 csv 文件
# ============================================================
for direct in directs:
    for radius in radii:
        folder = os.path.join(root_dir, f"{direct}-{radius}")
        if not os.path.isdir(folder):
            print(f"Skip folder (not found): {folder}")
            continue

        csv_paths = sorted(glob.glob(os.path.join(folder, "*.csv")))
        if not csv_paths:
            print(f"No csv files in: {folder}")
            continue

        print(f"Processing folder: {folder}")

        for csv_path in csv_paths:
            filename = os.path.basename(csv_path)
            ch_idx_raw = extract_channel_idx(filename)

            if ch_idx_raw is None:
                print(f"Skip file (cannot parse channel): {csv_path}")
                continue

            if ch_idx_raw not in channel_name_map:
                print(f"Skip file (unexpected channel CH{ch_idx_raw}): {csv_path}")
                continue

            axis_idx = ch_idx_raw   # CH0->0, CH1->1, CH2->2
            axis_name = channel_name_map[ch_idx_raw]

            df = pd.read_csv(csv_path)

            fbg_cols = get_fbg_columns(df)
            if not fbg_cols:
                print(f"Skip file (no FBG columns found): {csv_path}")
                continue

            # 只保留前16个点
            fbg_cols = [(idx, col) for idx, col in fbg_cols if idx < n_points_expected]
            if not fbg_cols:
                print(f"Skip file (no valid FBG0~FBG15 columns): {csv_path}")
                continue

            # ----------------------------------------------------
            # 行级 outlier 剔除：
            # 若某行任意一列与其前后5行范围内任意一行同列差值绝对值 > 9000，
            # 则整行不参与统计
            # ----------------------------------------------------
            valid_row_mask = build_valid_row_mask(
                df=df,
                fbg_cols=fbg_cols,
                threshold=500,
                half_window=10
            )

            n_removed = (~valid_row_mask).sum()
            if n_removed > 0:
                print(f"Removed {n_removed} outlier rows from: {csv_path}")

            # ----------------------------------------------------
            # 更新全局统计
            # 每个 csv 是一个通道的时序数据
            # 每列 FBGk 对应一个点 pk+1
            # ----------------------------------------------------
            for point_idx, col in fbg_cols:
                series = pd.to_numeric(df[col], errors="coerce")

                # 同时满足：不是 NaN，且不是 outlier 行
                valid_mask = (~series.isna()) & valid_row_mask
                if not valid_mask.any():
                    continue

                valid_series = series[valid_mask]

                local_max = valid_series.max()
                local_min = valid_series.min()

                # idxmax / idxmin 返回的是 DataFrame 原始索引
                local_max_row = int(valid_series.idxmax())
                local_min_row = int(valid_series.idxmin())

                # 更新全局最大值及其位置
                if local_max > global_max[point_idx, axis_idx]:
                    global_max[point_idx, axis_idx] = float(local_max)
                    global_max_file[point_idx, axis_idx] = csv_path
                    global_max_row[point_idx, axis_idx] = local_max_row

                # 更新全局最小值及其位置
                if local_min < global_min[point_idx, axis_idx]:
                    global_min[point_idx, axis_idx] = float(local_min)
                    global_min_file[point_idx, axis_idx] = csv_path
                    global_min_row[point_idx, axis_idx] = local_min_row

            # ----------------------------------------------------
            # 可选：导出原始展开数据
            # 每行保留时间戳 + 通道 + p1~p16
            # ----------------------------------------------------
            if SAVE_RAW_XLSX:
                timestamp_col = "timestamp" if "timestamp" in df.columns else None

                # 建立 point -> col_name 映射
                point_col_map = {idx: col for idx, col in fbg_cols}

                for row_idx in range(len(df)):
                    if not valid_row_mask[row_idx]:
                        continue
                    row_dict = {
                        "source_file": filename,
                        "direct": direct,
                        "radius": radius,
                        "channel": axis_name,
                    }

                    if timestamp_col is not None:
                        row_dict["timestamp"] = df.iloc[row_idx][timestamp_col]
                    else:
                        row_dict["timestamp"] = ""

                    for p in range(n_points_expected):
                        col_name = point_col_map.get(p, None)
                        row_dict[f"p{p+1}"] = (
                            pd.to_numeric([df.iloc[row_idx][col_name]], errors="coerce")[0]
                            if col_name is not None else np.nan
                        )

                    all_raw_rows.append(row_dict)

# ============================================================
# 把没有数据的位置转成 NaN
# ============================================================
global_max[global_max == -np.inf] = np.nan
global_min[global_min ==  np.inf] = np.nan
global_range = global_max - global_min

# ============================================================
# 表1：每个点 × 每个通道 的 max/min/range
# ============================================================
rows = []
axis_names = ["c1", "c2", "c3"]

for point_idx in range(n_points_expected):
    for axis_idx, axis_name in enumerate(axis_names):
        rows.append({
            "point": f"p{point_idx + 1}",
            "channel": axis_name,

            "max": global_max[point_idx, axis_idx],
            "max_file": global_max_file[point_idx, axis_idx],
            "max_row": global_max_row[point_idx, axis_idx],

            "min": global_min[point_idx, axis_idx],
            "min_file": global_min_file[point_idx, axis_idx],
            "min_row": global_min_row[point_idx, axis_idx],

            "range": global_range[point_idx, axis_idx],
        })

df_stats = pd.DataFrame(rows)

# ============================================================
# 表2：每个点的最大 range（在 c1/c2/c3 中取最大）
# ============================================================
point_max_range = np.nanmax(global_range, axis=1)

df_point_max_range = pd.DataFrame({
    "point": [f"p{i+1}" for i in range(n_points_expected)],
    "max_range": point_max_range
})

# ============================================================
# 宽表
# ============================================================
df_range_wide = pd.DataFrame({
    "point_index": np.arange(1, n_points_expected + 1),
    "c1_range": global_range[:, 0],
    "c2_range": global_range[:, 1],
    "c3_range": global_range[:, 2],
    "max_range": point_max_range
})

# ============================================================
# 输出 Excel
# ============================================================
with pd.ExcelWriter(summary_xlsx, engine="openpyxl") as writer:
    df_stats.to_excel(writer, sheet_name="point_channel_stats", index=False)
    df_point_max_range.to_excel(writer, sheet_name="point_max_range", index=False)
    df_range_wide.to_excel(writer, sheet_name="range_wide", index=False)

    if SAVE_RAW_XLSX and all_raw_rows is not None:
        df_raw = pd.DataFrame(all_raw_rows)
        preferred_cols = (
            ["source_file", "direct", "radius", "timestamp", "channel"]
            + [f"p{i}" for i in range(1, n_points_expected + 1)]
        )
        df_raw = df_raw[preferred_cols]
        df_raw.to_excel(writer, sheet_name="raw_data", index=False)

print(f"Saved summary xlsx: {summary_xlsx}")

# ============================================================
# 图1：3个通道的 range 曲线
# ============================================================
x = np.arange(1, n_points_expected + 1)

plt.figure(figsize=(10, 6))
for axis_idx, axis_name in enumerate(axis_names):
    plt.plot(x, global_range[:, axis_idx], marker="o", label=axis_name)

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

# ============================================================
# 图2：每个点的最大 range 曲线
# ============================================================
plt.figure(figsize=(10, 6))
plt.plot(x, point_max_range, marker="o", label="max_range")

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