# 全长与嵌套区域定标配置

本阶段实现定标数据选择、正确几何、全局分段校验和按区域批量优化。每个区域仍使用独立 Optimiser 执行现有的先 slope、后 weight 流程；本阶段的循环不是三区域联合损失优化。

## main 中的配置

这些配置现在全部位于 `build_argument_parser()` 内，可随整套传感器 parser 参数一起复制和迁移：

```python
parser.add_argument('--multi_region_calib', default=False, ...)
parser.add_argument('--optimization_region', default='full', ...)
parser.add_argument('--optimization_regions', default=['full', 'end15cm', 'end5cm'], ...)
parser.add_argument('--full_segmentation', default=[2,3,5,2,3,3,2,2], ...)
parser.add_argument('--calibration_data_root', default='0908-06B6', ...)
parser.add_argument('--calibration_regions', default={...}, ...)
```

新传感器先使用 False/full 完成全长定标和可用性验证。`multi_region_calib=True` 且 task 为 optim 或 score 时，按 `optimization_regions` 的顺序遍历全部区域。`multi_region_calib=False` 时，init/recon 可由 `optimization_region` 单独选择 full、end15cm 或 end5cm。`multi_region_calib=True` 的 recon 使用完整参数包和全长几何。各区域的长度、数据目录、半径、阈值、局部分段和可选初值集中在 `calibration_regions` 字典；其他长度可用同样字段添加条目。

| 选择 | 数据目录（0908-06B6 下） | 真实数据行号（1-based） | 分段 | 重构长度 |
|---|---|---|---|---|
| full | 全段测试 | 1–22 | [2,3,5,2,3,3,2,2] | 877 mm |
| end15cm | 末端测试/15cm | 16–22 | [3,2,2] | 150 mm |
| end5cm | 末端测试/5cm | 19–22 | [2,2] | 50 mm |

开启区域模式会检查所有已配置长度，确保它们共享同一全长空间分段。关闭区域模式时只检查并运行当前 `optimization_region`。

全长长度计算：`(7 + (1370 - 510) + 10) / 1000 = 0.877 m`。
Sensor 与 main 共用几何计算函数，直接构造 Sensor 也会根据 FBG 几何重新计算全长。OFDR/LUNA 全长路径仍保留显式长度设置，不使用 FBG 跨度。

`straight_trim=-0.05` 从全局 0.827 m 开始，末端四个真实点的局部坐标为 7、18、29、40 mm；50 mm 为虚拟末端点，不参与空间分段。15 cm 局部坐标为 28、62、96、107、118、129、140 mm，虚拟末端为 150 mm。

全局行号跟随裁剪与反序保存，不能直接当作解调仪硬件 FBG 标签。全局行号、空间段 ID、全局坐标和裁剪原点也保存在 `optim.calibration_context`，供后续参数包使用。

## 分段错误会被拒绝

- 全长分段总和必须等于真实点数，且所有段长度为正整数。
- 裁剪起点必须落在全长空间段的开始位置。
- 局部分段必须与全长对应后缀完全相同，不能只保证总点数相同。
- 例如全长尾部采用旧的 `[2,2,3]` 时，5 cm 的起点切入其中第二段，会在 Optimiser 创建前报错。
- 若希望 5 cm 使用 `[4]`，应同步把全长改为 `[2,3,5,2,3,3,4]`，15 cm 改为 `[3,4]`，5 cm 改为 `[4]`。

## 命令行示例

在仓库目录运行：

```powershell
python main.py --task optim --multi_region_calib False --optimization_region full
python main.py --task optim --multi_region_calib True --weights None --slopes None --direct 0
python main.py --task score --multi_region_calib True --direct 0
```

三个方向完成后，可导出有序参数包：

```powershell
python tools/sensor_parameter_package.py --results `
  calibration_results/06B6_NeTi_v2_centraltube-20260913T152012Z-dbd50a/results.json `
  calibration_results/06B6_NeTi_v2_centraltube-20260913T152022Z-3aa476/results.json `
  calibration_results/06B6_NeTi_v2_centraltube-20260913T152029Z-8a1a2a/results.json `
  --output params/06B6_NeTi_v2_centraltube_multi_region.json `
  --comparison docs/calibration-results-20260913-comparison.md
