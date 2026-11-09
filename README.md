## 1. 简介

该代码库包含形状感知任务代码，可支持多种方案的重构、参数优化与动态展示。

## 2. 依赖环境

本项目基于 Python 运行，主要依赖以下库：
- numpy
- scipy
- pandas
- matplotlib
- pySerial
- PyQt5
- vtk
在terminal中输入并运行指令pip install -r requirements.txt来进行安装

## 3. 代码结构
形状感知代码库/
├─ main.py                  # 主入口
├─ sensor.py                # 传感器参数与数据处理
├─ initialiser.py           # 初始化全局相位补偿与初始扭转系数
├─ reconstructor.py         # 形状重构
├─ optimiser.py             # 参数优化
├─ demonstrator.py          # 基础动态展示
├─ proto_demonstrator.py    # 完整样机动态展示
├─ IMU.py                   # IMU数据接受与处理文件
├─ visualisor.py            # 可视化
├─ utils.py                 # 字典递归处理方法等可以缩短代码、降低优化难度的工具
├─ model.stl                # 用于动态展示的人体模型
├─ ./tools                  # 用于部分临时任务的简易脚本
├─ requirements.txt         # 依赖环境
└─ README.md                # 当前文件
(注：如后续发现有更多参数需要手动调整，请参照当前格式更新至main.py中)

## 4. 使用说明

### 曲率空间插值模式

`main.py` 的 `--curvature_interp` 参数会同时作用于正式重构、slopes 优化和 weights 优化：

- `hermite`：原始角度 Hermite + 标量曲率 Hermite，默认基线。
- `scalar_pchip`：角度保持 Hermite，标量曲率改用 PCHIP。
- `pchip`：`scalar_pchip` 的兼容别名。
- `vector_linear`：构造曲率向量分量后分别做线性插值。
- `vector_pchip`：构造曲率向量分量后分别做 PCHIP 插值。

例如，使用曲率向量 + 分量 PCHIP 重新优化当前方向的 weight/slope：

```bash
python main.py --task optim --curvature_interp vector_pchip --weights None --slopes None --direct 0
```

若要与原始算法对比，只需保持其余参数一致并切换模式：

```bash
python main.py --task recon --curvature_interp hermite
python main.py --task recon --curvature_interp vector_linear
python main.py --task recon --curvature_interp vector_pchip
```

`nonnegative_curvature` 仅改变标量曲率模式；曲率向量模式通过 `hypot` 恢复曲率大小，结果天然非负。

### 4.1. 参数优化
#### 4.1.1. 初始化
在main.py最下方的main()方法中找到硬件参数、标定实验参数以及优化使用的超参数并按照说明修改其default值。

### 4.0 多区域模式

`multi_region_calib` 控制一次任务是使用单一区域，还是批量优化/完整拼接三个区域。当前默认区域为：

- `full`：完整传感器。
- `end15cm`：末端 15 cm。
- `end5cm`：末端 5 cm。

`optimization_region` 指定单次使用的区域；`optimization_regions` 指定 `optim` 在多区域模式下依次处理的区域，默认值为 `['full', 'end15cm', 'end5cm']`。

| task | `multi_region_calib=False` | `multi_region_calib=True` |
|---|---|---|
| `init` | 初始化 `optimization_region` 指定的一个区域 | 仍只初始化 `optimization_region`，同时校验三个区域与全长分段是否兼容 |
| `optim` | 只优化 `optimization_region` | 按 `optimization_regions` 依次优化 full、end15cm、end5cm |
| `recon` | 重构 `optimization_region` 指定的单一区域 | 使用完整传感器点位和参数包中的三个区域参数逐点拼接重构 |
| `demo` | 使用当前单区域参数动态展示 | 使用完整传感器点位和参数包中的三个区域参数动态拼接重构 |

#### 4.0.1 init：逐段检查初始化结果

`init` 不会自动遍历三个区域。需要分别指定 `optimization_region` 运行，从而检查每段数据、局部相位和分段拟合：

```powershell
python main.py --task init --multi_region_calib True --optimization_region full --weights None --slopes None
python main.py --task init --multi_region_calib True --optimization_region end15cm --weights None --slopes None
python main.py --task init --multi_region_calib True --optimization_region end5cm --weights None --slopes None
```

