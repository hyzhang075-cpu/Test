import glob
import os
import queue
import socket
import struct
import time
import re
import logging
import copy

import numpy as np
import pandas as pd

from scipy.interpolate import CubicSpline
from pathlib import Path
from collections import defaultdict
from scipy.signal import savgol_filter

from tools.utils import build_valid_row_mask, dict_recur_extract
from tools.zero_reference import load_zero_reference
from calibration_regions import compute_fbg_geometry


class WavelengthContinuityGuard:
    """Reject isolated large FiberTecc wavelength jumps independently per FBG."""

    def __init__(self, threshold_nm=12.0):
        threshold_nm = float(threshold_nm)
        if not np.isfinite(threshold_nm) or threshold_nm < 0.0:
            raise ValueError("threshold_nm must be a finite nonnegative number")
        self.threshold_nm = threshold_nm
        self._last_valid = {}
        self._candidate = {}

    def filter(self, sensor_id, wavelength):
        """Return a safe wavelength, or None until the first finite sample arrives."""
        value = float(wavelength)
        previous = self._last_valid.get(sensor_id)
        if not np.isfinite(value):
            return previous

        if previous is None:
            self._last_valid[sensor_id] = value
            return value

        candidate = self._candidate.get(sensor_id)
        if candidate is None:
            change = abs(value - previous)
            if change <= self.threshold_nm or np.isclose(
                    change, self.threshold_nm, rtol=0.0, atol=1e-12):
                self._last_valid[sensor_id] = value
                return value
            self._candidate[sensor_id] = value
            print(
                f"波长跳变提醒 sensor_id={sensor_id} "
                f"旧值={previous:.6f} 新值={value:.6f} "
                f"变化量={change:.6f} nm ({change * 1000.0:.3f} pm)"
            )
            return previous

        previous_change = abs(value - previous)
        candidate_change = abs(value - candidate)
        near_previous = previous_change <= self.threshold_nm or np.isclose(
            previous_change, self.threshold_nm, rtol=0.0, atol=1e-12)
        near_candidate = candidate_change <= self.threshold_nm or np.isclose(
            candidate_change, self.threshold_nm, rtol=0.0, atol=1e-12)
        if near_previous:
            self._candidate.pop(sensor_id, None)
            self._last_valid[sensor_id] = value
            return value
        if near_candidate:
            self._candidate.pop(sensor_id, None)
            self._last_valid[sensor_id] = value
            return value

        self._candidate[sensor_id] = value
        return previous