```

JSON 顶层以 `sensor_id` 开始。`shared_parameters` 按 parser 顺序分成硬件、定标实验、优化超参数、动态展示、重构、初始化、角度优化和运行控制组。每个 parser 参数只有一个权威位置；显式 CLI 值覆盖包内默认值，`--task` 始终必须显式给出。

`--comparison` 输出的汇总表、逐半径 point/end error 字典及明细统一使用完整传感器长度百分比：`error (m) / full.context.ideal_len (m) × 100`。end15cm/end5cm 也使用 full 长度作分母，weighted loss 按相同基准换算；文档记录各方向使用的完整长度。原始 results.json 和参数包中的误差、优化损失仍保留原值。

单区域与合并重构命令：

```powershell
python main.py --task recon --sensor_params params/06B6_NeTi_v2_centraltube_multi_region.json --multi_region_calib False --optimization_region full --direct 0
python main.py --task recon --sensor_params params/06B6_NeTi_v2_centraltube_multi_region.json --multi_region_calib False --optimization_region end15cm --direct 0
python main.py --task recon --sensor_params params/06B6_NeTi_v2_centraltube_multi_region.json --multi_region_calib False --optimization_region end5cm --direct 0
python main.py --task recon --sensor_params params/06B6_NeTi_v2_centraltube_multi_region.json --multi_region_calib True --direct 0
```

合并重构中，full、end15cm、end5cm 各自使用自己的 thresholds、sharpness、score 窗口、weights 和 slopes。每段先在它的定标支持点范围计算 score/mass，然后只把结果写入归属点：full 1–15，end15cm 16–18，end5cm 19–22。全长只使用 full 定标的统一 `global_phases_set` 和 `rot_ang`；局部相位只作为 provenance 保留。

离线全长验证：

```powershell
python tools/calibration_validation.py --sensor-params params/06B6_NeTi_v2_centraltube_multi_region.json
```

`deployment_ready` 只在优化、统一相位、实测 score 和全长几何全部验收后为 true。当前包为 candidate：240°/full 的 slope/weight 以及 240°/end15cm weight 阶段发散，全长回放的最大平均点误差为 187.314 mm，末端测试最大切向误差 141.643°，区域边界最大相位跳变 0.906 rad，因此仍为 false。详细结果见 `calibration-multiregion-validation.md`。

第二条命令依次优化 full、end15cm、end5cm。`--weights None --slopes None` 明确要求每个区域重新初始化。`--direct` 仍控制本次循环优化的方向；0°、120°、240°需要分别运行，输出会标记本次实际优化的方向。

每次批量运行在 `calibration_output_dir` 下创建独立的“传感器ID-UTC时间-随机后缀”目录，避免覆盖已有结果。每完成一个区域就原子更新：

- `results.json`：状态、区域配置、全局点位、两阶段状态、正常重构误差和详细误差；
- `parameters.py`：便于复制的区域 weights、slopes、相位和 rot_ang。

后续区域失败时，已完成区域仍保留，失败区域会写入异常，未开始区域保持 pending。

CLI 可覆盖所选区域的 folder_path、radii、thresholds、segmentation。新增列表/字典输入使用 Python 字面量解析，例如 `--thresholds "[0.8,1.2,2,3,4]"`。`ideal_len` 与 `straight_trim` 自动计算；若手动传入冲突值则报错。

三组 thresholds 本轮保留旧值以隔离裁剪修复；支持独立修改、不同档数，但尚未重新拟合参数。评分窗口、相位策略、插值与损失函数保持原实现。

新增 `task score` 会调用生产路径的 `_get_base()`、`_get_scores()` 和 `_alloc_mass()`，输出每个区域、方向、半径和真实点的：基础选档曲率、理论曲率、分位数、逐级 score/mass、平均档位占比和末点档位占比，并生成 JSON 与 PNG。它使用 `processed_Data` 中每个定标状态的平均应变，因此可以检查半径/点位之间的评分分离和 constant 边界效应，但不能表示原始帧噪声；要评估重复性仍需保留逐次或逐帧样本。

本机 0° 实际诊断已经表明，高曲率阈值不能直接照搬理论中点：5 cm 数据的基础曲率中位数在 100/50/30/20/15 mm 时约为 7.67/15.31/25.78/31.92/34.35 m⁻¹，明显低于理论 10/20/33.33/50/66.67 m⁻¹。应基于三个方向及重复采集的实际分布再确定最终阈值。

weights/slopes 默认 None，按当前区域初始化。旧 5 cm 数值保留在 main 的注释中作为历史参考；不可认为它们适用于修正后的长度和新分段。预载参数必须为方向字典，维度对应本区域 K/J；入口会验证并转换为 NumPy 数组，不自动截断或拼接参数。

## 优化策略建议

建议先用同一空间拓扑分别定标，再通过区域参数块联合校正。重构时逐点展开 final_weight/slope_map，不代表每个点都要成为独立优化变量。

1. 全长定标先建立可用性基线。
2. 各长度分别先优化 slope、再优化 weight，得到稳定初值；保存几何、相位及数据来源。
3. 统一全局相位参考后组装区域参数。最终部署所有权为 d>150 mm、50<d<=150 mm、d<=50 mm。
4. 联合校正时仍优化区域 K×J 参数块，针对各数据集生成逐点映射；分别归一化长度、半径、方向的损失，保留全长精度约束。

直接为每个点优化独立 weight/slope 会增加自由度，目前 5 cm 只有四点，不宜先走这条路径。反过来，单独拟合后仅拼接数组又无法处理局部相位参考及交界间隔。两阶段策略可以先建立可解释的初值，再解决全局部署误差。

## 可选 end5cm 真实点定标目标

### 19–20、21、22三组weights执行流程

新增 `--end5cm_independent_weights True`，默认False以兼容旧参数。它只对end5cm生效，与 `--end5cm_point_calib True` 配合使用。真实点分组 `weight_group_ids=[0,0,1,2]`；10个等级时，weights依次为19–20组10个、21组10个、22组10个，共30个；slopes仍10×2。此布局按分组选择weights，不再由end_start选择覆盖点。区域end_weights须True，虚拟点仍复制22点补偿曲率。旧20参数不会被自动复制成30参数。

1. 从项目目录运行以下单区域定标，不加载旧包，以便重新初始化三组weights；分别把direct设为0、120、240，保存每次打印的结果目录。

```bash
python main.py --task optim --multi_region_calib False --optimization_region end5cm --end5cm_point_calib True --end5cm_independent_weights True --weights None --slopes None --direct 0
```

2. 核对每个 `results.json`：区域完成、calibration_objective为real_points、weight_group_ids为[0,0,1,2]、weights长度30、slopes10×2。检查阶段状态、触边情况及30/20/15mm的21、22点曲率。不能把no_improvement直接视为通过。
3. 单区域recon传入新weights、slopes和保存的global_phases_set；也必须带 `--end5cm_independent_weights True`。其余参数与定标一致。下面PowerShell从direct0新结果读取参数，避免手抄；先把$r0替换为实际结果目录。

```powershell
$r0 = 'calibration_results/<新direct0目录>'
$report = Get-Content "$r0/results.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$entry = $report.regions.end5cm
$w = ConvertTo-Json -InputObject $entry.parameters.weights.'0' -Compress -Depth 10
$s = ConvertTo-Json -InputObject $entry.parameters.slopes.'0' -Compress -Depth 10
python main.py --task recon --multi_region_calib False --optimization_region end5cm --direct 0 --end5cm_independent_weights True --weights "{0: $w}" --slopes "{0: $s}" --global_phases_set $entry.parameters.global_phases_set
```

4. 三个方向都完成后，复用原完整结果的full/end15cm，仅替换end5cm。导出工具新增 `--base_results`：三个基础结果必须包含完整三区域；三个新results必须只含end5cm，方向和sensor_id必须一致。以下使用旧包的三个原始结果路径作为基础；$r120、$r240填新目录，输出采用新文件名。

```powershell
$r120 = 'calibration_results/<新direct120目录>'
$r240 = 'calibration_results/<新direct240目录>'
$old = Get-Content 'params/06B6_NeTi_v2_ftube_nophase_ang0_lastweight_angwindow.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$base = @($old.provenance.source_results)
python tools/sensor_parameter_package.py --base_results $base --results $r0 $r120 $r240 --output params/06B6_NeTi_v2_ftube_nophase_pointcalib_3weightgroups.json --comparison docs/calibration-pointcalib-3weightgroups-comparison.md
```

5. 完整定标回放与动态拼接对比使用新包；包自动继承两项新开关。先检查大半径曲线、30/20/15mm末端幅值、15cm/5cm交界、末端位置和姿态，再动态观察累计弯曲与扭转。没有自动重跑优化或自动覆盖旧包。

```bash
python main.py --task recon --multi_region_calib True --sensor_params params/06B6_NeTi_v2_ftube_nophase_pointcalib_3weightgroups.json --direct 0
python main.py --task demo --multi_region_calib True --sensor_params params/06B6_NeTi_v2_ftube_nophase_pointcalib_3weightgroups.json --direction_reference_direct 0
```

全长recon默认回放full数据；单区域end5cm回放用于小半径。跨区域全长小半径指标仍使用calibration_validation.py的定标回放，不以full目录的大半径图替代。

### end5cm覆盖感知weights优化与direct0单方向demo拼接

本节记录当前 `06B6_NeTi_v2_ftube` 的实际实施流程：保留
`params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json` 中已经优化的
full、end15cm和end5cm slope，只使用安装到导管后的5cm定标数据重新优化
end5cm weights；随后把新的direct0结果拼接成仅供direct0动态实验使用的完整参数包。
所有路径均相对于项目目录，旧参数包和旧优化结果不覆盖。

#### 1. 参数布局和空档处理规则

同时开启以下四个开关：

- `--end5cm_point_calib True`：weight目标使用真实点曲率相对于
  `1000/radius_mm` 的平方相对误差；
- `--end5cm_independent_weights True`：真实点按19–20、21、22分成三组，
  每组保留10档，最终仍输出30个weights；
- `--end5cm_independent_weight_score True`：19–20使用本组基础曲率评分，
  点21和点22分别使用各自的基础曲率评分；
- `--end5cm_coverage_aware_weights True`：只把有足够实测评分支持的档位交给
  优化器，未覆盖档不再作为自由参数。

覆盖判定排除半径0的直线状态。某组某档同时满足以下条件时才是自由档：

```text
effective_sample_count = 该组所有非零半径样本在该档的score mass之和
effective_sample_count >= end5cm_min_weight_effective_samples
max_mass >= end5cm_min_weight_max_mass
```

当前默认分别为 `1.0` 和 `0.05`。这样微小的sigmoid尾部不会被误认为一条完整
有效样本。没有满足覆盖条件的档位按
`--end5cm_uncovered_weight_policy interpolate_neutral_edges` 派生：

- 两侧都有可靠档时，按照实际threshold坐标对 `log(weight)` 插值；
- 位于第一个可靠档之前或最后一个可靠档之后时，固定为中性值 `1.0`；
- 派生档不进入SciPy自由变量，也不计作自由参数触边；
- 保存时仍展开为完整30个weights，recon/demo不需要在运行时重新插值。

这里的“合并空档”表示空档不再拥有独立优化自由度，由相邻可靠档共同决定；
它不会修改参数包的10档结构，也不会改变slopes的 `10×2` 形状。weight bounds
仍只约束自由档，默认保持 `(0.6, 5.0)`，不会根据覆盖情况自动扩大。

#### 2. 只优化安装后数据的end5cm weights

从项目目录运行。基础包用于提供既有slope、相位和其余区域参数；安装后定标
数据位于 `0909-06B6末端固定前端滑轨定标重测/5cm`。该目录目前只有direct0，
因此本次命令只运行 `--direct 0`：

```powershell
python main.py `
  --task optim `
  --sensor_params params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json `
  --multi_region_calib False `
  --optimization_region end5cm `
  --end5cm_point_calib True `
  --end5cm_independent_weights True `
  --end5cm_independent_weight_score True `
  --end5cm_coverage_aware_weights True `
  --end5cm_min_weight_effective_samples 1.0 `
  --end5cm_min_weight_max_mass 0.05 `
  --end5cm_uncovered_weight_policy interpolate_neutral_edges `
  --optim_weights_only True `
  --calibration_data_root "0909-06B6末端固定前端滑轨定标重测" `
  --folder_path 5cm `
  --radii "{'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 150, 100, 50, 30, 20, 15]}" `
  --weights None `
  --direct 0
```