设置为 `True` 时，程序还会检查三个区域是否能映射到同一套全长点位和全长分段。只想检查一个尚未加入完整区域配置的区域时，可使用 `--multi_region_calib False`。

#### 4.0.2 optim：按方向优化全部区域

下面一条命令会在同一次运行中依次优化 full、end15cm 和 end5cm，但只处理 `direct=0` 这一个标定方向：

```powershell
python main.py --task optim --multi_region_calib True --weights None --slopes None --direct 0
```

0°、120°、240° 必须分别运行：

```powershell
python main.py --task optim --multi_region_calib True --weights None --slopes None --direct 0
python main.py --task optim --multi_region_calib True --weights None --slopes None --direct 120
python main.py --task optim --multi_region_calib True --weights None --slopes None --direct 240
```

每次运行都会创建独立目录：

```text
calibration_results/<sensor_id>-<本地时间>-direct<方向>-<随机编号>/
```

目录中的 `results.json` 保存该方向三个区域的 weights、slopes、误差和优化状态。三个方向完成后，用 `tools/sensor_parameter_package.py` 合并参数；具体导出及定标回放验证命令见 [多区域定标说明](docs/calibration-regions.md)。

如果只需重新优化一个区域，应关闭多区域模式：

```powershell
python main.py --task optim --multi_region_calib False --optimization_region end5cm --weights None --slopes None --direct 0
```

#### 4.0.3 recon：单区域与完整拼接回放

单区域重构使用 `multi_region_calib=False`。加载参数包后，程序会选择对应区域自己的 thresholds、weights、slopes 和局部分段：

```powershell
python main.py --task recon --sensor_params params/06B6_NeTi_v2_ftube_multi_region_validated.json --multi_region_calib False --optimization_region full --direct 0
python main.py --task recon --sensor_params params/06B6_NeTi_v2_ftube_multi_region_validated.json --multi_region_calib False --optimization_region end15cm --direct 0
python main.py --task recon --sensor_params params/06B6_NeTi_v2_ftube_multi_region_validated.json --multi_region_calib False --optimization_region end5cm --direct 0
```

完整多区域重构必须同时提供参数包并设置 `multi_region_calib=True`：

```powershell
python main.py --task recon --sensor_params params/06B6_NeTi_v2_ftube_multi_region_validated.json --multi_region_calib True --direct 0
```

此时程序固定采用完整传感器几何。每个区域先根据自己的曲率 thresholds 和 sigmoid 设置计算等级，再从对应方向的 weights、slopes 中逐点装配参数；`optimization_region` 不再决定裁剪范围。

#### 4.0.4 demo：动态检查区域拼接

完整多区域动态展示使用已合并的参数包。推荐使用带定标回放证据的 `_validated.json`：

```powershell
python main.py --task demo `
  --sensor_params params/06B6_NeTi_v2_ftube_multi_region_validated.json `
  --multi_region_calib True `
  --direction_reference_direct 120
