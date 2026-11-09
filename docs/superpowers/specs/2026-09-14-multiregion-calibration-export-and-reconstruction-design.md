# 多区域定标参数导出、加载与重构设计

## 目标

在不改变 `dev-entrylimit-reducefilter` 核心优化算法的前提下，将 full、end15cm、end5cm 三个独立定标区域和 0°、120°、240° 三个方向的结果合并为一个可验证、可加载的传感器参数包。

系统需要同时支持：

- 单区域 `optim`、`score` 和 `recon`；
- 多区域批量 `optim`、`score`；
- 使用完整传感器全局点位的多区域 `recon`；
- 按区域使用不同的曲率阈值、sigmoid 参数、weights、slopes 和局部分段；
- 阻止未经验证的局部相位进入完整传感器部署。

## 保持不变的优化行为

现有 `Optimiser.optim_coeff()` 的含义和两阶段顺序保持不变：

1. 先优化 slopes，使用 `force_ideal_magnitude=True` 约束形状重构曲率；
2. 固定 slopes 后优化 weights，恢复正常应变估计曲率；
3. 保留 Powell 优化、边界、停止判断、发散回滚、损失函数和最终正常重构误差；
4. 每个区域继续创建独立 `Optimiser`，不把现有 `task optim` 改成三区域联合优化。

当前分支对 `optim_coeff()` 的额外返回值只用于记录两阶段状态。若未来需要联合校正，应新增独立流程，不改变现有 `task optim` 的可复现语义。

## 命令语义

`multi_region_calib` 根据任务类型解释：

| task | `multi_region_calib=False` | `multi_region_calib=True` |
|---|---|---|
| optim/score | 只处理 `optimization_region` | 依次处理 `optimization_regions` |
| recon | 重构 `optimization_region` 指定的单一区域 | 使用完整全局点位和合并区域参数重构 |

单区域 recon 必须允许：

```powershell
python main.py --task recon --multi_region_calib False --optimization_region full
python main.py --task recon --multi_region_calib False --optimization_region end15cm
python main.py --task recon --multi_region_calib False --optimization_region end5cm
```

因此，`resolve_calibration_region()` 不再把 `multi_region_calib=False` 等同于只能选择 full。该开关负责批量或合并运行方式；`optimization_region` 负责单区域选择。

## 参数文件结构与顺序

默认导出路径为：

```text
params/06B6_NeTi_v2_centraltube_multi_region.json
```

JSON 使用稳定插入顺序，不启用键名排序。顶层顺序为：

1. `sensor_id`
2. `format_version`
3. `shared_parameters`
4. `multi_region`
5. `regions`
6. `provenance`

`shared_parameters` 按 `build_argument_parser()` 的语义分组及组内参数出现顺序保存：

1. `hardware_parameters`
2. `calibration_experiment_parameters`
3. `optimization_hyperparameters`
4. `dynamic_display_parameters`
5. `reconstruction_parameters`
6. `initialization_parameters`
7. `angle_optimization_parameters`
8. `runtime_control_parameters`

所有 parser 参数必须各自拥有一个可编辑的权威位置。区域特有字段从共享参数中移出，保存在对应 `regions` 条目；统一相位和旋转角保存在 `multi_region`；任务和输出目录等非传感器物理参数保存在靠后的运行控制组。导出器同时在 provenance 中记录 parser 参数名顺序和源提交，供完整性审计，但不复制第二份可编辑默认值。

各区域至少保存：

- `length_m`
- `folder_path`
- `radii`
- `thresholds`
- `sharpness`
- 评分窗口及边界模式
- `local_segmentation`
- `global_segment_ids`
- `support_point_ids`
- `owned_point_ids`
- `weights`，方向键顺序固定为 0、120、240
- `slopes`，方向键顺序固定为 0、120、240
- 局部相位和局部 rot_ang 来源记录
- 各方向误差和优化状态

参数包同时保存源结果路径、源提交、生成时间和质量门禁结果。路径字段保留原始值，同时标记其可移植性；加载器对相对路径统一按参数文件或仓库路径解析。

## 结果合并和质量校验

结果合并器读取三个 `results.json`，并执行以下检查：

- sensor ID 一致；
- 顶层 direct 恰好是 0、120、240，不能用 0、1、2；
- 每个方向包含 full、end15cm、end5cm 且状态完整；
- 每个区域的 thresholds、局部分段、全局点位、全局段和重构长度跨方向一致；
- weight 长度等于该区域阈值数加一；
- slope 形状等于 `等级数 × 局部分段数`；
- 所有数值有限；
- 优化阶段状态、参数边界命中和误差进入质量报告。

合并器始终可以生成用于分析的 candidate 参数包。只有质量门禁通过后，才允许生成 `deployment_ready=true` 的部署参数包。

当前三份结果应被标记为 candidate，原因至少包括：

- 240° full 的 slope 和 weight 阶段发散；
- 240° end15cm 的 weight 阶段发散；
- 三个区域的局部相位参考不一致且尚未完成统一验证；
- 5 cm 的 20/15 mm 和部分 15 cm 小半径误差过大；
- 若 score 不能将高曲率数据稳定分开，需要重新设置阈值并优化。

## 相位和 rot_ang 策略

完整传感器运行时只允许一个 `global_phases_set` 和一个 `rot_ang`。

- full 的相位作为候选全局参考；
- end15cm、end5cm 的局部相位只保存到 provenance；
- 不把局部相位直接写入运行时区域参数；
- slope 按完整传感器空间连续累积，不在区域边界重新初始化相位；
- 局部 slopes 是在局部相位条件下得到的初值，必须经过完整点位回放验证；
- `rot_ang` 在合并后的完整重构上统一验证或重新搜索，局部 rot_ang 不直接部署。