不要添加 `--slopes None`。`--optim_weights_only True` 要求从 `--sensor_params`
继承同方向的既有slope；显式传入 `--slopes None` 会清除该来源。若PowerShell中的
`python` 被Microsoft Store别名接管，应先激活正确conda环境，或把命令开头替换为
该环境的 `python.exe`，其余参数不变。

本次实际输出目录为：

```text
calibration_results/06B6_NeTi_v2_ftube-20260920T162538+0800-direct0-f82abf
```

#### 3. 核验results.json

优化结束后至少检查以下字段：

```powershell
$r0 = 'calibration_results/06B6_NeTi_v2_ftube-20260920T162538+0800-direct0-f82abf'
$report = Get-Content "$r0/results.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$entry = $report.regions.end5cm

$report.direct
$entry.status
$entry.context.calibration_objective
$entry.context.weight_group_ids
$entry.context.weight_score_mode
$entry.parameters.weights.'0'.Count
$entry.parameters.slopes.'0'.Count
$entry.parameters.coverage_aware_weights.free_parameter_count
$entry.parameters.coverage_aware_weights.derived_parameter_count
$entry.parameters.coverage_aware_weights.support_map.groups | ConvertTo-Json -Depth 10
$entry.optimization.stages
$entry.optimization.parameter_bounds.weights
```

