# 负 `start_value` 与零点前传感点裁切：跨分支修改说明

## 1. 修改目的

当传感器第一个传感点位于固定件内部时，`start_value` 可能为负数，例如 `-11 mm`。固定件内部传感点的应变接近零，不应参与定标、分段拟合或曲线重构。

本修改采用以下策略：

1. 允许有限的负 `start_value`，但 `end_value` 仍必须为有限非负数。
2. 先按原始点位计算物理全长和全部采样坐标。
3. 删除所有坐标严格小于零的真实传感点。
4. 使用同一个裁切索引同步处理坐标、静态数据矩阵、实时数据点号、全局点号和分段。
5. 裁切后继续使用原有 `zero_init`，在 `0 m` 处添加虚拟点，并复制第一个保留真实点的曲率信息。
6. 如果裁切导致首段少于两个点，发出明确警告，要求重新分段和重新标定；程序不自动决定新的物理分段边界。

不要采用“保留负坐标并直接插入零点”的方案。原有 `zero_init` 会把 `0` 插到采样数组开头，负采样点会使 `ad_samp_dist` 不再严格递增，而且曲线会从固定件内部的负坐标开始，破坏原有重构语义。

## 2. 预期行为示例

以当前 08B5 配置为例：

```text
start_value = -11 mm
end_value = 6 mm
原始第 1 点 = -0.011 m
原始第 2 点 =  0.040 m
```

修改后的结果应为：

```text
raw_trim_idx = 1
global_point_ids = [2, 3, ..., 22]
samp_dist[0] = 0.040 m
ad_samp_dist[0] = 0.000 m
zero_init = True
ideal_len = 0.895 m
```

若原始全段分段为：

```text
[2, 5, 8, 3, 2, 2]
```

裁掉第一个点后，机械计算结果为：

```text
[1, 5, 8, 3, 2, 2]
```

首段只有一个点，无法可靠拟合。程序应发出 `RuntimeWarning`，并建议重新分段。例如在确认物理边界允许后，可考虑把裁切后的分段调整为：

```text
[2, 4, 8, 3, 2, 2]
```

这只是建议，不能由程序静默应用。调整分段后必须重新生成 `slopes`；旧参数不能继续使用。

当前分支已经把原始全段配置改为 `[3, 4, 8, 3, 2, 2]`，删除第一个负坐标点后得到 `[2, 4, 8, 3, 2, 2]`。其他分支应结合自身物理分段确认是否采用相同边界，不要只复制数值。

## 3. `calibration_regions.py` 修改项

### 3.1 放开 `start_value` 非负限制

在 `compute_fbg_geometry()` 中：

- `start_value`：要求有限，允许为负。
- `end_value`：要求有限且非负。
- `ideal_len`：必须大于零。
- 至少要有一个采样点位于零点或零点之后。

核心校验：

```python
if not np.all(np.isfinite(gaps)) or end_value < 0:
    raise ValueError(
        'start_value 必须是有限 mm 数值，end_value 必须是有限非负 mm 数值'
    )

if ideal_len <= 0 or not np.any(positions >= 0):
    raise ValueError('传感器有效长度必须为正，且至少有一个传感点位于零点或其后')
```

物理全长仍使用未裁切几何计算，不得因为删除负坐标点而缩短：

```python
ideal_len = (start_value + end_value + preset[-1] - preset[0]) / 1000
```

### 3.2 增加分段头部裁切函数

增加 `_trim_partition_prefix(segmentation, removed_points)`：

- 从第一个分段开始消费被裁掉的点数。
- 部分裁掉一个分段时，缩减该分段点数。
- 整段被裁掉时，删除该分段。
- 同时返回保留下来的原始分段编号，供 `global_segment_ids` 使用。

不能只执行 `segmentation[0] -= removed_points`，因为负点数量可能跨越多个分段。

### 3.3 在区域解析时先裁掉负坐标点

在 `resolve_calibration_region()` 中：

```python
ideal_len, raw_positions = compute_fbg_geometry(...)
raw_point_count = len(raw_positions)
raw_full_segments = _validate_partition(
    full_segmentation, raw_point_count, '全长'
)

zero_start_index = int(
    np.searchsorted(raw_positions, -1e-12, side='left')
)
positions = raw_positions[zero_start_index:]
full_segments, full_segment_ids = _trim_partition_prefix(
    raw_full_segments, zero_start_index
)
```

`-1e-12` 用于吸收浮点误差；接近零的小负数可视为零点。

全段 profile 的 `segmentation` 需要先按原始点数校验，再应用相同裁切。局部区域的分段继续按局部有效点数校验。

全局点号必须保留原始编号：

```python
global_point_ids = list(
    range(zero_start_index + start_index + 1, raw_point_count + 1)
)
```

### 3.4 检测不可拟合分段并警告

仅当实际解析 `optimization_region == 'full'`、确实裁掉了零点前数据且裁切后首段少于两个点时发出警告：