class Sensor:
    """
    传感器自身物理参数以及数据处理模块
    """
    def __init__(self, sensor_id, start_value, end_value, folder_path, centre_fibre=True, active_channels=[1, 3, 4], rot_dir=-1, exp_directs=[0, 120, 240], interrogator='FiberTecc', R=0.235e-3, ideal_len=1.35,
                radii={'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200], 'S': [0, 250, 200, 150], 'end': {2000: [30, 20, 15], 1500: [150, 100, 50]}, 
                       'rot0': {100: [10, 40, 70]}, 'up': {200: [0, 25, 50, 100], 100: [0, 25, 50, 100]}, 'down': {200: [0, 25, 50, 100], 100: [0, 25, 50, 100]}}, 
                samp_dist_preset=[510, 540, 570, 630, 710, 810, 910, 1010, 1110, 1210, 1310, 1410, 1510, 1610, 1710, 1815], active_angles=None, reverse=False, straight_trim=0.0,
                ss=2.6e-3, N=100, sensing_ranges={1: (583, 1048), 3: (678, 1146), 4: (749, 1215)}, smoothing_params={'window_length': 21,'polyorder': 3},
                IP='192.168.1.75', PORT=26546, data_freq=100, maxsize=100, samp_dist_preset_sub=None, interlaced_grating=False, channel_change=False, channel_layout=None, interlaced_offset=0.0,
                use_stored_zero=False, zero_reference_path=None,
                wavelength_jump_threshold_pm=12000.0, wavelength_jump_guard_enabled=True):
        
        # 实验参数
        self.exp_directs = exp_directs
        self.interrogator = interrogator
        self.sensor_id = sensor_id
        self.radii = {exp_direct: copy.deepcopy(radii) for exp_direct in self.exp_directs}
        self.calib_shapes = list(radii.keys())

        # active_channels:
        #   物理通道号 -> 当前运行时矩阵列号（按输入顺序）
        self.active_channels = {phy_ch: i for i, phy_ch in enumerate(active_channels)}
        self.num_channels = len(active_channels)
        self.num_channels_recon = self.num_channels
        self.active_angles = active_angles

        # ch_order:
        #   保持 read_data_FBG 现有逻辑不变：
        #   把“按物理通道升序读出的列”重排成 active_channels 的输入顺序
        self.ch_order = [sorted(active_channels).index(phy_ch) for phy_ch in active_channels]

        self.reverse = reverse
        self.rot_dir = rot_dir  # 标定实验时旋转传感器的方向，1对应逆时针，-1对应顺时针
        self.centre_fibre = centre_fibre

        # LUNA参数
        self.ss = ss
        self.num_groups = len(radii)
        self.N = N
        if interrogator == 'LUNA':
            missing_ranges = [phy_ch for phy_ch in active_channels if phy_ch not in sensing_ranges]
            if missing_ranges:
                raise ValueError(f"sensing_ranges 缺少这些激活物理通道的配置: {missing_ranges}")

        self.min_len = min(end - start for phy_ch, (start, end) in sensing_ranges.items() if phy_ch in self.active_channels)

        # sensing_ranges 的 key 直接使用物理通道号
        self.sensing_ranges = {phy_ch: (start, start + self.min_len) for phy_ch, (start, _) in sensing_ranges.items() if phy_ch in self.active_channels}
        self.smoothing_params = smoothing_params

        # 传感器物理参数
        self.ideal_len = ideal_len
        self.generate_samp_dist(reverse=reverse, start_value=start_value, end_value=end_value, straight_trim=straight_trim, samp_dist_preset=samp_dist_preset, samp_dist_preset_sub=samp_dist_preset_sub, interlaced_grating=interlaced_grating)  # 生成传感点在传感器上所处的实际位置（单位：米）
        self.total_points = len(self.samp_dist)
        self.R = R
        # print(self.samp_dist)
       
        # 动态数据接收相关参数
        self.IP = IP
        self.PORT = PORT
        self.data_queue = queue.Queue(maxsize=maxsize)
        self.data_freq = data_freq

        # 动态数据处理相关参数
        self.zero_points = {ch: [None] * self.total_points for ch in active_channels}
        self.is_zero_set = {ch: False for ch in active_channels}
        self._configure_zero_reference(use_stored_zero, zero_reference_path)
        self.current_snapshot = np.zeros((self.total_points, self.num_channels))
        self.buffer = bytearray()
        self.wavelength_jump_guard_enabled = bool(wavelength_jump_guard_enabled)
        self.wavelength_jump_threshold_pm = float(wavelength_jump_threshold_pm)
        self._wavelength_guard = WavelengthContinuityGuard(
            threshold_nm=self.wavelength_jump_threshold_pm / 1000.0
        )

        # 数据存储结构
        self.channel_change = channel_change
        self.channel_layout = channel_layout
        self.interlaced_grating = interlaced_grating
        # 在 __init__ 中添加以下两行保存预设数组
        self.samp_dist_preset = samp_dist_preset
        self.samp_dist_preset_sub = samp_dist_preset_sub
        self.interlaced_offset = interlaced_offset # 确保这个也保存了

        if self.interrogator in ['FiberTecc', 'Hippo']:
            # 1. 读取和清洗原始数据
            # read_data_FBG 只负责读取，输出矩阵按物理通道升序排列
            self.read_data_FBG(folder_path=folder_path, samp_dist_preset=samp_dist_preset, samp_dist_preset_sub=samp_dist_preset_sub)

            # 2. 先做通道重排
            # 注意：不要在这里之前裁剪，否则 channel_layout 的行段边界也可能被破坏
            if self.channel_change and self.channel_layout:
                self._reorder_channels_by_layout()
            else:
                self._reorder_channels_by_active()

            # 3. 如果是交错刻栅，先把原始 Data 合并 / 插值成最终采样点结构
            # 这样 Data 的行数和 generate_samp_dist() 里合并后的 samp_dist 参照系一致
            if self.interlaced_grating:
                self._apply_interlaced_grating(
                    samp_dist_preset=samp_dist_preset,
                    samp_dist_preset_sub=samp_dist_preset_sub
                )

            # 4. 最后再裁剪 Data
            # 现在 self.raw_trim_idx 对应的就是当前 Data 的行索引
            self.Data = dict_recur_extract(self.Data, lambda data: data[self.raw_trim_idx:, :])

            # 5. 中心光纤补偿
            if self.centre_fibre:
                self.centreData, self.outerData, self.processed_Data, self.plot_Data = self._process_centreData(data=self.Data)
                self.num_channels_recon = self.num_channels - 1
                if self.interlaced_grating:
                    self.num_channels_recon //= 2
            else:
                self.processed_Data = self.Data
                self.plot_Data = copy.deepcopy(self.Data)
        elif self.interrogator == 'LUNA':
            self.read_data_OFDR(folder_path=folder_path)

        # 这里只保留 reverse 对数据顺序的影响；trim 只在误差计算和可视化阶段使用。
        if reverse:
            self.processed_Data = dict_recur_extract(self.processed_Data, lambda arr: arr[::-1, :])
            self.plot_Data = dict_recur_extract(self.plot_Data, lambda arr: arr[::-1, :])

    def generate_samp_dist(self, reverse, start_value, end_value, straight_trim, samp_dist_preset, samp_dist_preset_sub, interlaced_grating):
        """
        生成传感点空间采样距离，并记录裁剪索引、虚拟起点和虚拟末端信息。

        该方法只处理空间坐标和索引，不直接修改 self.Data。实际静态数据的行裁剪在
        __init__ 中完成，并且应位于通道重排和交错刻栅合并之后。

        参数：
        - reverse: 是否生成用于反向重构的空间坐标。
        * False: 默认正向坐标；可保留原始 start_value 偏移，或在 straight_trim 非零时将保留段起点平移到 0。
        * True: 将裁剪后的 raw_samp_dist 反向排列，并加上 end_value 对应的末端偏移。
        - start_value: 固定端到第一个有效采样点的距离，单位 mm。
        - end_value: 最后一个真实采样点到末端虚拟点的距离，单位 mm。
        - straight_trim: 裁剪配置。
        * float: 按物理长度裁剪。若 >=0，则保留 raw_samp_dist >= straight_trim 的部分；
            若 <0，则使用 ideal_len + straight_trim 作为裁剪位置。
        * int 或其他非 float 数值: 若不为 0，则作为负向点数索引使用，例如 -8 表示保留最后 8 个点。
        * 0 / 0.0: 不裁剪，raw_trim_idx 保持为 0。
        - samp_dist_preset: 主光栅位置预设，单位 mm。
        - samp_dist_preset_sub: 交错刻栅第二组位置预设，单位 mm；interlaced_grating=True 时不能为空。
        - interlaced_grating: 是否将 samp_dist_preset 与 samp_dist_preset_sub 合并后生成采样距离。

        生成逻辑：
        1. LUNA 模式下，使用 np.arange(self.min_len) * self.ss 生成等间距 raw_samp_dist。
        2. FBG/Hippo 模式下：
        a. 若 interlaced_grating=True，先合并并排序两组位置预设；
        b. 对位置预设做差分、倒序，以 start_value 为起点累加；
        c. 将结果从 mm 转换为 m。
        3. 根据 straight_trim 计算 self.raw_trim_idx，并裁剪 raw_samp_dist。
        4. 根据 reverse 生成 self.samp_dist。
        5. 根据 self.samp_dist[0] 判断 self.zero_init；若需要，在 ad_samp_dist 前插入 0.0。
        6. reverse=False 且 end_value>0 时，在 ad_samp_dist 末尾追加末端虚拟点。
        7. 检查 self.samp_dist 的有限性和 self.ad_samp_dist 的严格递增性。

        更新的成员：
        - self.straight_trim: 当前裁剪配置。
        - self.trim_len: 当 straight_trim 为 float 时，对应的物理裁剪长度，单位 m。
        - self.raw_trim_idx: Data 行裁剪使用的起始索引。
        - self.samp_dist: 裁剪后的真实采样点坐标，单位 m。
        - self.zero_init: 是否需要在 ad_samp_dist 前补起点虚拟点。
        - self.end_point: 是否需要在 ad_samp_dist 后补末端虚拟点。
        - self.ad_samp_dist: 加入虚拟点后的采样坐标，单位 m。

        异常：
        - interlaced_grating=True 但 samp_dist_preset_sub is None 时抛出 ValueError。
        - raw_samp_dist 或 self.samp_dist 包含 NaN / inf 时抛出 ValueError。
        - self.ad_samp_dist 非严格递增时抛出 ValueError。

        注意：
        - end_value 在 reverse=True 分支中直接参与计算，当前版本假定其不是 None。
        - type(self.straight_trim) == float 的判断只识别 Python float；np.float64 等类型会进入非 float 分支。
        - 当 reverse=False 且 straight_trim==0.0 时，本版本保留 raw_samp_dist 的原始 start_value 偏移；
        当 straight_trim!=0 时，会将保留段起点平移到 0。
        """
        if self.interrogator == 'LUNA':
            raw_samp_dist = np.arange(self.min_len) * self.ss
        else:
            # 处理交错光栅逻辑
            if interlaced_grating:
                if samp_dist_preset_sub is None:
                    raise ValueError("当 interlaced_grating 为 True 时，samp_dist_preset_sub 不能为空")
                # 统一转为 numpy 数组合并，并进行升序排序
                combined_preset = np.concatenate((np.array(samp_dist_preset), np.array(samp_dist_preset_sub)))
                preset_to_diff = np.sort(combined_preset)
            else:
                preset_to_diff = np.array(samp_dist_preset)

            # FBG 的物理全长与点位必须来自同一份几何；先计算再裁剪。
            # 即使直接构造 Sensor 而不经过 main，也不能沿用旧的手填 ideal_len。
            self.ideal_len, raw_samp_dist = compute_fbg_geometry(
                start_value, end_value, preset_to_diff,
            )

        if not np.all(np.isfinite(raw_samp_dist)):
            raise ValueError("samp_dist 包含非有限值（NaN 或 inf）")

        # straight_trim 裁剪 samp_dist
        self.straight_trim = straight_trim
        # 负坐标点位于固定件内部，不参与应变定标或曲线重构。该索引稍后也用于
        # 裁切 Data，确保采样坐标与数据矩阵始终逐行对应。
        zero_start_idx = int(np.searchsorted(raw_samp_dist, -1e-12, side="left"))
        self.raw_trim_idx = zero_start_idx
        if type(self.straight_trim) == float:
            self.trim_len = straight_trim if straight_trim >= 0 else self.ideal_len + straight_trim

            if self.trim_len < raw_samp_dist[0]:
                raw_trim_idx = 0
            else:
                raw_trim_idx = np.searchsorted(raw_samp_dist, self.trim_len - 1e-12, side="left")

            if raw_trim_idx >= len(raw_samp_dist):
                raise ValueError(
                    f"straight_trim={straight_trim} 对应的 trim_len={self.trim_len} 已超出采样范围，"
                    f"最大采样距离为 {raw_samp_dist[-1]}"
                )
            self.raw_trim_idx = max(zero_start_idx, int(raw_trim_idx))
        else:
            if self.straight_trim != 0:
                point_trim_idx = max(0, len(raw_samp_dist) - int(np.abs(self.straight_trim)))
                self.raw_trim_idx = max(zero_start_idx, point_trim_idx)

        # 1-based 全局真实数据行号，不包含重构用虚拟点，也不冒充硬件 FBG 标签。
        self.global_point_ids = np.arange(1, len(raw_samp_dist) + 1)[self.raw_trim_idx:]
        raw_samp_dist = raw_samp_dist[self.raw_trim_idx:]
        self.global_samp_dist = raw_samp_dist.copy()

        # 先生成完整 samp_dist；reverse 只改变坐标方向，不与 straight_trim 耦合。
        if reverse:
            self.samp_dist = (raw_samp_dist[-1] - raw_samp_dist)[::-1] + end_value * 0.001
            self.global_point_ids = self.global_point_ids[::-1]
            self.global_samp_dist = self.global_samp_dist[::-1]
        else:
            if self.straight_trim != 0:
                # self.samp_dist = raw_samp_dist - raw_samp_dist[0]
                self.samp_dist = raw_samp_dist -  self.trim_len
            else:
                self.samp_dist = raw_samp_dist

        if not np.all(np.isfinite(self.samp_dist)):
            raise ValueError("samp_dist 包含非有限值（NaN 或 inf）")
        
        if np.abs(self.samp_dist[0]) < 1e-8:    # 处理浮点数精度问题，避免出现 -1e-16 之类的值
            self.samp_dist[0] = 0.0
        self.zero_init = bool(self.samp_dist[0] != 0.0)

        # reverse=False 时，在最后一个真实传感点之后补一个虚拟末端点
        # end_value 单位是 mm，这里转成 m
        self.end_point = (not reverse) and (end_value is not None) and (end_value > 0)

        self.ad_samp_dist = self.samp_dist.copy()

        # 起点虚拟点：已有逻辑，复制第一个传感点的 magnitude/angle
        if self.zero_init:
            self.ad_samp_dist = np.insert(self.ad_samp_dist, 0, 0.0)

        # 末端虚拟点：新增逻辑，复制最后一个传感点的 magnitude/angle，不参与分段，只参与最后重构和优化
        if self.end_point:
            self.ad_samp_dist = np.append(self.ad_samp_dist, self.ad_samp_dist[-1] + end_value * 0.001)
        if not np.all(np.diff(self.ad_samp_dist) > 0):
            raise ValueError("ad_samp_dist 必须是递增的数组")
        
        print(f"初始采样距离（m）：{raw_samp_dist}")
        print(f"生成的采样距离（m）：{self.samp_dist}")
        print(f"重构长度（m）：{self.ad_samp_dist}")

    
    def _configure_zero_reference(self, use_stored_zero, zero_reference_path):
        """加载严格校验的存储零状态，或保留原有首帧归零模式。"""
        self.use_stored_zero = bool(use_stored_zero)
        self.zero_reference_path = zero_reference_path
        if not self.use_stored_zero:
            return
        if not zero_reference_path:
            raise ValueError("use_stored_zero=True 时必须提供 zero_reference_path")
        loaded = load_zero_reference(
            zero_reference_path,
            sensor_id=self.sensor_id,
            active_channels=list(self.active_channels),
            total_points=self.total_points,
            raw_trim_idx=self.raw_trim_idx,
        )
        self.zero_points = {channel: loaded[channel].tolist() for channel in self.active_channels}
        self.is_zero_set = {channel: True for channel in self.active_channels}
        print(f"已加载 SensorID={self.sensor_id} 的存储零状态: {zero_reference_path}")

    # -------------------- FBG数据处理 --------------------
    def read_data_FBG(self, folder_path, samp_dist_preset, samp_dist_preset_sub=None):
        """
        读取 FiberTecc/Hippo 静态 FBG 标定数据，完成清洗、求均值和嵌套结构整理。

        本函数只负责“读取与清洗”。它输出的每个 data_matrix 按物理通道号升序排列，
        不在此处应用 active_channels 的输入顺序，也不在此处执行 channel_layout、交错刻栅合并、
        中心补偿或 straight_trim 裁剪；这些步骤由 __init__ 后续流程统一处理。

        支持的子文件夹命名格式：
        1. x-y             -> self.Data["circ"][x][y]
        2. x-y-S           -> self.Data["S"][x][y]
        3. x-y-z           -> self.Data["end"][x][y][z]
        4. x-y-z-R0        -> self.Data["rot0"][x][y][z]
        5. x-y-z-up        -> self.Data["up"][x][y][z]
        6. x-y-z-down      -> self.Data["down"][x][y][z]
        7. x-y-z-end3      -> self.Data["end3"][x][y][z]

        其中：
        - x 通常表示标定方向 direct。
        - y 通常表示圆弧半径或对应实验半径，单位 mm。
        - z 在 end/end3/rot0/up/down 中表示末级参数；对于 end3，z 表示圆弧平面相对 +y 的顺时针角度，单位度。

        参数：
        - folder_path: 静态标定数据根目录。
        - samp_dist_preset: 主光栅位置预设；用于确定每个 CSV 应有的数据列数。
        - samp_dist_preset_sub: 交错刻栅第二组位置预设；本函数仅接收该参数以保持接口一致，
        不在读取阶段直接使用。

        读取规则：
        - FiberTecc 文件名兼容 channel_{n}_*.csv、Channel_{n}_*.csv、CHANNEL_{n}_*.csv。
        - Hippo 文件名兼容 CH{n}_*.csv、ch{n}_*.csv、Ch{n}_*.csv。
        - 同一 channel 若匹配到多个 CSV，优先使用 _pick_first_nonempty_csv() 选择第一个非空文件。
        - CSV 前两列视为非 FBG 数据列；从第 3 列开始到 expected_cols 为有效采样数据。

        清洗规则：
        1. 读取 CSV 后删除全空列，避免表头列数多于实际数据列数时误判整行 NaN。
        2. 若列数不等于 len(samp_dist_preset)+2，则整个 subfolder 判为无效并跳过。
        3. 将 FBG 列转为数值，排除含缺数据或非数值的行。
        4. 调用 build_valid_row_mask() 排除 outlier 行。
        5. 对清洗后的有效行按列求均值。
        6. 若 channel 清洗后为空或均值包含 NaN/inf，则跳过该 channel。
        7. 若整个 subfolder 无有效 channel，或缺少构建矩阵所需的 active_channels，则跳过该 subfolder，
        并通过 _edit_radii() 从 self.radii 中撤销对应配置。

        输出/副作用：
        - 无返回值。
        - 更新 self.Data，结构为：
        * circ/S: self.Data[shape][x][y] = data_matrix
        * end/end3/rot0/up/down: self.Data[shape][x][y][z] = data_matrix
        - data_matrix 的形状为 (num_points, num_required_channels)，单位缩放为 1e-6。
        - data_matrix 的列顺序为 sorted(required_channels)，即物理通道升序。
        - 读取完成后，对各级字典按半径键降序排序，其中键 0 视为最大值。

        注意：
        - 交错刻栅启用时，本函数仍按 samp_dist_preset 的长度检查单个 CSV 的列数；
        两组交错位置的合并在 _apply_interlaced_grating() 中完成。
        - 当前函数会记录详细清洗统计，便于定位数据缺失、outlier 过多或通道文件异常。
        """
        self.Data = {"circ": {}, "S": {}, "end": {}, "end3": {}, "rot0": {}, "up": {}, "down": {}}

        expected_data_cols = len(samp_dist_preset)
        expected_cols = expected_data_cols + 2
        col_start, col_end = 2, expected_cols

        for subfolder in os.listdir(folder_path):
            subfolder_path = os.path.join(folder_path, subfolder)
            if not os.path.isdir(subfolder_path):
                continue

            x, y, z, folder_type = self._classify_folder(subfolder=subfolder)
            if folder_type is None:
                continue

            channel_data = {}
            valid_subfolder = True

            # 记录被清洗到全空的 channel，便于最后解释为什么 subfolder 被删
            clean_empty_channels = {}

            for channel in range(max(self.active_channels) + 1):
                if self.interrogator == 'FiberTecc':
                    # 兼容 Windows / Linux 下大小写差异
                    patterns = [
                        os.path.join(subfolder_path, f"channel_{channel}_*.csv"),
                        os.path.join(subfolder_path, f"Channel_{channel}_*.csv"),
                        os.path.join(subfolder_path, f"CHANNEL_{channel}_*.csv"),
                    ]
                elif self.interrogator == 'Hippo':
                    patterns = [
                        os.path.join(subfolder_path, f"CH{channel}_*.csv"),
                        os.path.join(subfolder_path, f"ch{channel}_*.csv"),
                        os.path.join(subfolder_path, f"Ch{channel}_*.csv"),
                    ]
                else:
                    logging.error(f"Unsupported interrogator type: {self.interrogator}")
                    valid_subfolder = False
                    break

                matched_files = sorted(set(file for pattern in patterns for file in glob.glob(pattern)))

                if not matched_files:
                    continue

                # 优先使用已有工具函数：避免第一个匹配文件为空时误跳过有效文件
                if hasattr(self, "_pick_first_nonempty_csv"):
                    file_path = self._pick_first_nonempty_csv(matched_files)
                    if file_path is None:
                        logging.info(f"subfolder {subfolder} channel {channel} 的候选 CSV 都为空或读取失败，已跳过该 channel。")
                        continue
                else:
                    file_path = matched_files[0]

                try:
                    df = pd.read_csv(file_path)
                    # 解决表头列数多于实际数据列数导致整行被误判为 NaN 的问题
                    df.dropna(axis=1, how='all', inplace=True)
                except Exception as e:
                    logging.warning(f"文件 {file_path} 读取失败，跳过该 channel。error={e}")
                    continue

                if df.empty:
                    logging.info(f"文件 {file_path} 只有表头没有数据行，视为未连接通道，已跳过 channel {channel}。")
                    continue

                current_num_cols = df.shape[1]

                if current_num_cols != expected_cols:
                    logging.warning(
                        f"Column count mismatch in {subfolder} Channel {channel}: "
                        f"found {current_num_cols}, expected {expected_cols}. "
                        f"当前 subfolder 将被跳过。"
                    )
                    valid_subfolder = False
                    break

                # -------------------- 清洗 NaN / outlier --------------------
                fbg_cols = list(enumerate(df.columns[col_start:col_end]))
                fbg_col_names = [col for _, col in fbg_cols]

                numeric_fbg = df[fbg_col_names].apply(pd.to_numeric, errors="coerce")

                # 1) 缺数据 / 非数值行排除
                non_missing_mask = ~numeric_fbg.isna().any(axis=1)
                non_missing_mask_np = non_missing_mask.to_numpy(dtype=bool)

                # 2) outlier 行排除
                outlier_valid_mask = np.asarray(build_valid_row_mask(df=df, fbg_cols=fbg_cols, threshold=9000, half_window=5), dtype=bool)

                if len(outlier_valid_mask) != len(df):
                    logging.error(
                        f"严重错误：文件 {file_path} 的 outlier_valid_mask 长度 "
                        f"{len(outlier_valid_mask)} 与 df 行数 {len(df)} 不一致，当前 subfolder 将被跳过。"
                    )
                    valid_subfolder = False
                    break

                valid_rows = non_missing_mask_np & outlier_valid_mask

                nan_row_mask = ~non_missing_mask_np
                outlier_row_mask = ~outlier_valid_mask

                removed_missing_count = int(np.sum(nan_row_mask))
                removed_outlier_count = int(np.sum(non_missing_mask_np & outlier_row_mask))
                removed_both_count = int(np.sum(nan_row_mask & outlier_row_mask))
                kept_count = int(np.sum(valid_rows))
                total_count = int(len(df))

                if removed_missing_count > 0:
                    logging.warning(f"警告：文件 {file_path} 中有 {removed_missing_count} 行存在缺数据或非数值，已跳过相关行。")

                if removed_outlier_count > 0:
                    logging.warning(f"警告：文件 {file_path} 中有 {removed_outlier_count} 行被判定为 outlier，已跳过相关行。")

                if removed_both_count > 0:
                    logging.warning(f"警告：文件 {file_path} 中有 {removed_both_count} 行同时存在缺数据/非数值且被判为 outlier。")

                if total_count != kept_count:
                    logging.info(
                        f"[CLEAN-STATS] {subfolder} channel={channel}: "
                        f"rows={total_count}, kept={kept_count}, "
                        f"missing_or_non_numeric={removed_missing_count}, "
                        f"outlier={removed_outlier_count}, both={removed_both_count}"
                    )

                cleaned_df = df.loc[valid_rows].copy()

                if cleaned_df.empty:
                    reason = (
                        f"rows={total_count}, kept=0, "
                        f"missing_or_non_numeric={removed_missing_count}, "
                        f"outlier={removed_outlier_count}, both={removed_both_count}"
                    )
                    clean_empty_channels[channel] = reason
                    logging.warning(
                        f"文件 {file_path} 在缺数据 / outlier 清洗后已无有效行，该 channel 将被跳过。"
                        f"统计：{reason}"
                    )
                    continue

                data_slice = cleaned_df.iloc[:, col_start:col_end].apply(pd.to_numeric, errors="coerce")
                channel_avg = data_slice.mean(axis=0).to_numpy()

                if not np.all(np.isfinite(channel_avg)):
                    logging.warning(f"文件 {file_path} 清洗后求均值仍包含 NaN / inf，该 channel 将被跳过。")
                    clean_empty_channels[channel] = "channel_avg contains NaN or inf after cleaning"
                    continue

                channel_data[channel] = channel_avg

            if not valid_subfolder:
                logging.error(f"严重错误：subfolder {subfolder} 被判定为无效，当前 subfolder 将被跳过。")
                continue

            # 整个 subfolder 没有任何有效 channel
            if len(channel_data) == 0:
                if clean_empty_channels:
                    logging.error(f"严重错误：subfolder {subfolder} 中所有可读 channel 都在清洗后无有效行。详情：")
                    for ch, reason in clean_empty_channels.items():
                        logging.error(f"  channel={ch}: {reason}")
                else:
                    logging.error(
                        f"严重错误：subfolder {subfolder} 中没有任何有效 channel，"
                        f"可能是没有匹配文件、文件为空、读取失败或列数问题。"
                    )

                logging.error(f"subfolder {subfolder} 将被跳过，并从 self.radii 中撤销对应项。")
                self._edit_radii(folder_type=folder_type, x=x, y=y, z=z)
                continue

            # 根据 active_channels 构造“必需 channel 列表”
            if self.interrogator == 'Hippo':
                required_channels = [phy_ch - 1 for phy_ch in self.active_channels]
                missing_channels = [ch for ch in required_channels if ch not in channel_data]
                missing_display_channels = [ch + 1 for ch in missing_channels]
            elif self.interrogator == 'FiberTecc':
                required_channels = list(self.active_channels)
                missing_channels = [ch for ch in required_channels if ch not in channel_data]
                missing_display_channels = missing_channels
            else:
                logging.error(f"Unsupported interrogator type: {self.interrogator}")
                continue

            # 只要缺少任一必需 channel，就撤销对应 radii
            if missing_channels:
                logging.error(
                    f"严重错误：subfolder {subfolder} 缺少构建 data_matrix 所需的必需通道 "
                    f"{missing_display_channels}，当前 subfolder 将被跳过，并从 self.radii 中撤销对应项。"
                )

                clean_missing = {ch: clean_empty_channels[ch] for ch in missing_channels if ch in clean_empty_channels}
                if clean_missing:
                    logging.error(f"其中以下必需通道是因为 NaN / outlier 清洗后无有效行而缺失：")
                    for ch, reason in clean_missing.items():
                        display_ch = ch + 1 if self.interrogator == 'Hippo' else ch
                        logging.error(f"  required channel={display_ch}: {reason}")
                else:
                    logging.error(f"当前已成功读取的 channel 为：{sorted(channel_data.keys())}")

                self._edit_radii(folder_type=folder_type, x=x, y=y, z=z)
                continue

            # 当前新版设计：read_data_FBG 只输出“按物理通道升序”的矩阵；
            # active_channels 输入顺序的重排，在 __init__ 后续 _reorder_channels_by_active/_layout 中完成。
            sorted_required_channels = sorted(required_channels)
            data_matrix = np.column_stack([channel_data[ch] for ch in sorted_required_channels]) * 1e-6

            if folder_type in ("circ", "S"):
                self.Data[folder_type].setdefault(x, {})
                self.Data[folder_type][x][y] = data_matrix
            elif folder_type in ("end", "end3", "rot0", "up", "down"):
                self.Data[folder_type].setdefault(x, {})
                self.Data[folder_type][x].setdefault(y, {})
                self.Data[folder_type][x][y][z] = data_matrix

        # 排序逻辑保持不变
        for shape in ["circ", "S"]:
            for x in list(self.Data[shape].keys()):
                self.Data[shape][x] = dict(sorted(self.Data[shape][x].items(), key=lambda item: float('inf') if item[0] == 0 else item[0], reverse=True))
            self.Data[shape] = dict(sorted(self.Data[shape].items(), key=lambda item: float('inf') if item[0] == 0 else item[0], reverse=True))

        for shape in ["end", "end3", "rot0", "up", "down"]:
            for x in list(self.Data[shape].keys()):
                for y in list(self.Data[shape][x].keys()):
                    self.Data[shape][x][y] = dict(sorted(self.Data[shape][x][y].items(), key=lambda item: float('inf') if item[0] == 0 else item[0], reverse=True))
                self.Data[shape][x] = dict(sorted(self.Data[shape][x].items(), key=lambda item: float('inf') if item[0] == 0 else item[0], reverse=True))
            self.Data[shape] = dict(sorted(self.Data[shape].items(), key=lambda item: float('inf') if item[0] == 0 else item[0], reverse=True))

    def _traverse_and_modify_data(self, data_dict, modify_func, *args, **kwargs):
        """
        递归遍历嵌套字典，并将所有叶子节点 numpy 矩阵替换为 modify_func 的返回值。

        参数：
        - data_dict: 待修改的嵌套字典，通常为 self.Data。
        - modify_func: 作用于叶子节点 numpy.ndarray 的函数。
        - *args, **kwargs: 传递给 modify_func 的额外参数。

        输出/副作用：
        - 无返回值。
        - 原地修改 data_dict 中所有叶子矩阵。

        用途：
        - 通道重排：_reorder_channels_by_active()、_reorder_channels_by_layout()。
        - 交错刻栅合并：_apply_interlaced_grating()。
        - 也可用于其他需要对所有标定数据统一应用矩阵变换的场景。
        """
        for k, v in data_dict.items():
            if isinstance(v, dict):
                self._traverse_and_modify_data(v, modify_func, *args, **kwargs)
            elif isinstance(v, np.ndarray):
                # print(f"{modify_func.__name__}修改前矩阵：{v}")  # 调试输出
                data_dict[k] = modify_func(v, *args, **kwargs)
                # print(f"{modify_func.__name__}修改后矩阵：{data_dict[k]}")  # 调试输出

    def _reorder_channels_by_active(self):
        """
        按 active_channels 的输入顺序全局重排 self.Data 中所有矩阵的列。

        适用条件：
        - channel_change=False，或没有提供 channel_layout。
        - 每个采样点处的通道物理排布一致，不需要分段改变列顺序。

        处理逻辑：
        1. 根据 interrogator 将 active_channels 转换为读取阶段使用的内部通道号。
        - Hippo: 物理通道号减 1。
        - FiberTecc: 直接使用物理通道号。
        2. read_data_FBG() 输出矩阵按 sorted(required_channels) 升序排列。
        3. 根据 active_channels 的输入顺序计算 target_indices。
        4. 对 self.Data 的每个叶子矩阵执行 matrix[:, target_indices]。

        输出/副作用：
        - 无返回值。
        - 原地修改 self.Data。

        说明：
        - 该方法只改变列顺序，不改变行数、单位或嵌套结构。
        """
        if self.interrogator == 'Hippo':
            req_chs = [phy_ch - 1 for phy_ch in self.active_channels]
        else:
            req_chs = list(self.active_channels)
            
        # 原始矩阵是按 sorted(req_chs) 排列的，找出目标顺序对应的索引
        sorted_chs = sorted(req_chs)
        target_indices = [sorted_chs.index(ch) for ch in req_chs]
        
        def reorder_active_func(matrix):
            # 通过切片直接重排矩阵的列
            return matrix[:, target_indices]

        self._traverse_and_modify_data(self.Data, reorder_active_func)

    def _reorder_channels_by_layout(self):
        """
        按 channel_layout 对 self.Data 中所有矩阵执行分段式通道重排。

        适用条件：
        - channel_change=True 且 channel_layout 非空。
        - 不同空间采样段的物理通道排列不同，例如交错焊接、接线变化或局部通道顺序改变。

        channel_layout 格式：
        - [(num_rows_1, [phy_ch_a, phy_ch_b, ...]), (num_rows_2, [...]), ...]
        - 每个元组表示当前连续 num_rows 行应采用的物理通道顺序。

        处理逻辑：
        1. read_data_FBG() 输出矩阵按物理通道升序排列。
        2. 将矩阵还原成 {内部通道号: 对应列数据} 的 channel_data。
        3. 调用 _reorder_matrix_by_layout() 按行段重新组装矩阵。
        4. 对 self.Data 的所有叶子矩阵重复此操作。

        输出/副作用：
        - 无返回值。
        - 原地修改 self.Data。

        注意：
        - 该方法应在 straight_trim 裁剪之前执行；否则 channel_layout 的行段边界会与原始数据错位。
        - channel_layout 中引用的通道必须存在于 active_channels 对应的数据中。
        """
        if self.interrogator == 'Hippo':
            req_chs = [phy_ch - 1 for phy_ch in self.active_channels]
        else:
            req_chs = list(self.active_channels)
            
        sorted_chs = sorted(req_chs)

        def reorder_layout_func(matrix):
            # 还原为 channel_data 字典格式，以便传入 _reorder_matrix_by_layout
            # 注意需要除以 1e-6 还原量级，因为 _reorder_matrix_by_layout 内部会再次乘以 1e-6
            channel_data = {ch_key: matrix[:, i] / 1e-6 for i, ch_key in enumerate(sorted_chs)}
            return self._reorder_matrix_by_layout(channel_data, self.channel_layout)

        self._traverse_and_modify_data(self.Data, reorder_layout_func)

    def _apply_interlaced_grating(self, samp_dist_preset, samp_dist_preset_sub):
        """
        对 self.Data 中所有叶子矩阵应用交错刻栅合并与中心通道插值。

        参数：
        - samp_dist_preset: 第一组采样位置，单位 mm。
        - samp_dist_preset_sub: 第二组交错采样位置，单位 mm；不能为空。

        处理逻辑：
        1. 检查 samp_dist_preset_sub 是否存在。
        2. 对 self.Data 的每个叶子矩阵调用 _process_interlaced_grating()。
        3. 将原始交错排列的数据合并为按空间位置排序后的统一矩阵。

        输出/副作用：
        - 无返回值。
        - 原地修改 self.Data。

        注意：
        - 该方法必须在 straight_trim 裁剪之前执行，使 Data 的行索引与 generate_samp_dist()
        中基于合并 preset 得到的 raw_trim_idx 处于同一参照系。
        - 当前实现假定输入矩阵列结构符合 _process_interlaced_grating() 的约定。
        """
        if samp_dist_preset_sub is None:
            logging.error("严重错误：启用了 interlaced_grating 但缺少 samp_dist_preset_sub。")
            return

        def interlaced_func(matrix):
            return self._process_interlaced_grating(data_matrix=matrix, samp_dist_preset=samp_dist_preset, samp_dist_preset_sub=samp_dist_preset_sub)

        self._traverse_and_modify_data(self.Data, interlaced_func)

    def _reorder_matrix_by_layout(self, channel_data, channel_layout):
        """
        根据 channel_layout 对单个 data_matrix 执行分段式通道重排。

        参数：
        - channel_data: 字典，key 为解调仪内部通道号，value 为该通道的整列空间数据。
        这些数据通常由按物理通道升序排列的 data_matrix 还原得到。
        - channel_layout: 分段通道布局，格式为 [(行数, [物理通道顺序]), ...]。
        例如 [(6, [2, 1, 4, 3, 7, 5, 6]), (10, [...])] 表示：
        前 6 个采样点使用第一组通道顺序，后 10 个采样点使用第二组通道顺序。

        输出：
        - data_matrix: 重排后的矩阵，形状为 (sum(num_rows), len(order))，单位为 1e-6 缩放后的值。

        异常：
        - 若 channel_layout 中引用的物理通道不存在于 channel_data，则抛出 ValueError。

        说明：
        - Hippo 模式下，物理通道号会转换为内部键 phy_ch-1。
        - FiberTecc 模式下，物理通道号直接作为内部键。
        - 本方法只处理单个矩阵；批量递归由 _reorder_channels_by_layout() 完成。
        """
        blocks = []
        current_row = 0
        
        for num_rows, order in channel_layout:
            row_end = current_row + num_rows
            block_cols = []
            
            # 针对当前行切片 [current_row : row_end]，按照 order 提取物理通道作为逻辑列
            for phy_ch in order:
                # 映射物理通道号到 channel_data 的键
                if self.interrogator == 'Hippo':
                    ch_key = phy_ch - 1
                else:
                    ch_key = phy_ch
                
                if ch_key not in channel_data:
                    raise ValueError(f"缺少物理通道 {phy_ch} (内部键 {ch_key}) 的数据")
                
                # 提取该物理通道在当前行范围内的数据
                col_data = channel_data[ch_key][current_row:row_end]
                block_cols.append(col_data)
            
            # 将提取出的多个一维数组按列堆叠，形成形状为 (num_rows, len(order)) 的局部矩阵
            block_matrix = np.column_stack(block_cols)
            blocks.append(block_matrix)
            
            # 更新行指针
            current_row = row_end
            
        # 将所有局部矩阵按行（垂直）拼接起来，恢复为完整的 data_matrix
        data_matrix = np.vstack(blocks) * 1e-6
        return data_matrix

    def _process_interlaced_grating(self, data_matrix, samp_dist_preset, samp_dist_preset_sub):
        """
        处理单个交错刻栅 data_matrix，将两组空间采样位置合并为统一序列。

        参数：
        - data_matrix: 原始交错刻栅矩阵。当前实现假定列顺序为：
        * 第 0 列：中心通道在 samp_dist_preset 位置处的数据；
        * 第 1、3、5 列：三个外围通道在 samp_dist_preset 位置处的数据；
        * 第 2、4、6 列：三个外围通道在 samp_dist_preset_sub 位置处的数据。
        - samp_dist_preset: 第一组位置预设，单位 mm。
        - samp_dist_preset_sub: 第二组位置预设，单位 mm。

        处理逻辑：
        1. 将两组位置转换为 numpy 数组 p1、p2。
        2. 对中心通道第 0 列建立 CubicSpline，用 p1 上的中心数据插值得到 p2 上的中心估计值。
        3. 分别拼接中心通道与三个外围通道在 p1/p2 上的数据。
        4. 合并 p1 和 p2，并按空间位置升序排序。
        5. 根据排序结果重构统一的 interlaced_data_matrix。

        输出：
        - interlaced_data_matrix: 合并后的矩阵，列顺序为 [center, outer1, outer2, outer3]。
        行顺序与 np.sort(concatenate([p1, p2])) 对应。

        注意：
        - p1 必须能够支持 CubicSpline 插值；若 p1 中有重复位置或有效点数不足，可能报错。
        - 当前实现固定假定有 1 个中心通道和 3 个外围通道，且输入列数至少为 7。
        - 该方法不做 straight_trim 裁剪；裁剪应在 __init__ 中交错合并之后统一执行。
        """
        p1 = np.array(samp_dist_preset)
        p2 = np.array(samp_dist_preset_sub)
        
        # print(f"原始 data_matrix:\n{data_matrix}")  # 调试输出
        # 1. 中心通道插值 (第0列)
        center_p1 = data_matrix[:, 0]
        # 确保 p1 是单调递增的，否则样条插值会报错
        sort_p1_idx = np.argsort(p1)
        cs = CubicSpline(p1[sort_p1_idx], center_p1[sort_p1_idx])
        center_p2 = cs(p2) # 预估 p2 位置处的数据
        
        # 2. 合并各通道数据
        center_combined = np.concatenate((center_p1, center_p2))
        # 外围通道：1/3/5 列对应 p1，2/4/6 列对应 p2
        outer1_combined = np.concatenate((data_matrix[:, 1], data_matrix[:, 2]))
        outer2_combined = np.concatenate((data_matrix[:, 3], data_matrix[:, 4]))
        outer3_combined = np.concatenate((data_matrix[:, 5], data_matrix[:, 6]))
        
        # 3. 按照位置排序合并
        p_combined = np.concatenate((p1, p2))
        sort_idx = np.argsort(p_combined)
        # print(f"交错刻栅合并后位置顺序: {p_combined[sort_idx]}")  # 调试输出
        
        # 4. 重构 data_matrix (16 * 4)
        interlaced_data_matrix = np.column_stack((
            center_combined[sort_idx],
            outer1_combined[sort_idx],
            outer2_combined[sort_idx],
            outer3_combined[sort_idx]
        ))
        # print(f"交错刻栅合并后 data_matrix:\n{interlaced_data_matrix}")  # 调试输出

        return interlaced_data_matrix

    def _classify_folder(self, subfolder):
        """
        解析静态标定数据子文件夹名称，判断其标定形状类型和参数。

        参数：
        - subfolder: 子文件夹名称，不包含父路径。

        支持格式：
        1. x-y             -> folder_type='circ', x=方向, y=半径, z=None
        2. x-y-S           -> folder_type='S',    x=方向, y=半径, z=None
        3. x-y-z           -> folder_type='end',  x=方向, y=半径, z=末级参数
        4. x-y-z-R0        -> folder_type='rot0'
        5. x-y-z-up        -> folder_type='up'
        6. x-y-z-down      -> folder_type='down'
        7. x-y-z-end3      -> folder_type='end3'

        对于 end3：
        - x 表示方向 direct；
        - y 表示圆弧半径，单位 mm；
        - z 表示圆弧平面相对 +y 的顺时针角度，单位度。

        输出：
        - (x, y, z, folder_type)
        * x/y/z 为 int 或 None；
        * folder_type 为字符串或 None。

        说明：
        - 匹配顺序为四段后缀、三段字母、三段数字、两段数字，避免 x-y-z-end3 被误识别为 x-y-z。
        - 不支持的格式会打印提示并返回 (None, None, None, None)。
        """
        # 注意顺序：先判四段，再判三段字母，再判三段数字，最后判两段
        # x-y-z-end3: x=direct, y=圆弧半径(mm), z=圆弧平面相对 +y 的顺时针角度(度)
        m_rot = re.fullmatch(r"(\d+)-(\d+)-(\d+)-(R0|up|down|end3)", subfolder)
        m_S = re.fullmatch(r"(\d+)-(\d+)-([A-Z]+)", subfolder)
        m_end = re.fullmatch(r"(\d+)-(\d+)-(\d+)", subfolder)
        m_circ = re.fullmatch(r"(\d+)-(\d+)", subfolder)

        if m_rot:
            x, y, z = map(int, m_rot.groups()[:3])
            suffix = m_rot.group(4)
            if suffix == "R0":
                folder_type = "rot0"
            elif suffix in ("up", "down", "end3"):
                folder_type = suffix
            else:
                folder_type = None

        elif m_S:
            x, y = map(int, m_S.groups()[:2])
            z = None
            suffix = m_S.group(3)
            if suffix == "S":
                folder_type = "S"
            else:
                print(f"Unsupported suffix in subfolder: {subfolder}")

        elif m_end:
            x, y, z = map(int, m_end.groups())
            folder_type = "end"

        elif m_circ:
            x, y = map(int, m_circ.groups())
            z = None
            folder_type = "circ"

        else:
            print(f"Invalid subfolder format: {subfolder}")
            x, y, z, folder_type = None, None, None, None
        
        return x, y, z, folder_type
    
    def _pick_first_nonempty_csv(self, file_list):
        """
        从候选 CSV 列表中选择第一个真正包含数据行的文件。
        若所有文件都只有表头或无法读取，则返回 None。
        """
        for file_path in sorted(file_list):
            try:
                df_tmp = pd.read_csv(file_path)
                if not df_tmp.empty:
                    return file_path
                else:
                    logging.warning(f"跳过只有表头无数据的文件: {file_path}")
            except Exception as e:
                logging.warning(f"读取文件失败，已跳过: {file_path}, error={e}")
        return None

    def _edit_radii(self, folder_type, x, y, z):
        """
        当某个 subfolder 被判定为无效时，同步从 self.radii 中撤销该 subfolder 对应的半径配置。

        无效情况包括：
        - 整个 subfolder 没有任何有效 channel；
        - 构建 data_matrix 所需的 active_channels 中任一必需 channel 缺失。
        """
        def _remove_from_container(container, value):
            if isinstance(container, set):
                container.discard(value)
            elif isinstance(container, list):
                while value in container:
                    container.remove(value)

        if folder_type in ("circ", "S"):
            # 1. x-y     -> self.radii['circ'] 去掉 y
            # 2. x-y-S   -> self.radii['S']    去掉 y
            if folder_type in self.radii[x]:
                _remove_from_container(self.radii[x][folder_type], y)
                
        elif folder_type in ("end", "end3", "rot0", "up", "down"):
            # 3. x-y-z       -> self.radii['end'][y]   去掉 z
            # 4. x-y-z-R0    -> self.radii['rot0'][y]  去掉 z
            # 5. x-y-z-up    -> self.radii['up'][y]    去掉 z
            # 6. x-y-z-down  -> self.radii['down'][y]  去掉 z
            # 7. x-y-z-end3  -> self.radii['end3'][y]  去掉 z
            if folder_type in self.radii[x]:
                # 如果 key 用的是字符串，可以把下面的 y_key 改成 str(y)
                y_key = y if y in self.radii[x][folder_type] else str(y) if str(y) in self.radii[x][folder_type] else None

                if y_key is not None:
                    _remove_from_container(self.radii[x][folder_type][y_key], z)

                    # 可选：如果删完后这个 y 对应的列表/集合空了，就把这个键也删掉
                    if len(self.radii[x][folder_type][y_key]) == 0:
                        del self.radii[x][folder_type][y_key]

    def _process_centreData(self, data):
        """
        将包含中心光纤与外围光纤的通道数据拆分，并生成中心补偿后的结果。

        步骤：
        1. 若输入为字典，则递归处理其各级 value，并保持原有嵌套结构不变。
        2. 若输入为 numpy 数组，则默认最后一个维度的第 1 列为中心光纤通道，其余列为外围光纤通道。
        3. 对数组输入：
            - 取第 1 列作为 centre_Data；
            - 取其余列作为 outer_Data；
            - 计算 processed_Data = outer_Data - centre_Data；
            - 构造 plot_Data = [centre_Data, outer_Data] 的列拼接结果。

        输入：
        - data:
            - 若为字典，则其叶子节点应为 numpy 数组；
            - 若为 numpy 数组，则默认第 1 列为中心光纤通道，其余列为外围光纤通道

        输出：
        - 若输入为字典，返回：
            - centre_Data_dict
            - outer_Data_dict
            - processed_Data_dict
            - plot_Data_dict
        - 若输入为 numpy 数组，返回：
            - centre_Data: 形状为 (..., 1) 的中心光纤数据
            - outer_Data: 形状为 (..., num_outer_channels) 的外围光纤数据
            - processed_Data: 中心补偿后的外围光纤数据
            - plot_Data: 由 centre_Data 与 outer_Data 按最后一个维度拼接得到的数据

        说明：
        - 本方法不修改输入 data，而是返回拆分及补偿后的结果
        - 当前实现使用第 1 列作为中心光纤通道
        """
        if isinstance(data, dict):
            centre_Data_dict = {}
            outer_Data_dict = {}
            processed_Data_dict = {}
            plot_Data_dict = {}
            for k, v in data.items():
                centre_Data_dict[k], outer_Data_dict[k], processed_Data_dict[k], plot_Data_dict[k] = self._process_centreData(data=v)
            return centre_Data_dict, outer_Data_dict, processed_Data_dict, plot_Data_dict
        elif isinstance(data, np.ndarray):
            # 使用 ... 适配任意维度，[0] 保持维度以便于后续广播相减
            centre_Data = data[..., [0]]
            outer_Data = data[..., 1:]
            processed_Data = outer_Data - centre_Data
            # 在最后一个维度上进行拼接
            plot_Data = np.concatenate([centre_Data, outer_Data], axis=-1)
            return centre_Data, outer_Data, processed_Data, plot_Data

    # -------------------- LUNA数据处理 --------------------
    def read_data_OFDR(self, folder_path):
        """
        从 LUNA/ODiSI 导出的多方向静态标定数据中读取、分组、预处理并重组通道数据。

        约定：
        - 数据目录按方向划分，即 folder_path 下包含多个以 direct 命名的子目录
        - 每个方向目录中存放若干 `_full.tsv` 文件
        - 文件名格式应匹配：
        ODiSI_xxxx_YYYY-MM-DD_HH-MM-SS_chX_full.tsv
        或
        ODiSI_xxxx_YYYY-MM-DD_HH-MM-SS_chX_gages_full.tsv
        - 同一时间戳下的多个通道文件视为同一组实验数据

        步骤：
        1. 遍历每个实验方向 direct 对应的子目录。
        2. 按文件名中的时间戳对 tsv 文件分组，每组对应一次采集。
        3. 从文件名解析物理通道号 phy_ch，并只保留激活通道对应的文件。
        4. 对每个物理通道、每个时间组：
            - 读取 tsv 数据；
            - 选取 NaN 最少的前 self.N 行求列均值；
            - 对缺失值做线性插值；
            - 用倍率阈值法修正局部突变点。
        5. 根据 self.sensing_ranges 提取各通道统一长度的有效传感区间。
        6. 对提取后的曲线执行平滑计算；当前版本仅计算平滑结果，不将其写入 self.Data。
        7. 先按物理通道升序组织成矩阵，再用 self.ch_order 重排到 active_channels 的输入顺序。
        8. 将排序后的时间戳依次映射到当前方向下的实验半径列表 self.radii[direct]['circ']。
        9. 最终写入 self.Data["circ"][direct][radius]。

        输入：
        - folder_path: LUNA 数据总目录路径，其下应包含以方向命名的子目录

        输出：
        - 无显式返回
        - 更新以下成员：
            - self.Data["circ"][direct][radius]
            - 值为形状为 (num_points, self.num_channels) 的 numpy 数组，单位缩放为 1e-6

        异常：
        - 当某个方向目录不存在时抛出 FileNotFoundError
        - 当某个物理通道缺少 OFDR 文件时抛出 ValueError
        - 当某物理通道缺少 sensing_ranges 配置时抛出 ValueError
        - 当某时间戳对应数组长度不足以完成切片时抛出 ValueError
        - 当某方向的时间组数超过当前方向预设半径数时抛出 ValueError

        说明：
        - 当前实现会计算 smoothed_data，但最终写入 self.Data 的仍是未平滑的 selected_interp_data
        - 最终列顺序语义与 read_data_FBG 保持一致
        """
        self.Data = {'circ': {}}

        physical_channels_sorted = sorted(self.active_channels.keys())

        for direct in self.exp_directs:
            file_folder = f"{folder_path}/{direct}"
            directory = Path(file_folder)

            if not directory.exists():
                raise FileNotFoundError(f"目录不存在: {directory}")

            pattern = re.compile(
                r'^ODiSI_\d+_\d{4}-\d{2}-\d{2}_(\d{2}-\d{2}-\d{2})_ch(\d+)(?:_gages)?_full$',
                re.IGNORECASE
            )

            # time_part -> {phy_ch: file_path}
            groups = defaultdict(dict)
            tsv_files = sorted(directory.glob('*_full.tsv'))

            for file in tsv_files:
                filename = file.stem
                match = pattern.match(filename)
                if not match:
                    logging.warning(f"文件名不符合预期格式，无法分组: {file.name}")
                    continue

                time_part = match.group(1)
                phy_ch = int(match.group(2))

                if phy_ch in self.active_channels:
                    groups[time_part][phy_ch] = file

            if len(groups) != len(self.radii[direct]['circ']):
                logging.warning(
                    f"预期分为 {len(self.radii[direct]['circ'])} 组，但实际分为 {len(groups)} 组。"
                )

            # grouped_data[time_part][phy_ch] = dataframe
            grouped_data = {}
            for group, file_map in groups.items():
                dataframes = {}
                for phy_ch, file in file_map.items():
                    try:
                        df = pd.read_csv(
                            file,
                            skiprows=31,
                            header=None,
                            sep='\t',
                            encoding='utf-8',
                            on_bad_lines='skip'
                        )
                        dataframes[phy_ch] = df
                    except Exception as e:
                        logging.error(f"错误: 读取文件 {file.name} 时发生错误: {e}")
                grouped_data[group] = dataframes

            interp_data = {}

            # 这里统一用“物理通道号”作为 key，与 self.sensing_ranges 对齐
            for phy_ch in physical_channels_sorted:
                interp_data_ch = {}

                for specific_time in sorted(grouped_data.keys()):
                    if phy_ch not in grouped_data[specific_time]:
                        raise ValueError(f"方向 {direct}、时间 {specific_time} 缺少物理通道 {phy_ch} 的 OFDR 文件。")

                    ch_data = grouped_data[specific_time][phy_ch]
                    all_frame_data = ch_data.iloc[2:, 3:]

                    frame_data = self._process_dataframe(df=all_frame_data)
                    frame_data_interp = pd.Series(frame_data).interpolate(method='linear',limit_direction='both')
                    processed_frame_data_interp = self._remove_outliers_by_ratio(array=frame_data_interp.to_numpy())

                    interp_data_ch[specific_time] = processed_frame_data_interp

                interp_data[phy_ch] = interp_data_ch

            selected_interp_data = self._extract_sensing_ranges(interp_data=interp_data)

            # 保留你原来的平滑流程；如果你想让最终 self.Data 使用平滑后的数据，
            # 只需把下面的 data_source 改成 smoothed_data。
            smoothed_data = {}
            for group_key, curves in selected_interp_data.items():
                smoothed_data[group_key] = {}
                for key, y in curves.items():
                    smoothed_data[group_key][key] = self._smooth_curve(y=y)

            # 为了最小改动，这里仍沿用你旧版的“未平滑结果写入 self.Data”行为
            data_source = selected_interp_data

            if not data_source:
                self.Data["circ"][direct] = {}
                continue

            timestamps = sorted(next(iter(data_source.values())).keys())

            if len(timestamps) > len(self.radii[direct]['circ']):
                raise ValueError(f"方向 {direct} 的时间组数 {len(timestamps)} 超过预设半径数 {len(self.radii[direct]['circ'])}。")

            timestamp_to_exp_samps = {timestamp: self.radii[direct]['circ'][idx] for idx, timestamp in enumerate(timestamps)}

            restructured_data = {}
            for timestamp in timestamps:
                if timestamp not in timestamp_to_exp_samps:
                    raise KeyError(f"Timestamp {timestamp} not found in timestamp_to_exp_samps")

                new_key = timestamp_to_exp_samps[timestamp]

                # 先按物理通道升序组装，语义与 read_data_FBG 的原始 data_matrix 保持一致
                data_matrix = np.column_stack([data_source[phy_ch][timestamp] for phy_ch in physical_channels_sorted]) * 1e-6

                # 再使用现有 read_data_FBG 同语义的 self.ch_order 重排到 active_channels 输入顺序
                if isinstance(data_matrix, np.ndarray):
                    data_matrix = data_matrix[:, self.ch_order]
                else:
                    data_matrix = [[row[i] for i in self.ch_order] for row in data_matrix]

                restructured_data[new_key] = data_matrix

            self.Data["circ"][direct] = restructured_data

    def _process_dataframe(self, df):
        """
        处理 DataFrame：选出包含 NaN 值最少的前 N 行，并计算每列的平均值。
        """
        # 计算每行 NaN 值的数量
        nan_counts = df.isna().sum(axis=1)
        
        # 按 NaN 值数量排序，选出包含 NaN 值最少的前 N 行
        rows_with_least_nan = df.loc[nan_counts.nsmallest(self.N).index]
        
        # 对每列计算平均值（跳过 NaN）
        column_means = rows_with_least_nan.mean()
        
        return column_means
    
    def _remove_outliers_by_ratio(self, array, ratio_threshold=5):
        """
        按与相邻值的相对倍率关系修正一维数组中的局部突变点。

        步骤：
        1. 创建输入数组的副本作为输出数组。
        2. 遍历数组中除首尾之外的各个位置。
        3. 若当前位置与前后相邻值的差值都超过 ratio_threshold 倍的相邻值绝对值，
        则将该位置视为局部突变点。
        4. 将突变点替换为前后相邻值的均值。

        输入：
        - array: 输入的一维数组
        - ratio_threshold: 判定局部突变点的倍率阈值；例如 5 表示差值超过相邻值绝对值的 5 倍时判为异常

        输出：
        - corrected_array: 修正后的一维数组，长度与输入相同

        说明：
        - 本方法不会删除数组元素，只会对满足条件的内部点做替换修正
        - 首尾两个元素不会被处理
        """
        corrected_array = array.copy()  # 创建副本以进行修改

        for i in range(1, len(array) - 1):  # 遍历数组，避开首尾两个元素
            prev_value = array[i - 1]  # 前一个值
            next_value = array[i + 1]  # 后一个值

            # 判断当前值是否为突变点（与前后值的差值超过 ratio_threshold 倍）
            if (abs(array[i] - prev_value) > ratio_threshold * abs(prev_value)) and (abs(array[i] - next_value) > ratio_threshold * abs(next_value)):
                # 如果是突变点，替换为相邻值的均值
                corrected_array[i] = (prev_value + next_value) / 2

        return corrected_array
    
    def _extract_sensing_ranges(self, interp_data):
        """
        从 interp_data 中按 self.sensing_ranges 指定的区间提取切片，并返回相同层级结构的新字典。

        步骤：
        1. 遍历 interp_data 中的每个物理通道。
        2. 根据 self.sensing_ranges[channel] 读取该通道对应的 start 与 end。
        3. 对该通道下的每个时间戳对应数组执行切片 array[start:end]。
        4. 将切片结果写入新的二级字典中并返回。

        输入：
        - interp_data: 二级字典
            - 一级 key: 物理通道号
            - 二级 key: 时间戳（如 "05-37-36"）
            - value: 一维数组

        输出：
        - result: 与 interp_data 具有相同层级结构的二级字典
            - 一级 key: 物理通道号
            - 二级 key: 时间戳
            - value: 提取后的数组切片

        异常：
        - 当某物理通道在 self.sensing_ranges 中缺少配置时抛出 ValueError
        - 当某时间戳对应数组长度不足以完成切片时抛出 ValueError
        """
        result = {}

        for channel, time_data in interp_data.items():
            # 获取当前 channel 的 start 和 end
            if channel not in self.sensing_ranges:
                raise ValueError(f"Missing range for {channel} in ranges dictionary.")
            start, end = self.sensing_ranges[channel]
            

            # 初始化存储当前通道的结果
            result[channel] = {}

            # 遍历时间戳，提取指定范围的切片
            for timestamp, array in time_data.items():
                if len(array) < end:
                    raise ValueError(f"Array under timestamp {timestamp} in {channel} is too short for range {start}:{end}.")
                # 提取切片并存储到新的字典中
                result[channel][timestamp] = array[start:end]

        return result
    
    def _smooth_curve(self, y):
        """
        对单条一维曲线做 Savitzky-Golay 平滑。

        处理流程：
        1. 从 self.smoothing_params 中读取 window_length 与 polyorder。
        2. 根据输入曲线长度对 window_length 做有限修正，确保：
        - 不超过输入长度；
        - 尽量保持为奇数。
        3. 对输入曲线执行平滑滤波并返回结果。

        输入：
        - y: 一维数组，表示某一通道在空间上的应变/信号曲线

        输出：
        - 平滑后的一维 numpy 数组，长度与输入一致

        说明：
        - 该方法仅负责单条曲线的平滑，不负责异常值处理与插值
        - 平滑参数由 self.smoothing_params 统一控制
        - 当前实现仅自动修正 window_length，不额外修正 polyorder
        """
        window_length = self.smoothing_params['window_length']
        polyorder = self.smoothing_params['polyorder']
        window_length = min(len(y) - 1 if len(y) % 2 == 0 else len(y), window_length)
        if window_length % 2 == 0:
            window_length += 1
        return savgol_filter(y, window_length, polyorder)

        
    # -------------------- FiberTecc动态数据接收 --------------------
    def receive_data_FiberTecc(self):
        """
        持续从解调仪 TCP 端口接收动态数据，并按设定频率推送处理后的数据帧到队列中。

        处理流程：
        1. 创建 TCP socket，并连接到 self.IP:self.PORT。
        2. 持续接收网络字节流，将其追加到 self.buffer。
        3. 调用 _process_buffer() 对缓存中的完整数据包进行解析与路由。
        4. 按 self.data_freq 控制推送频率，周期性调用 _prep_frame() 生成当前帧。
        5. 若队列已满，则丢弃最旧数据，再将新帧压入 self.data_queue。
        6. 当连接断开或发生异常时退出循环，并关闭 socket。

        输入：
        - 无（使用实例中的网络配置与缓存状态）

        输出：
        - 无直接返回值
        - 副作用：
        - 更新 self.buffer、self.current_snapshot、self.zero_points、self.is_zero_set
        - 将形状为 (1, self.total_points, self.num_channels) 的数据帧放入 self.data_queue

        异常：
        - 网络通信、连接中断、解析等异常会被捕获并打印
        - 无论是否异常退出，最终都会关闭 socket 连接

        说明：
        - 该方法通常运行于独立线程中，负责持续接收数据
        - 实际数据解析与预处理分别由 _process_buffer() 和 _prep_frame() 完成
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536) # 增大接收缓冲
            sock.connect((self.IP, self.PORT))
            print(f"已连接到解调仪 {self.IP}:{self.PORT}")
            print(f"激活通道配置: {self.active_channels}")

            last_push_time = time.time()        
            while True:
                # 接收网络数据
                try:
                    chunk = sock.recv(4096)
                    if not chunk: 
                        break
                    self.buffer.extend(chunk)
                except Exception:
                    break
                
                # 处理粘包
                self._process_buffer()

                # 推送数据
                now = time.time()
                if now - last_push_time >= 1 / self.data_freq:
                    data = self._prep_frame()
                    if self.data_queue.full():
                        try: 
                            self.data_queue.get_nowait()
                        except: 
                            pass
                    self.data_queue.put(data)
                    last_push_time = now

        except Exception as e:
            print(f"通信线程异常: {e}")
        finally:
            if sock: sock.close()

    def _process_buffer(self):
        """
        从接收缓存中解析完整数据包，并将解析出的传感器数据路由到对应通道与采样点。

        数据包约定：
        - 缓存前 4 字节为无符号整数，表示后续包体长度 N
        - 后续 N 字节为一个完整 packet body
        - packet body 的具体解析由 _parse_packet() 完成

        处理流程：
        1. 检查 self.buffer 中是否至少包含 4 字节包头。
        2. 读取包体长度 N，判断当前缓存是否已包含完整数据包。
        3. 若完整，则截取 packet body，并从缓存中移除该包。
        4. 调用 _parse_packet() 得到 (sensor_id, wavelength) 列表。
        5. 对每个传感器数据：
        - 解析物理通道号 phy_ch 与传感器索引 idx；
        - 检查是否属于激活通道且索引合法；
        - 将数据写入 self.current_snapshot 对应位置。
        6. 若某通道尚未设置归零基准，则逐点填充 zero_points；
        当该通道所有点均已初始化后，标记 is_zero_set[phy_ch] = True。

        输入：
        - 无（使用 self.buffer 中当前缓存的字节流）

        输出：
        - 无直接返回值
        - 副作用：
        - 消费 self.buffer 中已完整到达的数据包
        - 更新 self.current_snapshot
        - 可能更新 self.zero_points 与 self.is_zero_set

        说明：
        - 该方法可处理粘包情况，即一次接收中包含多个完整包
        - 对不完整数据包会保留在缓存中，等待后续字节到达
        """
        # 处理粘包
        while len(self.buffer) >= 4:
            N = struct.unpack('<I', self.buffer[0:4])[0]
            if len(self.buffer) < 4 + N: 
                break
            packet_body = self.buffer[4 : 4 + N]
            self.buffer = self.buffer[4 + N:]

            # 2. 解析数据
            sensor_list = self._parse_packet(packet_body)
            
            # 3. 数据路由 (Data Routing) - 列表驱动
            for sensor_id, wavelength in sensor_list:
                sid_str = str(sensor_id)
                if len(sid_str) < 3: 
                    continue
                try:
                    phy_ch = int(sid_str[0])    # 物理通道号 
                    idx = int(sid_str[1:]) - 1  # 传感器索引 (0~15)
                except: 
                    continue
                
                # 静态数据与几何都使用 raw_trim_idx 裁掉了固定件内部/区域外点；
                # 动态包仍携带原始点号，因此必须应用相同偏移。
                effective_idx = idx - self.raw_trim_idx
                if phy_ch in self.active_channels and 0 <= effective_idx < self.total_points:
                    # 找到对应的列
                    col = self.active_channels[phy_ch]
                    
                    if self.wavelength_jump_guard_enabled:
                        # 逐 FBG 连续性检查必须发生在绝对波长写入快照之前。
                        safe_wavelength = self._wavelength_guard.filter(
                            sensor_id=sensor_id,
                            wavelength=wavelength,
                        )
                        if safe_wavelength is None:
                            continue
                    else:
                        safe_wavelength = wavelength
                    self.current_snapshot[effective_idx, col] = safe_wavelength
                    
                    # 4. 归零基准设置 (首次收到有效数据时)
                    if not self.is_zero_set[phy_ch]:
                        if self.zero_points[phy_ch][effective_idx] is None:
                            self.zero_points[phy_ch][effective_idx] = safe_wavelength
                        
                        # 检查是否该通道已满
                        if all(v is not None for v in self.zero_points[phy_ch]):
                            self.is_zero_set[phy_ch] = True
                            print(f"物理通道 {phy_ch} 基准已设置")
        
    def _parse_packet(self, packet_body):
        """
        解析单个数据包包体，提取其中包含的传感器编号与数据。

        数据格式约定：
        - 包体前 2 字节表示传感器数量 sensor_count
        - 此后每个传感器块固定占 20 字节
        - 其中：
        - 偏移 2:4 为传感器 ID（unsigned short）
        - 偏移 16:20 为数据（float）

        处理流程：
        1. 读取包体中的 sensor_count。
        2. 按固定 20 字节步长遍历各个传感器块。
        3. 对每个块提取 sensor_id 与 wavelength。
        4. 将结果存储为 (sensor_id, wavelength) 元组列表返回。
        5. 若包体长度不足以支撑完整块，则停止解析剩余部分。

        输入：
        - packet_body: 单个完整数据包的包体字节串

        输出：
        - sensor_data_list: 列表，元素为 (sensor_id, wavelength) 二元组

        异常：
        - 若解析过程中发生异常，则打印错误信息并返回空列表

        说明：
        - 本方法只负责二进制解包，不负责通道映射、索引检查与数据写入
        - 后续的数据路由由 _process_buffer() 完成
        """
        try:
            sensor_count = struct.unpack('<H', packet_body[0:2])[0]
            sensor_data_list = []
            offset = 2

            for _ in range(sensor_count):
                if offset + 20 > len(packet_body): 
                    break
                sensor_block = packet_body[offset : offset + 20]
                # 偏移2-3: ID, 偏移16-19: 数据
                sensor_id = struct.unpack('<H', sensor_block[2:4])[0]
                wavelength = struct.unpack('<f', sensor_block[16:20])[0]
                sensor_data_list.append((sensor_id, wavelength))
                offset += 20

            return sensor_data_list
        
        except Exception as e:
            print(f"解析错误: {e}")
            return []

    def _prep_frame(self):
        """
        根据当前快照与归零基准，生成可供下游使用的单帧动态数据。

        处理流程：
        1. 初始化形状为 (self.total_points, self.num_channels) 的零矩阵。
        2. 遍历所有激活物理通道 phy_ch：
        - 若该通道已完成归零：
            1) 读取当数据 raw_vals；
            2) 读取对应基准值 base_vals；
            3) 计算差值 (raw_vals - base_vals) * 1000.0；
            4) 写入对应列。
        - 若尚未归零，则该通道整列保持为 0。
        3. 将结果 reshape 为 (1, self.total_points, self.num_channels) 并返回。

        输入：
        - 无（使用 self.current_snapshot、self.zero_points、self.is_zero_set）

        输出：
        - frame_to_send: numpy 数组，形状为 (1, self.total_points, self.num_channels)

        说明：
        - 返回结果中的数值表示相对于归零基准的变化量
        - 当前实现中使用乘以 1000.0 的缩放方式，具体物理意义取决于解调仪输出单位与后续处理约定
        - 该方法不会修改内部状态，仅根据当前缓存状态生成一帧数据
        """
        # 准备发送的数据帧 (1, self.total_points, self.num_channels)
        frame_to_send = np.zeros((self.total_points, self.num_channels))
        
        # 遍历白名单列表，按顺序填充数据
        for phy_ch in self.active_channels:
            i = self.active_channels[phy_ch]
            if self.is_zero_set[phy_ch]:
                raw_vals = self.current_snapshot[:, i]
                base_vals = np.array(self.zero_points[phy_ch]) # 处理可能存在的None。虽然is_zero_set为True理论上不会有None，但为了robustness，这里假设一旦set为True，base_vals全为float
                diff = (raw_vals - base_vals) * 1000.0 # 向量化计算: (当前值 - 基准值) * 1000
                frame_to_send[:, i] = diff
            else:
                # 未归零前发送0
                frame_to_send[:, i] = 0.0

        # 构造成 (1, self.total_points, self.num_channels) 的形状
        return frame_to_send.reshape(1, self.total_points, self.num_channels)
    
    # -------------------- Hippo动态数据接收 --------------------
    def receive_data_Hippo(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        sock.sendto(b'\x01\x02', (self.IP, self.PORT))
        sock.recv(2048)
        sock.sendto(b'\x01\x0A\x55', (self.IP, self.PORT))
        time.sleep(0.05)

        while True:
            try:
                wave8x16 = self._recv_010c_once(sock)          # (8,16) nm
            except socket.timeout:
                continue

            # data_received = {ch: wave8x16[i] for i, ch in enumerate(self.active_channels)}
            data_received = {phy_ch: wave8x16[phy_ch-1] for phy_ch in self.active_channels}

            for ch in self.active_channels:
                if self.zero_points[ch][0] is None:
                    self.zero_points[ch] = data_received[ch]
                    print(f"通道{ch}归零基准已设置")

            data = np.empty((1, 16, self.num_channels))
            for phy_ch, i in self.active_channels.items():
                data[0, :, i] = (data_received[phy_ch] - self.zero_points[phy_ch]) * 1000

            if self.data_queue.full():
                self.data_queue.get()
            self.data_queue.put(data)   

    def _recv_010c_once(self, sock):
        while True:
            data, _ = sock.recvfrom(2048)
            if data[:2] == b'\x01\x0C':
                break
        gratings = []
        off = 2
        while off < len(data):
            ch, m = data[off], data[off+1]
            off += 4
            waves = []
            for _ in range(m):
                w = struct.unpack('<I', data[off:off+4])[0] / 1000.0   # pm → nm
                waves.append(w)
                off += 4
            gratings.append((ch, m, waves))
        wave2d = np.zeros((8, 16))
        for ch, m, waves in gratings:
            if ch < 8 and waves:
                wave2d[ch, :len(waves)] = waves[:16]
        return wave2d