期望值为：direct为0，区域状态为 `complete`，目标为 `real_points`，
`weight_group_ids=[0,0,1,2]`，评分模式为 `group_mean`，weights长度30，slopes外层
长度10且每行长度2。当前结果识别出12个自由weight和18个派生weight：

| 组 | 真实点 | 自由档 | 派生档 |
|---|---|---|---|
| 0 | 19–20 | 5、6、7、8 | 0–4、9 |
| 1 | 21 | 5、6、9 | 0–4、7、8 |
| 2 | 22 | 3、4、5、6、9 | 0–2、7、8 |

档位0–9对应坐标 `[0, 0.8, 1.2, 2.0, 3.0, 4.0, 10.0, 20.0,
35.0, 45.0] m^-1`；其中0表示低于第一个threshold的区间。上述自由档集合由本次
数据和覆盖阈值产生，不应硬编码为其他传感器或其他数据集的默认答案。

本次weight阶段从loss `38.929973` 收敛到 `12.776172`。12个自由参数中5个达到
下限、1个达到上限；18个派生参数没有触边。`complete/converge` 只说明优化器完成，
不代表动态过弯、回直残差或区域交界已经通过验收，仍需按第6步回放和动态检查。

#### 4. 与基础包拼接为direct0动态demo包

常规 `tools/sensor_parameter_package.py --base_results ... --results ...` 要求基础结果和
新end5cm结果都具备0/120/240三个方向，不能用于只有direct0的新结果。此时使用专门的
`tools/build_single_direction_demo_package.py`：