```

multi-region demo 当前使用 `direction_reference_direct` 指定的一套方向参数，不支持三方向动态软混合，因此不要添加 `--direction_blend_enabled`。可将参考方向改为 `0`、`120` 或 `240`，分别观察动态效果。

参数包中 `deployment_ready=False` 时，demo 会在命令行打印 `[WARNING]`、参考方向和门禁失败原因，但仍继续运行，便于实际检查 end15cm/end5cm 交界处的曲率、位置和姿态连续性。该告警表示离线验证尚未通过，不会改变本次动态重构使用的参数。

`06B6_NeTi_v2_ftube_multi_region.json` 与 `_validated.json` 的重构参数相同；后者额外保存 score、相位传递和完整定标回放证据，因此动态验证优先使用 `_validated.json`。

若已有使用当前 --sensor_id 命名的文件夹，将其更名为 --sensor_id(归档)

若当前任务为LUNA数据分析，则阅读各通道结尾为gages.tsv的文件并按照以下步骤更新 --sensing_ranges 的default值:
    确保通道顺序与 --active_channels相同后，对于各个通道：
        从文件中找到传感点间距、(x轴， start)、(x轴， 1)、(x轴， 2)
        将该通道对应range改为 (((x轴， 1)-(x轴， start))/(传感点间距/1000), ((x轴， 2)-(x轴， start))/(传感点间距/1000))

    在terminal中输入并运行指令 python main.py --task init --weights None --slopes None 以生成初始Strain_Data图
    反复调整 --sensing_ranges 的default值直到 --exp_directs 中所有 方向 的 --sensor_id/--active_channels/--segmentation/方向/init_plots/Strain_Data_circ.png 中三个子图的首尾均接近水平轴
    在terminal中输入并运行指令 python main.py --task init --weights None --slopes None 进行检验

在terminal中输入并运行指令 python main.py --task init --weights None --slopes None
修改 --global_phases_set 的default值为 global phase
查看所有 --exp_directs 中的 方向 的 --sensor_id/--active_channels/--segmentation/方向/init_plots/Angle_Data.png 并将记录所有与S形弯标定形状转向位置对应处的角度跳变，修改 --turn_threshold 的default值以确保所有跳变均大于它的同时非跳变处的角度改变小于它

反复调整 --segmentation 的default值直到所有 方向 的 --sensor_id/--active_channels/--segmentation/方向/init_plots/Multi-Radius_Segmented_Linear_Fitting.png 分段合理
在terminal中输入并运行指令 python main.py --task init --weights None --slopes None 进行检验

确定 --segmentation 后检查各个 --sensor_id/--active_channels/--segmentation/方向/recon_plots/--rot_ang/形状 中最新的视频
分别尝试 --rot_dir 的两种取值并对比哪一个重构结果更合理
在terminal中输入并运行指令 python main.py --task init --weights None --slopes None 完成初始化

#### 4.1.2. 旋转角度优化
在terminal中输入并运行指令 python main.py --task ang --weights None --slopes None
若形状偏转不严重，可以先跳过该步骤，直接进入应变权重与扭转系数优化

#### 4.1.3. 应变权重与扭转系数优化
从初始化结束后的打印信息中获取：
    最优旋转角度
    最小误差
修改 --rot_ang 的 default 值为最优旋转角度。
在 len(--exp_directs) 个不同 terminal 中分别输入并运行：
    打开1-3个terminal，数量等同于已进行数据采集的方向数量。假设三个方向都已采集。分别运行
python main.py --task optim --weights None --slopes None --direct 0
python main.py --task optim --weights None --slopes None --direct 120
python main.py --task optim --weights None --slopes None --direct 240
当前已启用先用完美曲率优化扭转slope，再优化weight的流程。
(注：建议将这3个terminal与初始化的terminal分开)
(注: 若旋转角度差距不大，可以跳过旋转角度优化，因为这种情况下，直接从旋转角度0.0开始优化的结果会更好)


#### 4.1.4. 循环优化(大部分时候不需要)
反复执行以下操作直至 最优旋转角度 不再变化：
    从各个terminal的打印信息中获取：
        最优权重
        最优扭转系数
    修改 --weights 各方向为对应terminal的最优权重
    修改 --slopes 各方向为对应terminal的最优扭转系数
    修改 --ang_step 和 --ang_range 为原来的0.1倍(可自行判断)
    在初始化terminal中输入并运行指令 python main.py --task ang
    从打印信息中获取：
        最优旋转角度
        最小误差
    修改 --rot_ang 的default值为 最优旋转角度
    按情况在 len(--exp_directs) 个不同的terminal中分别输入并运行指令:
        python main.py --task optim  --direct 方向

#### 4.1.5. 更换超参
若前面几个步骤未能给出令人满意的结果，可对优化使用的超参数进行修改。若优化结果的重构图像中各个形状的半径显然不正常，则优先修改--bounds，否则按照文件中从上到下的优先级修改其余超参数。

#### 4.1.6 效果检验
从3个terminal的打印信息中获取：
    最优权重
    最优扭转系数
修改- -weights 各方向default值为对应terminal的最优权重
修改 --slopes 各方向default值为对应terminal的最优扭转系数
选择想要检查的 方向
在terminal中输入并运行指令 python main.py --task recon --direct 方向
若效果良好，将所有parser.add_argument赋值并粘贴进以 --sensor_id 命名的txt文件中，文件储存于params文件夹中
(注：建议将这个terminal与初始化的terminal和优化的3个terminal分开)

### 4.2 重构
将对应的 params/--sensor_id.txt 中的内容复制并粘贴替代从 parser = argparse.ArgumentParser() 到 args = parser.parse_args() 的部分
选择想要重构的 方向
在terminal中输入并运行指令 python main.py --task recon --direct 方向

### 4.3 动态展示
将对应的 params/--sensor_id.txt 中的内容复制并粘贴替代从 parser = argparse.ArgumentParser() 到 args = parser.parse_args() 的部分

#### 4.3.0 支气管入口锚点约束

动态展示可分别控制支气管入口的位置平移锚定和姿态旋转锚定：

```powershell
python main.py --task demo --anchor_translation_enabled
python main.py --task demo --anchor_rotation_enabled
python main.py --task demo --anchor_translation_enabled --anchor_rotation_enabled
```

约束约定如下：

- 第一帧光纤末端视为已到达主隆突；默认入口坐标从该末端沿三维光纤中心线反向累计 6 cm，并在跨越目标弧长的线段内插值得到。该计算不再假设光纤沿全局 X 方向延伸。
- 机械臂 UDP 数据和 Pickle 中的 `insert_value` 单位为 mm。
- 开头的 0 是通讯占位值；首个有限非零值作为推进量零点，当前相对推进量为“当前值减零点值”。
- 每帧从光纤末端沿三维折线弧长反推 `入口距离 + 相对推进量`；位置和经过 `rot_matrix` 的切向 `T` 使用同一线段及弧长比例插值。
- `--anchor_translation_enabled` 只固定入口位置，不旋转曲线。
- `--anchor_rotation_enabled` 只用最小旋转对齐入口切向 `T`，不使用 `Y/Z`，也不施加绕 `T` 的滚转；平移关闭时绕当前入口点旋转，不改变入口位置。
- 两个新开关同时开启时，后续帧先平移入口点到固定坐标，再绕该固定坐标作无滚转的最小旋转，使入口位置与切向 `T` 同时保持锚定。
- 约束不重采样光纤，输出仍为 60 个三维点。仅当旋转开关开启时，`End_pose` 才在原有 `rot_ang` 协议补偿后整体乘入口锚定旋转。
- 两个新开关都不添加时保持原来的动态坐标行为。旧参数 `--anchor_constraint_enabled` 保留兼容，等价于同时开启两个新开关。

启动时可显式设置入口距离：

```powershell
python main.py --task demo --anchor_translation_enabled --anchor_rotation_enabled --anchor_offset_m 0.06
```

运行中的单向 UDP 配置、reset 和本机状态查询协议见
[入口锚定 UDP 外部控制协议](docs/入口锚定UDP外部控制协议.md)。
外部 UDP 传入的 `entrance_offset_m` 表示导管末端到入口的距离；由于传感器位于导管末端后方 0.01 m，Demonstrator 会先减去 0.01 m，再将有效距离交给锚定算法。

动态 JSON 数据在任一入口锚定开关开启时，会对曲线和当前入口/旋转中心执行相同的软件坐标变换：坐标由 m 转为 mm，X 再减去机械臂当前绝对推进读数。`sendObj["anchor_point"]` 保存变换后的入口点；两个锚定开关都关闭、入口点尚未生成或推进读数无效时为 `null`。仅旋转锚定时，该点是当前帧切向 `T` 的插值位置及旋转中心。

新记录的 Pickle 中，`r_results` 继续保存锚定后的曲线以兼容旧读取程序；`r_results_before_anchor` 保存锚定前的 `r_results_postrot`；`anchor_point_m` 保存软件坐标变换前、单位为 m 的每帧入口/旋转中心。

对 Demonstrator 已记录的旧 Pickle 可继续离线回放；旧文件没有逐点 `T/Y/Z`，因此离线工具保持位置平移锚定：

```powershell
python tools/render_anchored_pickles.py `
  'E:\shape_exp\0820光明豬肺實測\待分析的数据' `
  --from-time 1922 `
  --to-time 1956 `
  --trajectory-output 'E:\shape_exp\0820光明豬肺實測\fiber_tip_trajectories' `
  --video-output 'E:\shape_exp\0820光明豬肺實測\pickle_videos'
```

