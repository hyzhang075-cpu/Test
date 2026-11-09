import numpy as np
from scipy import stats

from sensor import Sensor

from tools.utils import dict_recur_extract_path, dict_recur_flatten, dict_recur_unflatten

class Initialiser(Sensor):
    """
    形状重构的初始化模块
    """
    def __init__(self, discont, segmentation, connect=True, global_phases_set=None, interlaced_offset=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.discont = discont
        self.segmentation = segmentation # 对应原本的segments
        self.num_segments = len(segmentation)
        self.connect = connect
        self.global_phases_set = global_phases_set
        self.interlaced_offset = interlaced_offset
        if not self.global_phases_set:
            self.global_phases_set = 0.0
            self.rot_seg_fit(verbose=False, update_phase=True) # 初始化正确的全局相位与全局扭转系数

    def rot_seg_fit(self, verbose, update_phase):
        """
        初始化全局相位，并基于标定数据估计每个方向 direct 下的初始分段扭转系数。

        当前实现优先使用 circ 数据参与全局相位和扭转系数拟合：
        - 若 self.radii[self.exp_directs[0]] 中存在 'circ'，则 fit_shapes={'circ'}；
        - 否则使用第一个可用标定形状作为 fit_shapes。

        circ 之外的其他标定形状，例如 S、end、end3、rot0、up、down，若存在于
        self.processed_Data 中，仍会递归计算并保存：
        - magnitude_results
        - angle_results_raw
        - angle_results_unwrap

        但默认不参与：
        - phase_pool
        - global_fit_direct
        - individual_fits_direct
        - slopes_init

        参数：
        - verbose: 是否打印初始化过程、初始角、全局相位和分段拟合结果。
        - update_phase: 是否根据 direct==0 的 phase_pool 更新 self.global_phases_set。

        处理流程：
        1. 选择参与相位和扭转拟合的 fit_shapes。
        2. 调用 _calculate_dynamic_angles(mode='init') 生成初始化阶段的通道角度。
        3. 初始化结果容器：
        - slopes_init
        - magnitude_results
        - angle_results_raw
        - angle_results_unwrap
        - global_fit_direct
        - individual_fits_direct
        4. 遍历每个 direct 和每种 calib_shape。
        5. 对当前标定数据递归展开，将每个叶子矩阵转换为 strain_data。
        6. 调用 _calculate_curvature_and_angle() 得到曲率模和曲率方向角。
        7. 对方向角执行 np.unwrap()，并记录初始角 init_angle。
        8. 将 flat 结果还原为原始嵌套结构并保存。
        9. 对 fit_shapes 中的数据：
        - 收集可用于估计全局相位的初始角；
        - 收集可用于分段线性拟合的 unwrap 角度曲线。
        10. 当 direct==0 且 update_phase=True 时，用 phase_pool 的平均值更新全局相位。
        11. 对 fit_angle_data_flat 执行：
        - _compute_global_fit()：合并所有有效数据做全局分段拟合；
        - _compute_individual_fits()：每组数据单独做分段拟合。
        12. 将 global_fit 的斜率取负后写入 self.slopes_init[direct]。

        输出：
        - 无返回值。
        - 更新：
            - self.global_phases_set
            - self.slopes_init
            - self.magnitude_results
            - self.angle_results_raw
            - self.angle_results_unwrap
            - self.global_fit_direct
            - self.individual_fits_direct

        说明：
        - 半径为 0 的 circ/S 数据不参与 phase_pool。
        - _compute_global_fit() 内部还会跳过半径为 0、200、300 的数据。
        - self.slopes_init[direct] 使用 [-group[0] for group in global_fit]，
        即拟合斜率取负后作为初始扭转系数。
"""
        fit_shapes = {'circ'} if 'circ' in self.radii[self.exp_directs[0]] else {next(iter(self.radii[self.exp_directs[0]]))} # 第一个测试方向对应的形状中包含'circ'则用'circ'，否则用其中的第一个形状

        theta_dynamic = self._calculate_dynamic_angles(mode='init', segments=None, seg_slopes=None)

        self.slopes_init = {}
        self.magnitude_results = {}
        self.angle_results_raw = {}
        self.angle_results_unwrap = {}
        self.global_fit_direct = {}
        self.individual_fits_direct = {}

        for calib_shape in self.calib_shapes:
            self.magnitude_results[calib_shape] = {}
            self.angle_results_raw[calib_shape] = {}
            self.angle_results_unwrap[calib_shape] = {}

        for direct in self.exp_directs:
            phase_pool = []
            phase_pool_sources = []
            fit_angle_data_flat = {}

            if verbose:
                print(f"-------------------- {direct}方向初始化开始 --------------------")

            for calib_shape in self.calib_shapes:
                if calib_shape not in self.processed_Data:
                    continue

                if direct not in self.processed_Data[calib_shape]:
                    continue

                calib_data = self.processed_Data[calib_shape][direct]

                if calib_shape in ['circ', 'S']:
                    target_data = {radius: calib_data[radius] for radius in self.radii[direct][calib_shape] if radius in calib_data}
                else:
                    target_data = calib_data

                # ---------- 递归路径展开，逐个数据计算 magnitude / angle raw / unwrap / init ----------
                target_data_flat = dict_recur_flatten(target_data)

                bundled_flat = {}

                for path, leaf in target_data_flat.items():
                    strain_data = np.asarray(leaf).T

                    magnitude, angle = self._calculate_curvature_and_angle(epsilon=strain_data, alpha_dynamic=theta_dynamic)

                    angle_unwrap_i = np.unwrap(angle, discont=self.discont)
                    init_angle_i = angle_unwrap_i[0]

                    bundled_flat[path] = (magnitude, angle, angle_unwrap_i, init_angle_i)

                # ---------- 将 flat 结果还原成原始树结构 ----------
                magnitude_raw = dict_recur_unflatten({path: bundle[0] for path, bundle in bundled_flat.items()})
                angle_raw = dict_recur_unflatten({path: bundle[1] for path, bundle in bundled_flat.items()})
                angle_unwrap = dict_recur_unflatten({path: bundle[2] for path, bundle in bundled_flat.items()})
                init_angle = dict_recur_unflatten({path: bundle[3] for path, bundle in bundled_flat.items()})

                self.magnitude_results[calib_shape][direct] = magnitude_raw
                self.angle_results_raw[calib_shape][direct] = angle_raw
                self.angle_results_unwrap[calib_shape][direct] = angle_unwrap

                # ---------- fit_shapes 中指定的标定形状参与 phase 与 fit；当前仅 circ ----------
                if calib_shape in fit_shapes:
                    for path, bundle in bundled_flat.items():
                        angle_unwrap_i = bundle[2]
                        init_angle_i = bundle[3]
                        # 先归一化到-pi~pi，便于比较理解
                        init_angle_i = (init_angle_i + np.pi) % (2 * np.pi) - np.pi

                        # ---------- inline _phase_leaf_ok ----------
                        use_for_phase = True

                        if calib_shape in ['circ', 'S']:
                            radius = path[0]
                            if radius == 0:
                                use_for_phase = False

                        if use_for_phase:
                            phase_pool.append(init_angle_i)
                            phase_pool_sources.append({
                                'direct': direct,
                                'calib_shape': calib_shape,
                                'path': path,
                                'angle': float(init_angle_i),
                            })

                        fit_key = (calib_shape,) + path
                        fit_angle_data_flat[fit_key] = angle_unwrap_i

                if verbose:
                    print(f"calib_shape: {calib_shape}")
                    print(f"initial angle: {init_angle}")

            # ---------- 联合更新全局相位 ----------
            if direct == 0 and update_phase and len(phase_pool) > 0:
                for source in phase_pool_sources:
                    print(
                        "phase_pool source: "
                        f"direct={source['direct']}, "
                        f"calib_shape={source['calib_shape']}, "
                        f"path={source['path']}, "
                        f"angle={source['angle']}"
                    )

                # 映射成单位圆上的向量做圆周平均，避免180度附近的角度平均为0度
                phase_array = np.asarray(phase_pool, dtype=float)
                mean_phase = np.arctan2(
                    np.mean(np.sin(phase_array)),
                    np.mean(np.cos(phase_array)),
                )
                self.global_phases_set = -float(mean_phase)

            # ---------- 联合做全局 / 个体分段拟合 ----------
            if len(fit_angle_data_flat) > 0:
                global_fit = self._compute_global_fit(angle_data=fit_angle_data_flat)

                individual_fits_flat = self._compute_individual_fits(angle_data=fit_angle_data_flat)

                self.global_fit_direct[direct] = global_fit
                self.individual_fits_direct[direct] = dict_recur_unflatten(individual_fits_flat)
                self.slopes_init[direct] = [-group[0] for group in global_fit]

                if verbose:
                    print(f"global phase: {self.global_phases_set}")
                    print(f"segment fit: {global_fit}")

                    slopes_detail = dict_recur_extract_path(self.individual_fits_direct[direct], lambda groups, path: [group[0] for group in groups])

                    print(f"slopes: {slopes_detail}")

    def _calculate_dynamic_angles(self, mode, segments, seg_slopes):
        """
        计算每个重构通道在各采样点处的动态角度。

        动态角度用于将多通道应变投影到二维曲率向量上。它由两部分组成：
        1. 每个重构通道在截面圆周上的初始角度；
        2. 沿传感距离累积的自扭转相位。

        参数：
        - mode: 计算模式。
        * 'init': 初始化模式，不考虑分段扭转累积，动态角度等于初始通道角度。
        * 'recon': 重构模式，根据 segments 和 seg_slopes 沿 self.samp_dist 累积扭转相位。
        - segments: 分段索引区间列表，格式为 [(start, end), ...]。
        仅 mode='recon' 时使用。
        - seg_slopes: 每个分段对应的扭转系数，单位通常为 rad/m。
        仅 mode='recon' 时使用。

        初始角度生成规则：
        1. 若 self.active_angles 非空且长度等于 self.num_channels_recon：
        - 使用 active_angles 指定的角度；
        - 输入单位为 degree，内部转换为 rad；
        - 每个角度加上 self.global_phases_set。
        2. 否则若 self.interlaced_grating=True：
        - 第一组采样点使用 theta_0_1；
        - 第二组采样点使用 theta_0_2 = theta_0_1 + self.interlaced_offset；
        - 根据 samp_dist_preset 和 samp_dist_preset_sub 的空间位置排序后穿插合并。
        3. 否则：
        - 默认认为所有重构通道在截面圆周上均匀分布；
        - 第 i 个通道角度为 global_phase + i * 2π / num_channels_recon。

        重构模式逻辑：
        - 在 mode='recon' 中，先初始化 twist_phase 为 0。
        - 按 segments 顺序遍历每一段，根据对应 slope 在该段内累积：
        twist_phase = current_twist + slope * delta_dist。
        - 每段结束后更新 last_position 与 current_twist，使后续分段相位连续。
        - 最终 theta_dynamic = theta_0 + twist_phase。

        输出：
        - theta_dynamic: numpy 数组，形状为 (self.num_channels_recon, len(self.samp_dist))。
        表示每个重构通道在每个采样点处的动态角度，单位 rad。

        异常：
        - interlaced_grating=True 且 self.samp_dist_preset_sub is None 时抛出 ValueError。

        说明：
        - 本方法只计算参与重构的通道角度，不包含被中心光纤补偿剔除的中心通道。
        - mode='recon' 中若某个分段越过 self.samp_dist 长度，会跳过该分段。
        - 当交错刻栅开启时，theta_0 可能本身就是二维矩阵，形状为
        (num_channels_recon, total_points)，以支持不同采样点处通道角度不同。
        """
        # 获取 active_angles 参数，如果不存在则为 None
        active_angles = self.active_angles
        
        # 判断是否传入了有效的 active_angles
        if active_angles is not None and len(active_angles) == self.num_channels_recon:
            # 将传入的角度(度)转换为弧度，并加上全局相位
            theta_0_list = [self.global_phases_set + np.deg2rad(ang) for ang in active_angles]
            theta_0 = np.array([theta_0_list]).T
        else:
            if self.interlaced_grating:
                if self.samp_dist_preset_sub is None:
                    raise ValueError("交错刻栅模式下，samp_dist_preset_sub 不能为空")
                theta_0_1 = np.array([[self.global_phases_set + i * 2*np.pi/(self.num_channels_recon) for i in range(self.num_channels_recon)]]).T
                theta_0_2 = np.array([[self.global_phases_set + self.interlaced_offset + i * 2*np.pi/(self.num_channels_recon) for i in range(self.num_channels_recon)]]).T

                p1 = np.array(self.samp_dist_preset)
                p2 = np.array(self.samp_dist_preset_sub)
                
                # 按照各自的采样点数量进行水平平铺
                theta_0_1_full = np.repeat(theta_0_1, len(p1), axis=1)
                theta_0_2_full = np.repeat(theta_0_2, len(p2), axis=1)
                
                # 拼接后根据位置排序索引进行穿插重排
                theta_0_combined = np.concatenate((theta_0_1_full, theta_0_2_full), axis=1)
                p_combined = np.concatenate((p1, p2))
                sort_idx = np.argsort(p_combined)
                
                # 此时 theta_0 是一个形状为 (num_channels_recon, total_points) 的矩阵
                theta_0 = theta_0_combined[:, sort_idx]
            
            else:# 默认的均匀分布逻辑
                theta_0 = np.array([[self.global_phases_set + i * 2*np.pi/self.num_channels_recon for i in range(self.num_channels_recon)]]).T
            
        if mode == 'init':
            # theta_0 加上 0 矩阵保持形状一致
            theta_dynamic = theta_0 + np.zeros((self.num_channels_recon, len(self.samp_dist)))
        elif mode == 'recon':
            seg_frequencies = [slope for slope in seg_slopes]
            
            # 仅记录光纤由于扭转累积的整体相位 (1, total_points)
            twist_phase = np.zeros((1, len(self.samp_dist)))
            last_position = self.samp_dist[0]
            current_twist = 0.0
            
            # 按顺序处理每个分段，累积扭转相位
            for seg, freq in zip(segments, seg_frequencies):
                seg_start, seg_end = seg
                seg_slice = slice(seg_start, seg_end)
                
                if seg_start >= len(self.samp_dist) or seg_end > len(self.samp_dist):
                    continue

                # 计算相对距离（相对于累积基准位置）
                delta_dist = (self.samp_dist[seg_slice] - last_position)  # m
                # 计算当前分段的扭转累积
                twist_phase[0, seg_slice] = current_twist + freq * delta_dist
                
                # 更新基准相位和位置
                if seg_end <= len(self.samp_dist):
                    last_position = self.samp_dist[seg_end-1]
                    current_twist = twist_phase[0, seg_end-1]
                    
            # 最终动态角度 = 固有初始角度 + 累积扭转角度
            # 利用 numpy 的 broadcast 机制：(3, 1) + (1, N) 或 (3, N) + (1, N) 都能正确相加
            theta_dynamic = theta_0 + twist_phase

        return theta_dynamic

    def _calculate_curvature_and_angle(self, epsilon, alpha_dynamic):
        """
        根据多通道应变和动态通道角度计算曲率模与曲率方向角。

        参数：
        - epsilon: 各重构通道的应变数据。
        形状通常为 (self.num_channels_recon, num_points)。
        - alpha_dynamic: 各重构通道在各采样点处的动态角度。
        形状通常为 (self.num_channels_recon, num_points)。

        计算公式：
        - kappa_x = -2 / (num_channels_recon * R) * Σ epsilon_i * cos(alpha_i)
        - kappa_y = -2 / (num_channels_recon * R) * Σ epsilon_i * sin(alpha_i)
        - curvature_magnitude = sqrt(kappa_x^2 + kappa_y^2)
        - curvature_angle = atan2(kappa_y, kappa_x)

        输出：
        - curvature_magnitude: numpy 数组，表示每个采样点处的曲率模。
        - curvature_angle: list，表示每个采样点处的曲率方向角，单位 rad，范围映射到 [-π, π]。

        说明：
        - epsilon 和 alpha_dynamic 会先转换为 np.float64。
        - self.R 为外围光纤到中心的半径，单位 m。
        - 当前实现假设参与重构的通道在曲率求解中等权。
        - curvature_angle 返回为 Python list，而不是 numpy 数组。
        """
        # 计算曲率向量的 x 和 y 分量

        epsilon = np.asarray(epsilon, dtype=np.float64)
        alpha_dynamic = np.asarray(alpha_dynamic, dtype=np.float64)

        kappa_x = -2 / (self.num_channels_recon * self.R) * np.sum(epsilon * np.cos(alpha_dynamic), axis=0)
        kappa_y = -2 / (self.num_channels_recon * self.R) * np.sum(epsilon * np.sin(alpha_dynamic), axis=0)

        # 计算曲率模
        curvature_magnitude = np.sqrt(kappa_x**2 + kappa_y**2)

        # 计算曲率向量与坐标轴的夹角 (弧度)
        curvature_angle = np.arctan2(kappa_y, kappa_x)
        # curvature_angle = [ang + 2*np.pi if ang < 0 else ang for ang in curvature_angle]    #转化到0-2pi
        # 转化到-pi到pi范围内
        curvature_angle = [ang if -np.pi <= ang <= np.pi else (ang + 2*np.pi if ang < -np.pi else ang - 2*np.pi) for ang in curvature_angle]

        # curvature_magnitude = np.full(shape=len(curvature_magnitude), fill_value=np.mean(curvature_magnitude[:-1]))
        return curvature_magnitude, curvature_angle

    def _compute_global_fit(self, angle_data):
        """
        对多条标定曲线合并后的自扭转角度-距离数据做分段全局线性拟合。

        该方法用于估计某个 direct 下统一的分段扭转系数。它会把多个标定数据中
        同一分段的数据池化到一起，再对每个分段统一拟合一条直线。

        参数：
        - angle_data: 字典。
        key 可以是：
        * 半径；
        * 或 (calib_shape, ...path) 形式的完整路径键。
        value 为对应标定数据的 unwrap 角度序列。

        处理流程：
        1. 为每个分段建立 pooled_x 和 pooled_y。
        2. 遍历 angle_data 中的每条角度曲线。
        3. 从 key 中解析半径：
        - 若 key 是 tuple 且长度大于 1，则使用 key[1] 作为半径；
        - 否则直接使用 key。
        4. 跳过半径为 0、200、300 的数据。
        5. 调用 _segment_data() 得到当前曲线的 x_data、y_data 和分段索引。
        6. 将每条曲线中同一分段的数据加入对应 pooled_x / pooled_y。
        7. 将所有非空分段拼接为 combined_x / combined_y，并生成 merged_segments。
        8. 调用 _piecewise_linear_fit() 对合并数据逐段拟合。
        9. 若部分分段无数据，则用 (np.nan, np.nan) 补齐到 self.num_segments 长度。

        输出：
        - fit_results: list[tuple]。
        每个元素为对应分段的 (slope, intercept)。
        若所有数据都不可用，则返回 [(np.nan, np.nan)] * self.num_segments。

        说明：
        - 这是“全局拟合”：同一 direct 下多个半径/标定条件的数据会被合并后共同拟合。
        - self.slopes_init[direct] 后续会使用这里得到的 slope 的相反数。
        """
        pooled_x = [[] for _ in range(self.num_segments)]
        pooled_y = [[] for _ in range(self.num_segments)]

        for key, angles in angle_data.items():
            # 兼容 fit_key = (calib_shape,) + path 的情况
            radius = key[1] if isinstance(key, tuple) and len(key) > 1 else key

            if radius in {0, 200, 300}:
                continue

            x_data, y_data, segments = self._segment_data(angles=angles)

            for idx, (start, end) in enumerate(segments):
                if idx >= self.num_segments:
                    break
                pooled_x[idx].extend(x_data[start:end])
                pooled_y[idx].extend(y_data[start:end])

        combined_x = []
        combined_y = []
        merged_segments = []
        current = 0

        for xs, ys in zip(pooled_x, pooled_y):
            if len(xs) == 0:
                continue
            seg_len = len(xs)
            combined_x.extend(xs)
            combined_y.extend(ys)
            merged_segments.append((current, current + seg_len))
            current += seg_len

        if len(combined_x) == 0:
            return [(np.nan, np.nan)] * self.num_segments

        fit_results = self._piecewise_linear_fit(y_data=np.asarray(combined_y, dtype=float), x_data=np.asarray(combined_x, dtype=float), segments=merged_segments)

        # 若某些段完全没有数据，可补齐到固定长度
        if len(fit_results) < self.num_segments:
            fit_results += [(np.nan, np.nan)] * (self.num_segments - len(fit_results))

        return fit_results
    
    def _compute_individual_fits(self, angle_data):
        """
        对每条标定曲线分别做分段线性拟合。

        与 _compute_global_fit() 不同，本方法不会合并不同标定数据，而是对每个 key
        对应的角度曲线单独执行分段拟合，用于观察单组数据自己的扭转趋势。

        参数：
        - angle_data: 字典。
        key 可以是半径，也可以是 (calib_shape, ...path) 形式的完整路径键。
        value 为对应标定数据的 unwrap 角度序列。

        处理流程：
        1. 遍历 angle_data 中每条曲线。
        2. 若 key 本身等于 0，则跳过该组数据。
        3. 调用 _segment_data() 生成 x_data、y_data 和分段索引。
        4. 调用 _piecewise_linear_fit() 得到该曲线的分段拟合结果。
        5. 将结果保存到 individual_fits[key]。

        输出：
        - individual_fits: 字典。
        key 与输入 angle_data 的 key 对应；
        value 为该曲线的分段拟合结果 list[(slope, intercept), ...]。

        说明：
        - 当前实现只直接跳过 key == 0 的情况。
        - 若 key 是 (calib_shape, ...path) 形式，即使其中包含半径 0，也不会被该判断自动跳过；
        如需严格跳过完整路径中的半径 0，需要额外解析 key。
        """
        individual_fits = {}

        for radius, angles in angle_data.items():
            if radius == 0:
                continue

            x_data, y_data, segments = self._segment_data(angles=angles)
            individual_fits[radius] = self._piecewise_linear_fit(y_data, x_data, segments)

        return individual_fits
    
    def _piecewise_linear_fit(self, y_data, x_data, segments):
        """
        对给定 x/y 数据按指定分段逐段执行线性回归。

        参数：
        - y_data: 因变量数组，通常为 unwrap 后的曲率方向角，单位 rad。
        - x_data: 自变量数组，通常为采样距离 self.samp_dist 的子序列，单位 m。
        - segments: 分段索引区间列表，格式为 [(start, end), ...]。
        区间采用左闭右开形式。

        处理流程：
        1. 遍历每个分段 (start, end)。
        2. 使用 slice(start, end) 提取当前分段的 x_seg 和 y_seg。
        3. 若当前分段有效点数少于 2，则返回 (np.nan, np.nan)。
        4. 否则调用 scipy.stats.linregress() 做一元线性回归。
        5. 保存当前分段的 slope 和 intercept。

        输出：
        - results: list[tuple]。
        每个元素为对应分段的 (slope, intercept)。
        slope 和 intercept 均转换为 float。
        有效点不足的分段返回 (np.nan, np.nan)。

        说明：
        - 本方法只负责拟合，不负责 unwrap、不负责分段生成，也不负责异常半径过滤。
        - slope 的单位通常为 rad/m，可理解为该分段的自扭转角速度或扭转频率估计。
        """
        results = []
        for start, end in segments:
            seg_slice = slice(int(start), int(end))
            x_seg = x_data[seg_slice]
            y_seg = y_data[seg_slice]
            if len(x_seg) and np.all(x_seg == x_seg[0]):
                # A singleton first point defines phase only, not a spatial derivative.
                results.append((0.0, float(np.mean(y_seg))))
                continue
            if len(x_seg) < 2 or len(y_seg) < 2:
                results.append((np.nan, np.nan))
                continue
            slope, intercept, *_ = stats.linregress(x_seg, y_seg)
            results.append((float(slope), float(intercept)))
        return results

    def _segment_data(self, angles):
        """
        为单条自扭转角度曲线生成对应的距离数组、unwrap 角度数组和拟合分段。

        参数：
        - angles: 单条曲率方向角序列，单位 rad。
        可以是原始 angle，也可以是已经部分展开的角度序列；本方法内部会再次调用 np.unwrap()。

        处理流程：
        1. 使用 np.unwrap(angles, discont=self.discont) 得到连续角度曲线 unwrapped。
        2. 取 unwrapped 与 self.samp_dist 的共同有效长度 raw_valid_length。
        3. 根据 self.zero_init 决定 x/y 数据的起点：
        - 若 self.zero_init=True，则从第 0 个采样点开始使用；
        - 若 self.zero_init=False，则跳过第 0 个采样点，从第 1 个采样点开始使用。
        4. 截断 x_data 和 y_data，使二者长度一致。
        5. 若 total_points<=0，则返回空分段。
        6. 调用 _calculate_segments(total_points) 生成不重叠基础分段 base_segments。
        7. 若 self.connect=False，直接返回 base_segments。
        8. 若 self.connect=True：
        - 第 0 段保持不变；
        - 从第 1 段开始，每段 start 向左扩展 1 个点；
        - end 保持不变；
        - 以此让相邻分段在拟合时共享一个边界点。

        输出：
        - x_data: 与角度曲线对应的采样距离数组，单位 m。
        - y_data: unwrap 后的角度数组，单位 rad。
        - segments: 用于拟合的分段索引区间列表，格式为 [(start, end), ...]。

        说明：
        - segments 采用左闭右开区间。
        - connect=True 只影响拟合阶段的分段索引，不改变原始 x_data/y_data。
        - self.zero_init 的语义来自 Sensor.generate_samp_dist()：当 ad_samp_dist 中需要补起点虚拟点时，
        这里保留第 0 个真实采样点；否则跳过第 0 个点以避免起点对拟合造成影响。
        """
        unwrapped = np.unwrap(angles, discont=self.discont)
        raw_valid_length = min(len(unwrapped), len(self.samp_dist))

        if self.zero_init or self.straight_trim != 0:   #如果是裁剪了，那第一个点也要保留
            x_data = self.samp_dist[:raw_valid_length]
            y_data = unwrapped[:raw_valid_length]
        else:
            x_data = self.samp_dist[1:raw_valid_length]
            y_data = unwrapped[1:raw_valid_length]

        total_points = min(len(x_data), len(y_data))
        x_data = x_data[:total_points]
        y_data = y_data[:total_points]

        if total_points <= 0:
            return x_data, y_data, []

        # Step 1: 生成不重叠基础分段
        base_segments = self._calculate_segments(total_points)

        if all(int(end) - int(start) == 1 for start, end in base_segments):
            # Independent interval slopes: point j uses the interval (j-1,j).
            return x_data, y_data, [(max(int(start)-1, 0), int(end))
                                    for start, end in base_segments]

        # Step 2: 如果不启用连接，则直接返回不重叠分段
        if not self.connect:
            return x_data, y_data, base_segments

        # Step 3: 启用连接时，从第二段开始，每段向左拓展 1 个点
        if len(base_segments) <= 1:
            return x_data, y_data, base_segments

        segments = []

        for idx, (start, end) in enumerate(base_segments):
            start = int(start)
            end = int(end)

            # 首段不变；此后每段向左拓展一个点
            if idx > 0:
                start = max(start - 1, 0)

            if end > start:
                segments.append((start, end))

        return x_data, y_data, segments

    def _calculate_segments(self, total_points):
        """
        根据 self.segmentation 和当前数据长度生成不重叠分段。

        参数：
        - total_points: 当前可用于拟合或重构的数据点总数。

        segmentation 规则：
        - self.segmentation = [n1, n2, ..., nk]
        - 列表长度 k 表示目标分段数。
        - 每个元素 ni 表示对应分段的点数。

        处理流程：
        1. 若 total_points <= 0，返回空列表 []。
        2. 检查 self.segmentation 是否为非空 list 或 tuple。
        若非法，则退化为单段 [(0, total_points)]。
        3. 尝试将 segmentation 中每个元素转换为 int。
        若转换失败，则退化为单段。
        4. 若存在负数，则退化为单段。
        5. 删除长度为 0 的分段。
        若删除后为空，则退化为单段。
        6. 从头到尾按 segmentation 指定长度生成左闭右开的不重叠分段。
        7. 最后一段自动吸收所有剩余点，避免尾部数据未被覆盖。
        8. 若 segmentation 总长度超过 total_points，则自动在 total_points 处截断。

        输出：
        - segments: 分段区间列表，格式为 [(start, end), ...]。
        若无法生成有效分段，则返回 [(0, total_points)]。

        说明：
        - 本方法生成的是基础不重叠分段。
        - 若 self.connect=True，相邻段共享边界点的逻辑不在这里执行，而是在 _segment_data() 中执行。
        - 返回分段通常用于 _piecewise_linear_fit() 或后续重构中的分段扭转系数应用。
        """
        if total_points <= 0:
            return []

        seg_cfg = self.segmentation

        # segmentation 必须是非空 list / tuple
        if not isinstance(seg_cfg, (list, tuple)) or len(seg_cfg) == 0:
            return [(0, total_points)]

        # 尝试转成整数列表
        try:
            lengths = [int(x) for x in seg_cfg]
        except (TypeError, ValueError):
            return [(0, total_points)]

        # 不允许负数
        if any(x < 0 for x in lengths):
            return [(0, total_points)]

        # 去掉 0 长度段；如果全为 0，则退化为单段
        lengths = [x for x in lengths if x > 0]
        if len(lengths) == 0:
            return [(0, total_points)]

        segments = []
        start = 0

        for i, seg_len in enumerate(lengths):
            if start >= total_points:
                break

            # 最后一段吸收所有剩余点，避免尾部漏点
            if i == len(lengths) - 1:
                end = total_points
            else:
                end = min(start + seg_len, total_points)

            if end > start:
                segments.append((start, end))

            start = end

        return segments if segments else [(0, total_points)]