```powershell
python tools/build_single_direction_demo_package.py `
  --base-package params/06B6_NeTi_v2_ftube_nophase_endpointcalib_endslopenew.json `
  --override-result calibration_results/06B6_NeTi_v2_ftube-20260920T162538+0800-direct0-f82abf/results.json `
  --output params/06B6_NeTi_v2_ftube_nophase_coverageaware_endweights_direct0_demo.json `
  --direction 0
```

拼接行为是：

- full和end15cm完整保留基础包内容；
- end5cm/direct0替换为新结果中的30个weights、继承的 `10×2` slopes、局部相位、
  优化状态和覆盖感知support map；
- 参数结构内部的end5cm 120/240槽位复制direct0，仅用于满足现有多区域装配器的
  三方向schema，不能当作120/240定标结果；
- 运行范围固定为 `exp_directs=[0]`、`direction_reference_direct=0`，并关闭
  `direction_blend_enabled`；
- `deployment_ready=False` 保留，表示这是单方向实验包，不是三方向部署包；
- provenance记录基础包和覆盖结果路径，便于追溯。

#### 5. 核验拼接包

下面命令只读取JSON，不连接解调仪：

```powershell
$p = Get-Content 'params/06B6_NeTi_v2_ftube_nophase_coverageaware_endweights_direct0_demo.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$p.shared_parameters.calibration_experiment_parameters.exp_directs
$p.shared_parameters.dynamic_display_parameters.direction_reference_direct
$p.shared_parameters.dynamic_display_parameters.direction_blend_enabled
$p.shared_parameters.runtime_control_parameters.end5cm_coverage_aware_weights
$p.regions.end5cm.weights.'0'.Count
$p.regions.end5cm.slopes.'0'.Count
$p.regions.end5cm.coverage_aware_weights.free_parameter_count
$p.multi_region.deployment_ready
$p.provenance.single_direction_demo
```