工具会生成带 `_anchored_` 后缀的新 PNG 和 MP4，不覆盖原始 Pickle 或原有结果。可用 `--max-frames` 控制每个视频的最大采样帧数，并用 `--overwrite` 覆盖已有的锚点结果。

动态展示支持以下两种参数使用方式。

#### 4.3.1 只使用精度最高的一套方向参数

先从 0°、120°、240° 三套标定参数中选出重构精度最高的一套，并通过 `--direction_reference_direct` 指定方向。不要添加 `--direction_blend_enabled`，程序就会在整个动态过程中固定使用该方向的 `weights` 和 `slopes`。

例如，120° 参数精度最高时：

```powershell
python main.py --task demo --direction_reference_direct 120
```

如果最高精度参数是 0° 或 240°，将命令末尾改为：

```powershell
--direction_reference_direct 0
```

或：

```powershell
--direction_reference_direct 240
```

该模式也用于三方向软过渡启用前的方向坐标校准。建议先使用最高精度的单套参数检查并确定 `rot_ang`，例如：

```powershell
python main.py --task demo `
  --direction_reference_direct 120 `
  --rot_ang 旋转角度
```

其中 `旋转角度` 应替换为实际数值。

#### 4.3.2 打开 0°/120°/240° 三方向软过渡

