# 支气管入口锚点约束设计

## 目标

在动态光纤重构和历史 Pickle 回放中加入可选的支气管入口位置约束。约束开启后，整条重构曲线只能做平移，不能额外旋转或变形；输出始终保持 60 个三维点。

## 坐标与距离约定

- 重构曲线坐标单位为米，机械臂 UDP/Pickle 的 `insert_value` 单位为毫米。
- 第一帧重构曲线的末端点视为已经到达主隆突。
- 支气管入口固定坐标由第一帧曲线末端沿三维中心线反向累计 0.06 m，并在线段内插值得到：`anchor = first_source_point`。
- Pickle 开头的 `insert_value == 0` 是通信尚未建立时的占位值，不作为机械臂零点。
- 首个有限且非零的读数（目标数据约为 156.8 mm）定义为推进量零点。后续相对推进量为 `current_insert - baseline_insert`。
- 在机械臂零点尚未建立时，相对推进量按 0 处理。零点建立后的零值视为掉线占位，沿用上一有效相对推进量。

## 每帧约束算法

1. 令目标反推弧长 `distance = entrance_offset_m + relative_insert_mm / 1000`，其中入口距离默认 0.06 m。
2. 从当前曲线末端沿离散折线反向累计真实三维弧长，不使用点号比例或单独的 X 坐标。
3. 在跨过目标弧长的线段内做线性插值，得到光纤与入口对应的精确点。
4. 计算 `translation = anchor - entrance_point`，把同一平移向量加到全部点上。
5. 不改变点顺序、点数、点间向量、曲率或末端姿态方向。

当目标弧长超过当前曲线总长时，使用曲线起点作为可达到的最远约束点，并在诊断结果中标记 `clamped=True`；动态程序继续运行，不因单帧越界退出。

## 代码边界

新增 `entrance_anchor.py`，只负责单位归一、推进量基准状态、折线反向弧长插值和平移约束。它不依赖 PyQt、VTK、串口或网络，可被实时展示和离线工具共同调用。

`demonstrator.py` 在动态滤波完成后、DataRecorder 保存以及 VTK/UDP 输出之前调用锚点约束。`main.py` 新增 `--anchor_constraint_enabled` 开关，默认关闭，因此现有运行结果保持不变。

新增 `tools/render_anchored_pickles.py`，逐帧读取 Demonstrator 生成的 Pickle，应用同一约束状态机，并生成：

- `fiber_tip_trajectories/<stem>_anchored_tip_trajectory.png`
- `pickle_videos/<stem>/<stem>_anchored_full.mp4`

原始 Pickle 和已有未锚定图像/视频保持只读，不覆盖。

## 验证数据和验收标准

验证文件范围为：

- `VTK_ShapeData_20260820_192216.pkl`
- `VTK_ShapeData_20260820_193638.pkl`
- `VTK_ShapeData_20260820_195043.pkl`
- `VTK_ShapeData_20260820_195642.pkl`

验收要求：

- 每个输入文件都能生成一张 3D 末端轨迹 PNG 和一个 MP4。
- 每帧输出形状均为 `(60, 3)` 且有限。
- 首个非零机械臂读数被归零，前导零不造成约 156.8 mm 的坐标跳变。
- 对未发生弧长越界的帧，重新计算的入口点与固定锚点距离在浮点误差范围内。
- 每帧平移前后的相邻点差分相同，证明没有额外旋转或形变。
- 功能关闭时动态输出与原行为一致。

## 非目标

- 不做入口切向量对齐或刚体旋转。
- 不估计肺模型坐标系或配准 STL。
- 不修改原始波长、曲率、方向角、Kalman 状态或重构算法。
- 不覆盖原有实验结果。
