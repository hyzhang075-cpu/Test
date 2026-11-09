import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

for time in [1028, 1108, 1119, 1129, 1155, 1220, 1230, 1448, 1526, 1812]:
    pkl_path = f"Shenyang_data_16pt/realtime_data_20260228_{time}.pkl"  # 改成你的文件名
    base, _ = os.path.splitext(pkl_path)
    xlsx_path = base + ".xlsx"

    rows = []
    n_points_expected = 5  # 你希望是 60 列点；如果想“按实际点数”，把下面相关逻辑改掉

    with open(pkl_path, "rb") as f:
        while True:
            try:
                frame = pickle.load(f)
            except EOFError:
                break

            ts = frame.get("timestamp_ms", None)
            now_seconds = ts/1000
            dt_object = datetime.fromtimestamp(now_seconds)
            ts = dt_object.strftime("%H:%M:%S") + f".{int((now_seconds % 1) * 1000):03d}"
            pts = np.asarray(frame["r_results_postrot"], dtype=float)  # shape: (N, 3)

            if pts.ndim != 2 or pts.shape[1] != 3:
                raise ValueError(f"r_results_postrot shape 异常: {pts.shape}, 期望 (N,3)")

            # 只取前 60 个点；如果不足 60，则用 NaN 补齐到 60
            if pts.shape[0] >= n_points_expected:
                pts = pts[:n_points_expected, :]
            else:
                pad = np.full((n_points_expected - pts.shape[0], 3), np.nan, dtype=float)
                pts = np.vstack([pts, pad])

            # 转成 3 x 60: 行分别是 x, y, z
            xyz = pts.T  # (3, 60)

            # 组装 3 行：timestamp 只在第一行显示，后两行留空
            for axis_i, axis_name in enumerate(["x", "y", "z"]):
                row = {"timestamp_ms": ts if axis_i == 0 else ""}
                # 60 列点：p1..p60
                for j in range(n_points_expected):
                    row[f"p{j+1}"] = xyz[axis_i, j]
                rows.append(row)

    df = pd.DataFrame(rows, columns=["timestamp_ms"] + [f"p{i}" for i in range(1, n_points_expected + 1)])

    # 写 Excel
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)

    print("Saved:", xlsx_path)