确认三套方向参数均已写入 `--weights` 和 `--slopes`，且使用最高精度单套参数完成 `rot_ang` 校准后，添加 `--direction_blend_enabled`：

```powershell
python main.py --task demo `
  --direction_reference_direct 120 `
  --rot_ang 旋转角度 `
  --direction_blend_enabled
```

`--direction_reference_direct` 在软过渡模式中仍然需要：程序先用该方向的第 0 曲率等级 slope 粗略估计当前弯曲方向，再在相邻的 0°、120°、240° 参数之间进行半余弦插值，并用混合后的完整参数完成正式重构。

软过渡的稳定参数可按需显式设置：

```powershell
python main.py --task demo `
  --direction_reference_direct 120 `
  --rot_ang 旋转角度 `
  --direction_blend_enabled `
  --direction_min_curvature 0.5 `
  --direction_min_consecutive 3 `
  --direction_consistency_threshold 0.6 `
  --direction_smooth_alpha 0.15
```

各参数含义：

- `direction_min_curvature`：方向估计所需的最小有效曲率；低于该值时冻结上一帧方向权重。
- `direction_min_consecutive`：近端稳定弯曲区要求的最少连续点数。
- `direction_consistency_threshold`：弯曲区最低方向一致性；低于该值时冻结上一帧方向权重。
- `direction_smooth_alpha`：方向权重的跨帧指数平滑系数，越小越稳定但响应越慢，取值范围为 `(0, 1]`。

注意：

- `--direction_blend_enabled` 是开关参数，不带该参数即为关闭，不能写成 `--direction_blend_enabled False`。
- 三套 `weights` 的数组形状必须一致，三套 `slopes` 的数组形状也必须一致。
- 三方向参数需要采用相同的曲率等级数、阈值定义、分段方式和参数排列约定。
- 应先关闭软过渡校准 `rot_ang`，再打开软过渡；否则角度坐标偏差可能导致程序稳定地混合错误方向的参数。
- 单套模式和三方向软过渡都只影响动态展示，不改变静态参数优化流程。

更完整的原理和排查方法见 [动态三方向参数软过渡：原理、注意事项与踩坑记录](docs/动态三方向参数软过渡_原理_注意事项与踩坑记录.md)。

### 辅助工具目录

参数包导出与导入位于 `tools/sensor_parameter_package.py`，定标回放验证位于 `tools/calibration_validation.py`，零点文件处理位于 `tools/zero_reference.py`，通用辅助函数位于 `tools/utils.py`。代码中使用 `from tools.模块名 import ...` 导入。

在项目根目录执行工具，例如 `python tools/sensor_parameter_package.py --help`，也可用 `python -m tools.sensor_parameter_package --help`。`main.py` 的任务命令和 `params` 文件路径保持原用法。

### 区域独立末端权重

`calibration_regions` 中的 `end_weights/end_start` 决定各区域是否另算末端权重。当前parser区域默认值为：full、end15cm关闭；end5cm开启，`end_start=-1`，只补偿全局第22个真实点。虚拟末点随后复制第22点补偿后的曲率。

设某区域有N个曲率等级：关闭时weights长度为N；开启时长度为2N，前N个为普通点权重，后N个为末端点权重，两组按该区域同一套实测曲率评分混合。slopes仍为N行，不增加一组。此功能沿用原有先slope、后weight优化，不增加单调性约束。