期望得到：`exp_directs=[0]`、参考方向0、方向混合关闭、覆盖感知开启、30个weights、
10行slopes、12个自由参数以及 `deployment_ready=False`。运行时不需要再次计算
support map；完整30 weights已经写入参数包。

#### 6. 运行动态demo并验收

```powershell
python main.py `
  --task demo `
  --multi_region_calib True `
  --sensor_params params/06B6_NeTi_v2_ftube_nophase_coverageaware_endweights_direct0_demo.json `
  --direction_reference_direct 0 `
  --rot_ang -30 `
  --use_stored_zero false
```

不要添加 `--direction_blend_enabled`，也不要把 `direction_reference_direct` 改成120或240。
`deployment_ready=False` 的warning不会阻止demo，它用于提醒该包只能做direct0动态实验。
覆盖感知开关控制优化阶段的自由参数选择；recon/demo直接使用已经展开的30 weights，
不要求运行时的 `optimization_region=end5cm`。若旧电脑仍报
`end5cm_coverage_aware_weights 仅允许 optimization_region=end5cm`，说明其 `main.py`
尚未同步运行时校验修复；应同步当前分支代码。临时排查可在命令末尾加
`--end5cm_coverage_aware_weights False`，这只关闭优化控制标记，不会改写参数包中已经
展开的weights。

验收至少包括：大半径下full区域精度，30/20/15mm时点21和点22的曲率，
end15cm/end5cm交界处的位置与切向连续性，末端累计弯曲角，回直后的反向残余弯曲，
以及不同方向弯曲时是否出现额外扭转。安装后数据只重新拟合了direct0 weights，不能据此
判断120/240方向已完成同配置定标，也不能把材料迟滞、安装应变传递和算法误差混为同一结论。

### 单方向、单区域回放

仅优化end5cm/direct0时，可将该区域 `results.json` 的20个weights、10×2 slopes与 `global_phases_set` 传给单区域recon：

```bash
python main.py --task recon --multi_region_calib False --optimization_region end5cm --direct 0 --weights "{0: <weights列表>}" --slopes "{0: <slopes二维列表>}" --global_phases_set <保存的相位>
```

单区域recon默认将实验方向范围限制为当前 `direct`，不要求其他两个方向参数；显式 `--exp_directs "[0]"` 也可使用。显式指定多个实验方向时，参数校验仍要求该列表内每个方向都有参数，且列表必须包含当前direct。优化任务和多区域recon保留原方向范围。回放需与优化时的区域thresholds、分段、end_weights/end_start及插值设置一致；这只重构局部5cm，不代替完整传感器参数包。

默认 `--end15cm_point_calib False` 和 `--end5cm_point_calib False` 保留所有区域原有几何优化。两个开关分别只控制 end15cm、end5cm 的真实点目标，full 始终使用几何目标；批量调度会分别解析每个区域的有效模式。两区域共用下述方向与曲率幅值损失定义，但 `end5cm_independent_weights`、三组权重评分、coverage-aware 权重和 `optim_weights_only` 仍仅支持 end5cm。

单独优化 end15cm 时，例如：

```bash
python main.py --task optim --sensor_params params/08B5_NeTi_end5NewOptim.json --multi_region_calib False --optimization_region end15cm --end15cm_point_calib True --direct 0
```

已有参数包不会因打开开关而自动变更；需重新运行优化并导出新参数包，才会保存 end15cm 的 `calibration_objective=real_points`。

已有参数包可以作为导出工具的 `--base_results`，再叠加三个方向的同一区域结果。下例以已包含新 end5cm 参数的 08B5 包为底包，仅替换 end15cm；full 和 end5cm 保持原样：

```powershell
python tools/sensor_parameter_package.py `
  --base_results params/08B5_NeTi_end5NewOptim.json `
  --results `
    calibration_results/08B5_NeTi-20260923T161612+0800-direct0-dd1bff/results.json `
    calibration_results/08B5_NeTi-20260923T161916+0800-direct120-23743b/results.json `
    calibration_results/08B5_NeTi-20260923T161921+0800-direct240-d2ba95/results.json `
  --output params/08B5_NeTi_end15Point_end5NewOptim.json
```