若相位验证未通过，参数包必须保持 `deployment_ready=false`。离线验证允许显式加载 candidate，但动态展示和正常部署默认拒绝未验证参数。

## 区域支持范围和所有权范围

区域评分范围与最终参数所有权分开保存：

| 区域 | 评分支持点 | 最终参数所有权点 | 所有权全局空间段 |
|---|---|---|---|
| full | 1–22 | 1–15 | 0–4 |
| end15cm | 16–22 | 16–18 | 5 |
| end5cm | 19–22 | 19–22 | 6–7 |

评分仍在原定标支持范围内计算，然后只提取所有权点。这样 end15cm 不会因为最终只拥有三个点而改变原七点定标时的评分窗口边界行为。

## 不同曲率阈值下的逐点参数装配

每个区域可以使用不同的阈值数量。对区域 `r`、方向 `d`、全局点 `i`：

1. 使用区域基准 slopes 计算选档用基础曲率；
2. 在该区域的 `support_point_ids` 上，以 `thresholds_r`、`sharpness_r` 和保存的评分边界模式计算 sigmoid scores 和 masses；
3. 对区域拥有的点计算：

```text
final_weight[i] = Σ mass_r[k, i] * weight_r[d][k]
slope_map[i]    = Σ mass_r[k, i] * slope_r[d][k, local_segment(i)]
```

4. 将各区域拥有点的结果合并为完整传感器长度的 `final_weight` 和 `slope_map`；
5. 后续应变加权、动态通道角度、插值、标架积分和误差计算沿用现有实现。

构造选档基础曲率时，每个全局空间段采用其所有者区域的第 0 级 slope。该基础映射与待选档的其他等级分开构造，避免假设三个区域具有相同矩阵形状。

装配器必须检查：所有真实点恰好归属一个区域、不得遗漏或重叠；局部分段必须映射到完整全局段；方向必须存在；参数维度必须与本区域阈值一致。

## 参数加载与 main 适配

新增参数文件入口，例如：

```powershell
python main.py --task recon --sensor_params params/06B6_NeTi_v2_centraltube_multi_region.json ...
```

main 使用两阶段解析：

1. 预解析 `--sensor_params` 和 `--sensor_id`；
2. 加载并验证参数包；
3. 将共享参数设置为完整 parser 的默认值；
4. 再执行正式解析；
5. 命令行显式参数覆盖参数文件；
6. `task` 始终要求命令行显式提供，参数文件不能自动启动任务。

单区域 recon 从参数包选择 `optimization_region` 对应的完整三方向参数，再沿用单区域 Reconstructor。多区域 recon 将完整区域配置传给 Reconstructor，并强制使用 full 几何。

加载器拒绝未知格式版本、sensor ID 冲突、缺失 parser 参数、错误方向、维度不匹配和非有限数值。candidate 仅允许离线验证；动态 demo 和部署路径拒绝 `deployment_ready=false`。

## score 与阈值调整

在最终部署导出前，对 0°、120°、240° 和三个区域运行生产路径 `task score`。

阈值调整只依据应变估计基础曲率分布，不直接采用理论半径中点。报告至少比较：

- 各半径、各真实点的基础曲率分布；
- 各阈值的 sigmoid score 和 mass；
- 平均档位占比和末端档位占比；
- 相邻半径分布重叠；
- 评分窗口边界效应；
- 10%–90% sigmoid 过渡宽度。

若 30/20/15 mm 不能稳定分开，应调整对应区域 thresholds 和 sharpness，再重新优化受影响区域与方向。不能只修改部署参数而继续沿用旧优化结果。

## 完整传感器验证

验证使用完整 22 个真实点及虚拟末端点。对 full、15 cm、5 cm 数据分别以全局坐标运行，并按对应实验几何计算局部或分段理想形状。

报告按方向、区域和半径分别统计：

- 平均逐点误差；
- 末端位置误差；
- 末端切向和姿态误差；
- 2000–200 mm 大半径回归；
- 100/75/50/30 mm 的 15 cm 表现；
- 30/20/15 mm 的 5 cm 表现；
- 全局段 4→5、5→6 边界两侧的基础曲率、mass、weight、slope、累计相位及曲率向量变化。

三方向单独验收，不能只看合并平均值。相位、边界连续性、高曲率和既有大半径精度均通过后，才将参数包升级为 deployable。

## 测试范围

新增测试覆盖：

- 三个结果目录按 0/120/240 正确合并；
- 结果上下文或传感器不一致时拒绝；
- weight/slope 维度按各区域独立阈值验证；
- JSON 字段、参数组和组内字段顺序稳定；
- 当前 parser 参数完整导出；
- 参数包导出后再加载的往返一致性；
- 命令行覆盖参数文件默认值；
- `multi_region_calib=False` 下三个区域均可 recon；
- 所有权点无重叠、无遗漏；
- 不同阈值和不同等级数的逐点装配；
- support 范围评分与 owned 范围提取；
- 单一全局相位和连续 slope 累积；
- 未验证局部相位和发散优化阻止部署导出；
- 旧单区域参数路径保持兼容。

回归测试至少包含：

```powershell
python -m pytest tests/test_vector_filter_configuration.py tests/test_calibration_batch.py tests/test_calibration_regions.py -q
```

完成后运行新增测试、重构相关测试和可执行的完整测试集，并记录已知无关失败。