```bash
python main.py --task optim --multi_region_calib True --weights None --slopes None --direct 0
```

分别将direct换为120、240运行。不要为批量任务传入全局`--end_weights/--end_start`，请在区域字典中修改；单区域对照可使用`--optimization_region end5cm --end_weights False`。新配置下end5cm有10个等级，优化生成20个weights，slopes保持10×2。

导出工具会保存每个区域的end_weights、end_start和完整双组weights，main及多区域recon/demo加载后按各区域真实support点范围分配。旧参数包缺少字段时保持关闭，不自动复制旧weights生成新定标结果。加载旧包时会继承其旧区域配置；要使用当前parser的新区域默认值重新优化，请省略`--sensor_params`，优化后导出到新的文件名。

### end5cm 真实点方向与曲率幅值定标

若需要19–20普通组、21独立组、22独立组，另加 `--end5cm_independent_weights True`。此时end5cm weights为三组共30个，slopes仍10×2；单区域recon也需开启此布局，参数包加载会自动继承。旧20参数保持兼容，不能自动复制为新30参数。仅重跑end5cm时，可通过导出工具 `--base_results` 复用旧full/end15cm结果。完整执行步骤见 [三组weights执行流程](docs/calibration-regions.md)。

`--end5cm_point_calib` 默认 `False`，只改变 end5cm 的优化目标。开启后仍先优化 slope、再优化 weight：在区域 `global_phases_set` 已确定的情况下，以每个非零圆弧样本的首个真实点方向为固定参考，最小化真实点19–22的圆周方向误差；随后按 `folder_path` 中真实定标数据和 `radii` 中真实半径，最小化各真实点曲率相对于 `1000/radius_mm` 的平方相对误差。直线状态不参与这两项拟合，虚拟点、空间滤波和插值也不进入新目标函数。

```bash
python main.py --task optim --multi_region_calib True --end5cm_point_calib True --weights None --slopes None --direct 0
```

分别将 direct 换为120、240运行。full、end15cm继续采用原几何目标；end5cm的thresholds、双组weights、10×2 slopes及 `end_start=-1` 保持现有配置。新开关不自动修改末端权重范围，也不增加等级间单调性或平滑约束。最终仍通过正常重构报告几何误差，不能用新阶段loss替代回放验收。

新模式仅支持圆弧 `circ`，且需要至少一个有限正半径。结果和导出包记录各区域 `calibration_objective`；旧包缺字段时按 `geometry` 处理，加载新包时继承开关，显式 `--end5cm_point_calib False` 可重新优化原模式对照。recon/demo不因这个开关改变重构公式；它们使用已导出的参数。当前开关不优化全局相位，首点方向的绝对准确性与交界相位仍需回放核验。

### 固定上游相位与跨界 slope 对比测试

`--use_full_transported_phase` 默认 `False`。开启后，按照 full → end15cm → end5cm 顺序优化：

```bash
python main.py --task optim --multi_region_calib True --use_full_transported_phase True --weights None --slopes None --direct 0
```

对 `120`、`240` 分别运行，再用 `tools/sensor_parameter_package.py --results ... --output ...` 合并三方向新结果。建议使用新的输出文件名，例如 `params/06B6_NeTi_v2_ftube_multi_region_full_phase.json`，保留原参数用于对照。导出工具从优化结果记录识别新模式；旧参数包不会自动获得新相位。

参考相位只使用上游非零圆弧弯曲样本，排除半径 `0` 的直线状态。各样本按原有曲率评分混合上游 slope，推算到区域前一个真实点，再对相位取圆周均值。跨界间隔（例如全局点 15→16、18→19）固定使用 full 第 0 档 slope，与当前曲率档位无关；区域内部仍使用该区域自己的 thresholds、slope 和 weight。end5cm 的上游包含已优化的 end15cm。

局部优化开始前一次性固定相位，整个优化期间不随候选 slope 更新。两阶段优化、损失和选档流程保持原逻辑。结果同时保存物理裁剪起点与首个真实点的相位，当前算法将后者作为 `global_phases_set`。full 第 0 档指 slope 数组的第 0 行，并不使用直线状态的相位。

独立优化 end15cm 可以使用含 full 结果的来源参数包：

```bash
python main.py --task optim --sensor_params params/06B6_NeTi_v2_ftube_multi_region.json --multi_region_calib False --optimization_region end15cm --use_full_transported_phase True --weights None --slopes None --direct 0
```

