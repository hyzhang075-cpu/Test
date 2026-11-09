# Calibration region selection implementation plan

**Goal:** 在 main 中统一选择全长或嵌套末端定标数据，自动计算长度，并在优化前拒绝不匹配的空间分段。

**Scope:** 本轮用户明确要求的模式开关、区域配置、几何和分段校验；逐点联合优化仍处于方案比较阶段。

**Extension:** 后续同分支增加 parser 内嵌区域参数、区域循环优化、逐区域结果落盘和实际评分分布诊断；仍未实施三区域联合损失或最终部署参数组装。

**Architecture:** main 保存 multi_region_calib、optimization_region、全长分段和数据配置。独立 calibration_regions 模块解析配置并生成全局点/段映射；现有 Optimiser 继续执行 slope 后 weight 的两阶段优化。

**Constraints:** 新分支 dev-entrylimit-reducefilter-multiregion；保留原未提交改动；单位 mm 输入、m 输出；不静默截断分段；不自动合并不同相位参数；不触发硬件连接或长时间重新定标。

## Task 1: 配置与几何

- [x] 新增 tests/test_calibration_regions.py：0.877 m、15 cm 七点、5 cm 四点、边界恰好落点、非法跨段、模式关闭只允许全长。
- [x] 运行新测试并确认因缺少接口失败。
- [x] 新增 calibration_regions.py：resolve_calibration_region(start_value, end_value, samp_dist_preset, full_segmentation, profiles, optimization_region, multi_region_calib)。计算完整真实坐标、裁剪起点、局部分段、全局 ID；严格验证几何和段对应。
- [x] 运行测试确认长度和边界正确。

## Task 2: main 接入

- [x] main 中显式定义区域开关与选择、各区域 folder_path/radii/thresholds/segmentation；全长分段是唯一拓扑基准。
- [x] 在 Optimiser 构造之前解析配置；CLI 几何参数优先参与长度计算；配置冲突报错；失效旧参数不自动复用。
- [x] 校验预载 weights/slopes 维度和有限性；将全局映射保留在优化对象的定标上下文中。
- [x] 添加入口测试确认不同区域配置到达真实优化入口且非法分段在读取数据前失败。

## Task 3: 验证与交付

- [x] 使用 0908-06B6 三组数据执行无 GUI 的读取、初始化和正常重构检查，不运行优化。
- [x] 检查数据裁剪点数、插值末端长度及有限性；记录各方向/半径覆盖。
- [x] 运行完整 tests，与修改前基线比较；审查 diff 与已有改动保留情况。
- [x] 文档说明开关、配置、分段映射及独立优化后联合校正的建议。
