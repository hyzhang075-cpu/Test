# end15cm 拼接损失试验补丁

尚未应用到项目源码。草稿仅支持来源完整参数包 + 独立 end15cm optim。

保留 end15cm_point_calib=True、use_full_transported_phase=False。默认关闭新开关。

## 修改范围

- main.py：增加 end15cm_assembly_loss 与 end15cm_assembly_loss_weight；拒绝批量模式、非 end15cm、weights-only、反向及非法系数。
- optimiser.py：保留真实点方向损失，在 slopes 阶段增加全长实测拼接几何损失；weights 阶段保持原目标；记录分量。
- end15_assembly_loss.py：新文件，缓存 full 实测数据与固定 full 参数；禁用 end5cm 替换，仅装配候选 end15cm，复用正式重构。源包的全局相位和 rot_ang 不变，不使用固定上游参考相位模式。
- tools/sensor_parameter_package.py：登记两个试验控制参数；加载参数包时不自动开启该试验。

损失定义：对源包 full 的非零圆弧样本等权平均，每个样本为 (全曲线平均平方点位误差 + 平方末端误差) / 全长平方。新总损失为原真实点方向损失 + lambda * 上述损失。lambda=1 仅为首轮试验值，不是已验证最优值。评价样本不包含 full 未实测的小半径数据；局部高曲率仍由原真实点目标覆盖。

仅支持原有分段及 thresholds 不变的独立 end15cm 试验。暂未支持批量逐区域更新与 end5cm 新损失，不应按完整生产流程使用。

## 应用（由用户执行）

先备份 main.py、optimiser.py、tools/sensor_parameter_package.py。

```powershell
git apply --check --ignore-space-change docs/proposed_end15_assembly_loss/end15_assembly_loss.patch
git apply --ignore-space-change docs/proposed_end15_assembly_loss/end15_assembly_loss.patch
```

若 check 失败，说明源码与草稿基线不匹配，不要强行应用。

## 单方向试验

```powershell
python main.py --task optim `
  --sensor_params params/09B7_corrected_multi_region_candidate.json `
  --multi_region_calib False --optimization_region end15cm `
  --use_full_transported_phase False --end15cm_point_calib True `
  --end15cm_assembly_loss True --end15cm_assembly_loss_weight 1 `
  --direct 120 --exp_directs "[120]" --rot_ang -31.4 `
  --calibration_output_dir calibration_results/09B7_corrected_end15_assembly_trial `
  2>&1 | Tee-Object 09B7_corrected_end15_assembly_trial_direct120.log
```

继承原参数，不加 weights None / slopes None。源包不被修改。试验结果未合并到原包。结果 optimization.assembly_loss 中保存损失分量、源包和评价半径。weights 阶段不含新约束，因此最终 assembly 损失不一定等于 slopes 阶段结束时的损失。

## 已完成检查

见 draft-check-results.json。实际09B7/120数据完成语法、总损失加和、新候选敏感性、关闭开关一致性、重复评价一致性、owner参数无修改、装配背景及非法配置拒绝检查。未运行完整优化；未证明拼接改善。环境缺少 pytest，未运行现有 pytest 套件。check_draft.py 仅用于草稿隔离检查。