独立优化 end5cm 则要求来源包中同方向的 end15cm 已使用新模式优化并导出。来源数据目录仍需可访问。新模式目前支持正向点位。

加载新参数包时，recon/demo 自动继承新模式；只对包含新模式局部结果的方向固定跨界 slope：

```bash
python main.py --task demo --sensor_params params/06B6_NeTi_v2_ftube_multi_region_full_phase.json --multi_region_calib True
python main.py --task recon --sensor_params params/06B6_NeTi_v2_ftube_multi_region_full_phase.json --multi_region_calib False --optimization_region end15cm --direct 0
```

关闭优化开关可生成原逻辑对照结果。运行新包时显式传入 `--use_full_transported_phase False` 可对比跨界装配策略；这不会重新优化参数，因此完整算法对比应分别优化两套参数。实际运行的上游相位仍随应变和曲率选档变化，固定参考是定标弯曲样本的均值，不能保证每帧相位完全一致；定标回放验证会计算实际装配相位与固定参考的偏差。末端真实点幅值偏小的修正留待单独处理。

## 5.当前版本信息
版本号：v9
日期：2026.06.16
创建人：高至简
主要改动：
- 重构 straight_trim 裁剪逻辑，使数据、采样点、误差计算和可视化统一使用有效段
- 添加 end3 标定形状及其理论形状/理论曲率支持
- 将优化流程改为 slopes 强制理论曲率、weights 正常曲率的两阶段优化
- 添加完整样机动态展示原型，支持人体模型、入体长度、曲率入口识别和自动校准

## 6. 版本记录
| 版本号 | 日期 | 修改人 | 主要改动 | 备注 |
|---|---|---|---|---|
| v0 | 2026-03-18 | 高至简 | 统合重构LUNA与肠镜FBG形状重构、参数优化代码以及动态展示代码；整理统一入口与基本使用流程 | 初始版本 |
| v0.1 | 2026-03-23 | 高至简 | 添加适用于支气管镜任务的数据处理方法，并将数据处理接口按解调仪品牌分类（FiberTecc、Hippo、LUNA） | 无 |
| v1 | 2026-03-30 | 高至简 | 添加S形弯曲与末尾额外卷曲两种形状的配套算法；修复了数据未按通道排序的bug和扭转系数优化初始化使用错误初始值的bug | 无 |
| v2 | 2026-04-01 | 曹丹倩 | 修改数据处理与可视化模块以兼容任意数量的通道 | 该版本并非基于v1的拓展，而是平行的 |
| v3 | 2026-04-02 | 高至简 | 融合v1与v2的功能 | 无 |
| v4 | 2026-04-08 | 高至简 | 添加零螺距与螺旋的重构与可视化，并调整了优化顺序 | 该版本零螺距优化未使用螺距误差 |
| v4.1 | 2026-04-16 | 曹丹倩 | 添加了对Nan值与数据异常点的排除 | 当存在整个csv文件所有行都存在Nan值的情况时会有问题 |
| v4.2 | 2026-04-22 | 高至简 | 添加了扭转系数优化上下界；在某一subfolder中存在所有行都有nan值得情况下，只有该subfolder对应的标定形状会从重构与优化中被忽略；修复了_F_S_frame输出顺序与调用时不一致的bug；修改了储存初始化与重构结果的路径 | 无 |
| v5 | 2026-04-23 | 高至简 | 将global_phases_sets加入parser；修改分段逻辑使得可以兼容任意数量的分段；将bound和归一化逻辑合并；将零螺距和S形弯曲的数据也加入初始化考察范围内；进一步使用utils中的字典递归处理方法缩短代码；将优化时零螺距数据的误差标准改为螺距；修正了通道顺序问题 | 无 |
| v5.1 | 2026-04-28 | 高至简 | 将 end_len 加入args并确保end形状的基准是最后一个栅点前 end_len 长度进入末端弧圈，而非传感器末端前 end_len；添加了各分段首尾相连的初始化途径 | 无 |
| v5.2 | 2026-04-29 | 高至简 | 添加了平行标架优化；计算global_phases_set前将用于计算均值的角度等价到[-pi, pi] | 无 |
| v6 | 2026-05-07 | 高至简 | 将半径误差加入了零螺距优化；添加了动态展示时的角度跳变判定与处理 | 无 |
| v6.1 | 2026-05-08 | 高至简 | 将零螺距优化与原始版本同步，添加了PCA求轴向的过程；添加了在优化时冻结部分曲率分区相关参数的设置以方便零螺距数据优化 | 无 |
| v7 | 2026-05-20 | 高至简 | 现可指定重构一部分长度；可进行反向重构；添加了曲率分区判断前根据等曲率板形状放大的设置 | 无 |
| v8 | 2026-05-20 | 曹丹倩 | 加入交错刻栅、通道顺序改变对初始数据的重排 | 无 |
| v9 | 2026-06-16 | 高至简 | 添加交错刻栅与分段通道重排；重构 straight_trim 裁剪逻辑；添加 end3 标定形状；将优化改为 slopes 理论曲率 + weights 正常曲率的两阶段流程；添加完整样机动态展示原型 | 无 |
| v9.1 | 2026-07-07 | 曹丹倩 | 修正straight_trim剪裁后的原点问题 | 无 |
| v10 | 2026-07-22 | 曹丹倩 | 动态增加3方向参数过渡算法 | 无 |
| v10.1 | 2026-07-30 | 曹丹倩 | 修正初始化时global phase角度平均在边界处出错的问题 | 无 |
| v10.2 | 2026-08-07 | 邱国翀 | 加了动态kalman滤波 | 无 |
| v10.5 | 2026-08-22 | 曹丹倩 | 增加向量插值算法，动态0状态匹配，修改数据传输内容，TNN endpose修改，增加pickle保存内容 | 无 |