`--base_results` 也继续接受旧的三份完整 `results.json`。两种底包模式都允许 `--results` 仅包含 end15cm 或仅包含 end5cm，且必须覆盖 0/120/240 三方向；输出包可再次作为下一次的底包。参数包模式不支持 `--comparison`，并要求输出到不同于底包的新文件；每次替换区域后部署验证门禁会重置，需重新验证。

```bash
python main.py --task optim --multi_region_calib True --end5cm_point_calib True --weights None --slopes None --direct 0
```

再分别运行 direct 120、240。也可关闭批量模式并指定 `--optimization_region end5cm` 单独定标。若需当前parser的区域配置，省略旧 `--sensor_params`；加载旧包仍会继承其区域配置，显式开启新优化开关并不会自动改动旧weights布局。

两阶段目标为：

1. **方向阶段**：保持初始化或上游固定参考确定的 `global_phases_set`；每个非零圆弧样本以首个真实点为方向参考，计算真实点的 `mean(1-cos(angle_i-angle_first))`，再按半径样本等权平均。当前相位累计算法中，首点不受候选slope影响，因此参考不会随优化器改变。方向比较在滤波/插值之前执行，数值零曲率点不比较方向；首点无有效曲率时明确报错。
2. **幅值阶段**：固定slope，使用 `folder_path` 中的实际应变，按真实半径 `radii` 得到目标 `kappa=1000/radius_mm`，计算各真实点 `mean((measured_kappa/kappa-1)^2)`，再按半径样本等权平均。补偿曲率仍由生产评分、普通/末端weights及应变转换产生。

只支持 `circ` 数据；半径0直线状态不进入新拟合，仍保留在最终几何回放。半径须有限、非负且至少有一个正值。虚拟点不作独立测量，不参与新loss；运行时仍复制补偿后的末点并执行原有插值、标架和滤波流程。

两阶段loss均无量纲，含义不同，不可相互比较，也不能与旧几何loss直接比较。现有停止阈值、权重界限、slope界限、冻结配置和按曲率混合规则继续适用；本改动没有自动扩大界限或增加等级间约束。最终正常几何误差仍另行保存，comparison表格继续使用完整传感器长度百分比，参数明细标注优化目标和阶段loss定义。

`results.json` 的context/parameters保存 `calibration_objective=real_points` 或 `geometry`，optimization记录阶段loss定义。导出要求同一区域三个方向的模式一致；参数包按end5cm的实际模式回填parser开关，旧包缺字段时关闭。开关只控制优化，不会通过运行时切换重新计算已保存的参数。

本模式减少局部方向扭转作为几何拟合自由度，但不重新对齐首点绝对方向、不保证全长交界连续，也不证明幅值拟合后几何已准确；应继续使用定标回放核验。

2026-09-18适配验证：相关测试130项通过。实际end5cm CSV初始化读取14个非零半径；weights为20、slopes为10×2，末端mask为 `[False,False,False,True]`。初始方向loss为0.305526，初始曲率平方相对误差为0.215829，均有限；仅初始化与计算loss，未运行优化。全量测试209项通过、3项既有失败（UDP锚点两项、向量窗口parser默认值与测试预期不一致一项）。

## 本次验证

使用三个实际目录，运行真实 Optimiser 初始化、CSV 读取、中心补偿、空间裁剪与正常模式重构，没有连接硬件、打开 GUI 或执行参数优化。

- full：3 个方向 × 9 个半径/直线状态，共 27 条。
- end15cm：3 × 13，共 39 条。
- end5cm：3 × 15，共 45 条。
- 全部 111 条形状均输出有限值，所需半径没有缺失；每条输出 120 个插值点。
- 几何、点数和末端长度符合上表，详细结果见同目录 `calibration-regions-validation.json`。

这验证配置、读取和重构链路可用，不证明重新定标后的精度提升。

修改前完整测试基线为 79 passed、3 failed。批量优化和评分诊断加入后，区域相关测试覆盖 parser 迁移、区域隔离、显式 None、失败保留、参数转换及生产评分质量。

本轮最终完整测试为 **144 passed、2 failed**。剩余两项均是既有 UDP anchor offset 测试；从关键基线提交到当前分支，`demonstrator.py`、入口约束实现和该测试没有差异。本次新增和直接相关的定向测试全部通过。