```python
warnings.warn(
    '...首段仅剩 1 个点，无法可靠进行分段拟合。'
    '请重新分段并重新标定；不要直接沿用现有 slopes。',
    RuntimeWarning,
    stacklevel=2,
)
```

警告至少应包含：

- `start_value`；
- 裁掉的点数；
- 裁切前分段；
- 裁切后分段；
- 一个满足每段至少两个点的参考分段；
- 重新标定且不得沿用旧 `slopes` 的提示。

不要自动写回建议分段，因为分段边界具有物理意义。

## 4. `sensor.py` 修改项

### 4.1 采样坐标与静态数据使用同一个裁切索引

在 `generate_samp_dist()` 生成完整 `raw_samp_dist` 后计算：

```python
zero_start_idx = int(
    np.searchsorted(raw_samp_dist, -1e-12, side='left')
)
self.raw_trim_idx = zero_start_idx
```

如果同时配置了 `straight_trim`，最终索引取两种裁切要求中更靠后的一个：

```python
self.raw_trim_idx = max(zero_start_idx, straight_trim_idx)
```

后续现有静态数据裁切必须继续使用：

```python
self.Data = dict_recur_extract(
    self.Data,
    lambda data: data[self.raw_trim_idx:, :],
)
```

裁切必须发生在通道重排和交错刻栅合并之后，确保 `raw_trim_idx` 与最终矩阵行索引一致。

### 4.2 保留原有 `zero_init`

裁切后的第一个真实点如果大于零：

```python
self.zero_init = bool(self.samp_dist[0] != 0.0)
```

原有逻辑随后在 `ad_samp_dist` 前插入 `0.0`。重构阶段复制第一个保留真实点的数据作为零点虚拟数据，因此不需要让曲线从负坐标开始。

### 4.3 实时数据点号同步偏移

FiberTecc 网络包中的点号仍是裁切前的原始编号。写入 `current_snapshot` 前必须转换：

```python
effective_idx = idx - self.raw_trim_idx
if phy_ch in self.active_channels and 0 <= effective_idx < self.total_points:
    self.current_snapshot[effective_idx, col] = wavelength
```

`zero_points` 也必须使用 `effective_idx`。否则静态标定数据正确，但实时数据会整体错位一行，并可能丢掉最后一个有效点。

## 5. 测试修改项

至少增加以下回归测试：

1. 负 `start_value` 被接受，负坐标点被删除。
2. `global_point_ids` 保留原始编号，而不是从 1 重新编号。
3. `segmentation` 与裁切点数同步变化。
4. `samp_dist` 不含负数，`ad_samp_dist` 从零开始且严格递增。
5. 静态数据矩阵使用相同 `raw_trim_idx`。
6. 实时包原始点号正确映射为 `effective_idx`。
7. 裁切后首段只有一个点时发出包含“重新分段”的 `RuntimeWarning`。
8. 裁切后首段仍有至少两个点时不发出该警告。
9. `end_value < 0`、非有限输入、全部采样点均位于零点前时仍被拒绝。

建议验证命令：

```powershell
python -m py_compile calibration_regions.py sensor.py
python -m pytest tests/test_calibration_regions.py -q
python -m pytest tests/test_calibration_regions.py tests/test_calibration_phase_reference.py tests/test_multiregion_reconstruction.py tests/test_calibration_batch.py -q
```

还应使用目标分支的实际参数完成一次只到配置解析层的冒烟验证，确认输出至少包括：

```text
global_point_ids=[2, ..., 22]
sample_dist_m[0]=0.04
ideal_len=0.895
```

## 6. 跨分支移植检查清单

- [ ] 搜索并删除所有要求 `start_value >= 0` 的校验，但保留有限性检查。
- [ ] 保持 `ideal_len` 使用原始物理几何计算。
- [ ] 几何解析和 `Sensor` 使用相同的零点前裁切规则与容差。
- [ ] `raw_trim_idx` 同时裁切坐标和静态数据矩阵。
- [ ] 全局点号保持原始编号。
- [ ] 分段计数随裁切同步变化，且支持跨多个分段裁切。
- [ ] 首段不足两个点时发出重新分段及重新标定警告。
- [ ] 不自动采用建议分段，不复用旧 `slopes`。
- [ ] 实时数据点号减去 `raw_trim_idx`。
- [ ] `straight_trim` 与零点前裁切同时存在时取更靠后的裁切位置。
- [ ] 正 `start_value`、局部区域、反向重构和多区域参数包行为保持兼容。
- [ ] 运行回归测试，并检查实际传感器配置输出。

## 7. 参数与结果兼容性

该修改会改变有效真实点数量和首段点数。以下产物应视为与旧配置不兼容并重新生成：

- 全段 `slopes`；
- 依赖分段数或分段边界的标定参数；
- `global_point_ids`、`global_segment_ids` 和 support/owned point 元数据；
- 基于旧点数保存的动态零状态文件。

如果裁切只缩短首段但没有删除整个分段，斜率矩阵的列数可能恰好不变，这并不表示旧参数仍然有效。首段支持点和拟合含义已经改变，仍应重新标定。