### 当前帧 full 混合相位锚定（2026-11-05）

多区域 recon/demo 的 `--use_full_transported_phase True` 现在对每帧独立按 full 的评分配置混合全部档位 slope，并将 end15cm 首个支持点锚定到该帧 full 的累计相位。end5cm 首点从上游相位继续递推，跨界间隔采用 end15cm 在该点的实际混合 slope；各局部区域首点之后保留局部混合 slope，weights 归属不变。False 保留原始右端点 slope 递推。

此处只更新运行时装配，不宣称局部 real_points 优化损失已改为绝对方向损失。已有离线验收报告不适用于新算法，需重新回放；首点相位一致不保证全段几何和方向均达标。旧文档中的 fixed full level0 运行时说明已不适用于这个开关的新版 recon/demo 行为。

```powershell
python docs/09B7_compat_dispatch.py main.py --task recon --sensor_params params/09B7_NeTi_recalib.json --multi_region_calib True --use_full_transported_phase True --direct 0 --exp_directs "[0,120,240]"
```

`python docs/check_full_mixed_phase_anchors.py` 检查三个方向24帧全长非零圆弧，验证 end15cm 首点与 full 相位一致、end5cm 跨界使用 end15cm 混合 slope，以及局部内部 slope 和 weights 不变。


### 正式入口整合：逐样本上游相位与绝对方向优化

开启 `--use_full_transported_phase True` 并按 full、end15cm、end5cm 顺序执行 optim 时，局部真实点方向损失现在使用每个实测样本的入口相位，并对照 `-(direct * rot_dir + rot_ang)` 的已知平面圆弧方向。权重阶段仍对照已知半径曲率；优化误差回放也使用同一个逐样本入口相位。关闭该开关保留原来的相对首点损失。

局部试验未测量的上游点以 full 直线标定帧填充，与离线局部回放构造一致；这是假设，不代替完整同步实测数据。算法不会自动保证所有误差门槛通过。历史参数仍可加载，但应重新优化、合并和验证。

正式 main 和参数包工具已接入旧控制参数过滤，不再需要 docs/09B7_compat_dispatch.py。标准命令：

```powershell
python main.py --task optim --multi_region_calib True --use_full_transported_phase True --weights None --slopes None --direct 0
python main.py --task recon --sensor_params params/09B7_NeTi_new.json --multi_region_calib True --use_full_transported_phase True --direct 0 --phase_output docs/09B7_direct0_phases.csv
```

phase_output 只在显式指定时写出CSV，包含各半径、真实点、未环绕相位、混合slope、weight、曲率幅值与方向。没有新增源码文件；辅助历史试验脚本不再是这些正式功能的必需入口。
#   T e s t  
 