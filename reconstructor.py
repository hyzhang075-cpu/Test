import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.interpolate import CubicHermiteSpline, PchipInterpolator

from initialiser import Initialiser

from utils import dict_recur_paths, dict_recur_unflatten, dict_recur_extract_path

class Reconstructor(Initialiser):
    """
    形状重构模块
    """
    def __init__(self, soft=True, frame_rule='TNB', rot_ang=0.0, turn_threshold=2.0, init_weight=1.0, weights=None, slopes=None, min_consecutive=3, sharpness=4.8, end_start=-6, end_weights=False, thresholds=[0.8, 1.5, 2.0, 3.0, 4.0], 
                 TNB_threshold=0.15, interp_num=60, move_filter=3, kalman_params={'angle': {'Rk': 0.001, 'Bk': 0.001}, 'magnitude': {'Rk': 0.0001, 'Bk': 0.01}},
                 curvature_interp='hermite', nonnegative_curvature=False, rot_ang_by_direct=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rot_seg_fit(verbose=True, update_phase=False) # 打印初始信息，但不更新全局相位
        self.magnitude_ratio = dict_recur_extract_path(self.magnitude_results, lambda arr, path: 1.0 if path[-1] == 0 else float((1000 / path[-1]) / np.mean(arr)))
        # 重构所需参数
        self.soft = soft
        self.frame_rule = frame_rule
        self.turn_threshold = turn_threshold
        self.thresholds = thresholds # 曲率分级阈值
        self.min_consecutive = min_consecutive
        self.sharpness = sharpness

        self.num_levels = len(self.thresholds) + 1 
        self.base_segments = self._calculate_segments(total_points=self.total_points)
        self.end_mask = np.arange(self.total_points) >= self.total_points + end_start
        self.TNB_threshold = TNB_threshold # FS重构时直接复制上一点的曲率大小阈值

        # 需要优化的应变权重、扭转系数以及旋转角度
        self.end_weights = end_weights # 是否优化末端权重
        self.init_weight = init_weight
        if not weights:
            self.weights = {direct: np.ones(2 * self.num_levels) for direct in self.exp_directs} if self.end_weights else {direct: init_weight * np.ones(self.num_levels) for direct in self.exp_directs}
        else:
            self.weights = weights

        if not slopes:
            # 若涉及S形弯优化，则准备两组扭转系数，否则一组
            self.slopes = {direct: np.array([np.concatenate((self.slopes_init[direct], self.slopes_init[direct])) for _ in range(self.num_levels)]) for direct in self.exp_directs} if 'S' in self.calib_shapes else {direct: np.array([self.slopes_init[direct] for _ in range(self.num_levels)]) for direct in self.exp_directs} 
        else:
            self.slopes = slopes
        self.rot_ang = rot_ang
        self.rot_ang_by_direct = rot_ang_by_direct or {} 

        # 滤波、插值所需参数
        self.move_filter = move_filter
        self.kalman_params = kalman_params
        self.interp_num = interp_num
        self.curvature_interp = self._normalise_curvature_interp(curvature_interp)
        self.nonnegative_curvature = bool(nonnegative_curvature)

    @staticmethod
    def _normalise_curvature_interp(method):
        """Return the canonical production curvature interpolation mode."""
        aliases = {'pchip': 'scalar_pchip'}
        canonical = aliases.get(method, method)
        supported = {'hermite', 'scalar_pchip', 'vector_linear', 'vector_pchip'}
        if canonical not in supported:
            raise ValueError(
                "curvature_interp must be one of: hermite, pchip, "
                "scalar_pchip, vector_linear, vector_pchip"
            )
        return canonical

    @staticmethod
    def _vector_curvature_method(mode):
        """Map a production vector mode to its component interpolation method."""
        methods = {
            'vector_linear': 'linear',
            'vector_pchip': 'pchip',
        }
        try:
            return methods[mode]
        except KeyError as exc:
            raise ValueError(f"unsupported vector curvature mode: {mode}") from exc

    def reconstruct_shapes(self, calib_shape, direct, verbose=False, force_ideal_magnitude=False):
        """
        对指定标定形状和方向下的所有数据执行三维形状重构。

        参数：
        - calib_shape: 标定形状类型，例如 'circ'、'S'、'end'、'end3'、'rot0'、'up'、'down'。
        - direct: 标定方向角，对应 self.exp_directs 中的一个方向。
        - verbose: 是否打印每组重构的中间信息。

        处理流程：
        1. 从 self.processed_Data[calib_shape][direct] 中取出当前方向下的数据。
        2. 读取当前 direct 对应的 weight 和 slope。
        3. 根据 calib_shape 构造待重构数据的路径树：
        - circ/S: 单层路径，以 radius 为 key；
        - end/end3/rot0/up/down: 双层路径，以 radius 和末级参数为 key。
        4. 根据 direct 和当前形状的 rot_dir 生成绕 x 轴旋转矩阵。
        5. 遍历路径树中的所有叶节点，逐组调用 _reconstruct_frame()：
        - 将应变转换为曲率大小和方向角；
        - 滤波、插值；
        - 根据 frame_rule 重构三维曲线。
        6. 对每条重构曲线施加方向旋转 r @ rot_matrix.T。
        7. 将 flat_results 还原为与输入数据一致的嵌套结构。

        输出：
        - r_results_postrot: 与标定数据结构一致的重构结果字典。
        每个叶节点为形状 (interp_num, 3) 的三维曲线坐标数组。
        - interp_dist: 插值后的空间采样距离数组。

        说明：
        - 当前实现中 magnitude_ratio 被强制设为 1.0。
        - rot_matrix 只在重构曲线完成后应用，不影响曲率和角度估计过程。
        - 若 verbose=True，会打印 keys 和旋转前的 r。
        """
        # ---------- 初始准备 ----------
        calib_Data = self.processed_Data[calib_shape][direct]
        weight = self.weights[direct]
        slope = self.slopes[direct]

        interp_dist = None
        rot_dir = self.rot_dir[self.calib_shapes.index(calib_shape)]
        rot_matrix = self._get_rot_x(direct=direct, rot_dir=rot_dir)

        # ---------- 构造路径树 ----------
        if calib_shape in ['circ', 'S']:
            path_tree = {radius: None for radius in self.radii[direct][calib_shape]}
        else:
            path_tree = {radius: {idx: None for idx in self.radii[direct][calib_shape][radius]} for radius in self.radii[direct][calib_shape]}

        # ---------- 遍历所有叶节点路径并重构 ----------
        flat_results = {}

        for path in dict_recur_paths(path_tree):
            keys = list(path)

            radius = keys[0]
            # magnitude_ratio = self.magnitude_ratio[calib_shape][direct][radius]
            magnitude_ratio = 1.0 # 如果不使用magnitude_ratio, 就把上一行注释掉，用这一行

            if isinstance(magnitude_ratio, dict):
                magnitude_ratio = magnitude_ratio[keys[1]]

            _, _, _, interp_dist, r, _, _, _, _ = self._reconstruct_frame(keys=keys, calib_shape=calib_shape, calib_Data=calib_Data, weight=weight, slope=slope, magnitude_ratio=magnitude_ratio, init_T=[1.0, 0.0, 0.0], verbose=verbose, force_ideal_magnitude=force_ideal_magnitude)

            r_postrot = r @ rot_matrix.T
            flat_results[path] = r_postrot

            if verbose:
                print(f"keys: {keys}")
                print(f"r: {r}")
                print()

        # ---------- 还原为原本嵌套结构 ----------
        r_results_postrot = dict_recur_unflatten(flat_results)

        return r_results_postrot, interp_dist

    def _reconstruct_frame(self, keys, calib_shape, calib_Data, weight, slope, magnitude_ratio, init_T, verbose=False, unwrap_threshold=0.65, align_threshold=0.15, angle_prev=None, angle_unwrap_prev=None, force_ideal_magnitude=False):
        """
        对单组应变数据执行完整的单帧三维重构流程。

        参数：
        - keys: 当前数据在 calib_Data 中的路径。
        * None: 直接使用 calib_Data；
        * [radius]&#58; 使用 calib_Data[radius]；
        * [radius, idx]&#58; 使用 calib_Data[radius][idx]。
        - calib_shape: 当前标定形状类型。
        - calib_Data: 当前 direct 下的标定数据字典。
        - weight: 当前 direct 下的曲率等级应变权重。
        - slope: 当前 direct 下的曲率等级分段扭转系数。
        - magnitude_ratio: 曲率大小比例修正系数，用于曲率分级前的 score_magnitude。
        - init_T: 初始切向量，通常为 [1.0, 0.0, 0.0]。
        - verbose: 是否打印插值距离、角度、曲率和初始法向量等中间信息。
        - unwrap_threshold: 帧间 unwrap 分支选择阈值。
        - align_threshold: 若首点曲率低于该阈值且存在上一帧角度，则用上一帧首点角度对齐当前首点。
        - angle_prev: 上一帧 raw angle，用于动态重构时保持帧间相位连续。
        - angle_unwrap_prev: 上一帧 unwrap angle，用于动态重构时选择最接近上一帧的 2π 分支。

        处理流程：
        1. 调用 _Strain_2_Cur() 得到最终用于重构的曲率大小 magnitude 与方向角 angle。
        2. 若提供上一帧角度且当前首点曲率很小，则用上一帧首点角度对齐当前首点。
        3. 根据 zero_init 和 end_point 处理虚拟点：
        - zero_init=True: 在开头复制第一个真实点的 magnitude 和 angle；
        - zero_init=False: 将 angle[0] 设置为 angle[1]；
        - end_point=True: 在末尾复制最后一个真实点的 magnitude 和 angle。
        4. 调用 _framewise_unwrap_limit() 得到连续角度 angle_unwrap。
        5. 对 angle_unwrap 做移动平均滤波。
        6. 对 magnitude 做 Kalman 滤波。
        7. 检查滤波后的角度和曲率是否包含 NaN / inf。
        8. 使用 _KT_Hermit_interp_tang() 对角度和曲率分别按 self.ad_samp_dist 做 Hermite 插值。
        9. 根据插值后的首点角度构造初始法向量 init_N。
        10. 根据 self.frame_rule 选择重构方式：
            - 'TNB': 由角度差分计算 torsion，并调用 _F_S_frame()；
            - 'TNN': 调用 _parallel_frame()。

        输出：
        - 若 frame_rule == 'TNB':
        返回 angle, angle_unwrap, cur_interp, interp_dist, r, T, N, B。
        - 若 frame_rule == 'TNN':
        返回 angle, angle_unwrap, cur_interp, interp_dist, r, T, N1, N2。

        异常：
        - 若滤波后的角度或曲率包含非有限值，抛出 ValueError 并附带 calib_shape 和 keys。
        - 若插值过程中数据长度与 self.ad_samp_dist 不一致或包含非法值，抛出带上下文的 ValueError。

        说明：
        - 本方法是单条曲线的完整重构入口。
        - 动态展示时可通过 angle_prev / angle_unwrap_prev 保持相邻帧 angle unwrap 的连续性。
        - self.cur_interp 会被更新为当前帧插值后的曲率数组，主要用于调试或外部诊断。
        """
        # ---------- 计算重构使用的曲率大小与方向 ----------
        magnitude, angle = self._Strain_2_Cur(keys=keys, calib_shape=calib_shape, calib_Data=calib_Data, weight=weight, slope=slope, magnitude_ratio=magnitude_ratio, verbose=verbose)
        magnitude_raw = magnitude.copy()
        angle_raw = angle.copy()
        if force_ideal_magnitude:
            magnitude = self._construct_ideal_magnitude_for_recon(keys=keys, calib_shape=calib_shape, sample_dist=self.samp_dist)
        if angle_prev is not None and magnitude[0] < align_threshold:
            angle[0] = angle_prev[0]
        
        if self.zero_init:
            magnitude = np.insert(magnitude, 0, magnitude[0])  # 起点复制第一个传感点
            angle = np.insert(angle, 0, angle[0])
        else:
            angle[0] = angle[1]

        if getattr(self, "end_point", False):
            magnitude = np.append(magnitude, magnitude[-1])  # 末端复制最后一个传感点
            angle = np.append(angle, angle[-1])
        # print(magnitude)
        # ---------- 重构前预处理 ----------
        angle_unwrap = self._framewise_unwrap_limit(angle=angle, angle_prev=angle_prev, angle_unwrap_prev=angle_unwrap_prev, unwrap_threshold=unwrap_threshold)
        ang_filter = self._moving_average_scipy(data=angle_unwrap, window_size=self.move_filter, mode='reflect')
        cur_kal = self._Kalman_filter(data=magnitude, Rk=self.kalman_params['magnitude']['Rk'], Bk=self.kalman_params['magnitude']['Bk'])

        # 增加上下文信息字符串，方便报错时追踪
        context_str = f"calib_shape: {calib_shape}, keys(radius/end_radius): {keys}"

        # 检查预处理后的角度与曲率序列是否包含 NaN / inf
        if not np.all(np.isfinite(ang_filter)):
            raise ValueError(f"[{context_str}] ang_filter 包含 NaN 或 inf。请检查 _Strain_2_Cur 的输出。")
        if not np.all(np.isfinite(cur_kal)):
            raise ValueError(f"[{context_str}] cur_kal 包含 NaN 或 inf。请检查 _Strain_2_Cur 的输出。")

        # 使用 try-except 捕获插值过程中的报错并追加上下文信息
        try:
            if self.curvature_interp in {'vector_linear', 'vector_pchip'}:
                if force_ideal_magnitude:
                    curvature_samples = self._construct_ideal_magnitude_for_recon(
                        keys=keys,
                        calib_shape=calib_shape,
                        sample_dist=self.ad_samp_dist,
                    )
                else:
                    curvature_samples = cur_kal
                cur_interp, ang_interp, interp_dist = self._interpolate_curvature_vector(
                    magnitude=curvature_samples,
                    angle=angle_unwrap,
                    method=self._vector_curvature_method(self.curvature_interp),
                )
            else:
                # Preserve the historical scalar path: angle Hermite plus an
                # independently interpolated scalar curvature magnitude.
                ang_interp, interp_dist = self._KT_Hermit_interp_tang(data=ang_filter)

                if force_ideal_magnitude:
                    cur_interp = self._construct_ideal_magnitude_for_recon(keys=keys, calib_shape=calib_shape, sample_dist=interp_dist)
                else:
                    if not np.all(np.isfinite(cur_kal)):
                        raise ValueError(f"[{context_str}] cur_kal 包含 NaN 或 inf。请检查 _Strain_2_Cur 的输出。")

                    cur_interp, interp_dist = self._interpolate_curvature(
                        data=cur_kal,
                        method=self.curvature_interp,
                        nonnegative=self.nonnegative_curvature,
                    )

            if not np.all(np.isfinite(cur_interp)):
                raise ValueError(f"[{context_str}] cur_interp 包含 NaN 或 inf。")

            self.cur_interp = cur_interp

        except ValueError as e:
            raise ValueError(f"数据追踪信息 -> {context_str} | 原始报错: {e}")
        interp_ss = np.diff(interp_dist)

        # Frenet-Serret 路径仍以首点曲率方向作为初始主法向。
        init_N = np.array([0, np.cos(ang_interp[0]), np.sin(ang_interp[0])])

        if verbose:
            print(f"interp_dist: {interp_dist}")
            print(f"ang_interp: {ang_interp}")
            print(f"cur_interp: {cur_interp}")
            print(f"init_N: {init_N}")

        intermediates = {
            'magnitude': magnitude_raw.copy(),
            'angle': angle_raw.copy(),
            'cur_kal': cur_kal.copy(),
            'ang_filter': ang_filter.copy(),
            'cur_interp': cur_interp.copy(),
            'ang_interp': ang_interp.copy(),
        }

        if self.frame_rule == 'TNB':
            # Frenet-Serret重构
            ang_diff = np.diff(ang_interp)
            torsion = (ang_diff - 2 * np.pi * np.floor((ang_diff + np.pi) / (2 * np.pi))) / interp_ss
            if verbose:
                print(f"torsion: {torsion}")
            r, T, N, B = self._F_S_frame(kappa=cur_interp, tau=torsion, ss=interp_ss, init_T=init_T, init_N=init_N)  
            return angle, angle_unwrap, cur_interp, interp_dist, r, T, N, B, intermediates
        elif self.frame_rule == 'TNN':
            # 平行标架重构
            r, T, Y, Z, _, _ = self._parallel_frame(
                kappa=cur_interp,
                angles=ang_interp,
                ss=interp_ss,
                init_T=init_T,
                init_N=init_N,
                return_principal_frame=True,
            )
            return angle, angle_unwrap, cur_interp, interp_dist, r, T, Y, Z, intermediates

    def _construct_ideal_magnitude_for_recon(self, keys, calib_shape, sample_dist):
        """
        为 slopes 优化阶段构造强制使用的理论曲率 magnitude。

        注意：
        - 输入 sample_dist 单位为 m；
        - keys 中的 radius / idx 通常来自 radii 配置，单位为 mm；
        - 输出曲率单位为 1/m；
        - 本函数只在 force_ideal_magnitude=True 时使用。
        """

        sample_dist = np.asarray(sample_dist, dtype=float)

        if sample_dist.ndim != 1:
            raise ValueError(f"sample_dist 应为一维数组，当前 shape={sample_dist.shape}")

        if keys is None or len(keys) == 0:
            raise ValueError(
                f"force_ideal_magnitude=True 时需要 keys 提供理论形状参数，"
                f"但当前 keys={keys}, calib_shape={calib_shape}"
            )

        # 使用相对弧长，避免裁剪后 sample_dist 不从 0 开始造成错位
        s = sample_dist - sample_dist[0]

        radius_mm = float(keys[0])

        def kappa_from_radius_mm(r_mm):
            r_mm = float(r_mm)
            if np.isclose(r_mm, 0.0):
                return 0.0
            return 1000.0 / r_mm

        # circ / end3：整段都是同一理论曲率
        if calib_shape in ["circ", "end3"]:
            kappa = kappa_from_radius_mm(radius_mm)
            return np.full(shape=len(sample_dist), fill_value=kappa, dtype=float)

        # end：前段使用主半径，末端 end_len 使用第二半径
        if calib_shape == "end":
            if len(keys) < 2:
                raise ValueError(f"end 形状需要 keys=[radius, radius_end]，当前 keys={keys}")

            radius_end_mm = float(keys[1])

            kappa_main = kappa_from_radius_mm(radius_mm)
            kappa_end = kappa_from_radius_mm(radius_end_mm)

            samp_dist = np.asarray(self.samp_dist, dtype=float)
            effective_len = float(samp_dist[-1] - samp_dist[0])
            split_pos = max(0.0, effective_len - float(self.end_len))

            return np.where(s <= split_pos, kappa_main, kappa_end).astype(float)

        # rot0：前后直线为 0，中间圆弧段为 1000 / radius
        if calib_shape == "rot0":
            if len(keys) < 2:
                raise ValueError(f"rot0 形状需要 keys=[radius, rot_pos]，当前 keys={keys}")

            radius_m = radius_mm * 0.001
            rot_pos_m = float(keys[1]) * 0.001

            if np.isclose(radius_m, 0.0):
                return np.zeros(len(sample_dist), dtype=float)

            kappa = kappa_from_radius_mm(radius_mm)
            rot_start = rot_pos_m
            rot_end = rot_pos_m + 2.0 * np.pi * radius_m

            return np.where((s >= rot_start) & (s <= rot_end), kappa, 0.0).astype(float)

        # S：前 0.1 m 直线为 0，后面两个半圆弧 magnitude 都是 1000 / radius
        if calib_shape == "S":
            radius_m = radius_mm * 0.001

            if np.isclose(radius_m, 0.0):
                return np.zeros(len(sample_dist), dtype=float)

            kappa = kappa_from_radius_mm(radius_mm)

            straight_len = 0.1
            arc_start = straight_len
            arc_end = straight_len + 2.0 * np.pi * radius_m

            return np.where((s >= arc_start) & (s <= arc_end), kappa, 0.0).astype(float)

        raise ValueError(f"force_ideal_magnitude 暂不支持 calib_shape={calib_shape}") 

    def _framewise_unwrap_limit(self, angle, angle_prev=None, angle_unwrap_prev=None, unwrap_threshold=0.65):
        """
        在逐帧动态重构中限制 angle unwrap 的相位分支跳变。

        该方法与 diagnostics 中 make_framewise_unwrap_processor 的核心逻辑等价，
        用于避免相邻帧之间由于 np.unwrap 自动选择不同 2π 分支而导致角度序列突然跳变。

        参数：
        - angle: 当前帧原始曲率方向角序列，单位 rad，通常范围在 [-π, π]。
        - angle_prev: 上一帧原始曲率方向角序列。
        - angle_unwrap_prev: 上一帧 unwrap 后的曲率方向角序列。
        - unwrap_threshold: 判断当前帧与上一帧相邻段 raw step 是否足够接近的阈值。

        处理流程：
        1. 先对当前帧 angle 调用 np.unwrap(angle, discont=self.discont) 得到 angle_unwrap。
        2. 若没有上一帧信息，直接返回 angle_unwrap。
        3. 从第 1 个点开始逐点检查相邻段 step = angle[i] - angle[i-1]。
        4. 若当前帧和上一帧对应相邻段的 raw step 差异小于 unwrap_threshold，
        则不直接接受 np.unwrap 的结果，而是在 step-2π、step、step+2π 中选择
        最接近上一帧 unwrap step 的分支。
        5. 若当前点发生分支修正，将 offset 累积并传递给后续点。
        6. 若当前序列长于上一帧序列，则对剩余点继续叠加最终 offset。

        输出：
        - angle_unwrap: 修正后的当前帧连续角度序列。

        说明：
        - 该方法主要用于动态序列，不是静态初始化所必需。
        - 它同时考虑当前帧内部连续性和相邻帧之间的连续性。
        """
        angle_unwrap = np.unwrap(angle, discont=self.discont)
        if angle_prev is None or angle_unwrap_prev is None:
            return angle_unwrap

        offset = 0.0

        for i in range(1, len(angle_prev)):
            angle_unwrap[i] += offset

            step = angle[i] - angle[i - 1]
            step_prev = angle_prev[i] - angle_prev[i - 1]

            segment_step_diff = np.abs((step - step_prev + np.pi) % (2 * np.pi) - np.pi)

            if np.isclose(segment_step_diff, 0.0, atol=unwrap_threshold, rtol=0.0):
                unwrap_val = angle_unwrap[i]
                unwrap_step_prev = angle_unwrap_prev[i] - angle_unwrap_prev[i - 1]

                candidate_steps = np.array([step - 2 * np.pi, step, step + 2 * np.pi], dtype=np.float64)
                chosen_step = candidate_steps[np.argmin(np.abs(candidate_steps - unwrap_step_prev))]

                angle_unwrap[i] = angle_unwrap[i - 1] + chosen_step

                step_offset = angle_unwrap[i] - unwrap_val
                offset += step_offset

        if offset != 0.0 and len(angle_prev) < len(angle_unwrap):
            angle_unwrap[len(angle_prev):] += offset

        return angle_unwrap

    def _Strain_2_Cur(self, keys, calib_shape, calib_Data, weight, slope, magnitude_ratio=1.0, verbose=False):
        """
        将一组应变数据转换为最终用于三维重构的曲率大小与方向角。

        该方法包含两次曲率计算：
        1. 使用基础扭转系数 base_slopes 计算基础 magnitude / angle，用于曲率分级；
        2. 根据曲率等级选择或混合 weight / slope 后，再重新计算最终 magnitude / angle。

        参数：
        - keys: 当前数据在 calib_Data 中的路径。
        * None: 直接使用 calib_Data.T；
        * [key1]&#58; 使用 calib_Data[key1].T，常见于 circ/S；
        * [key1, key2]&#58; 使用 calib_Data[key1][key2].T，常见于 end/end3/rot0/up/down。
        - calib_shape: 当前标定形状类型。
        - calib_Data: 当前 direct 下的标定数据字典。
        - weight: 当前 direct 下的曲率等级权重。
        - slope: 当前 direct 下的曲率等级和分段扭转系数。
        - magnitude_ratio: 用于曲率分级前修正 magnitude 的比例因子。
        - verbose: 是否打印分数、质量分配、最终权重、最终分段和最终角度等中间结果。

        处理流程：
        1. 取 slope[0] 作为基础分段扭转系数 base_slopes。
        2. 调用 _get_base() 得到：
        - strain_data；
        - 基础 magnitude；
        - 基础 angle；
        - turn_segments。
        3. 用 score_magnitude = magnitude * magnitude_ratio 作为曲率分级依据。
        4. 根据 self.soft 进行曲率等级分配：
        - soft=False: 根据 thresholds 和 min_consecutive 生成硬分级 hard_level_idx；
        - soft=True: 调用 _get_scores() 和 _alloc_mass() 生成软分配 masses。
        5. 根据 masses 与 weight 计算每个采样点的 final_weight。
        若 end_weights=True，则 end_mask 区域使用对应等级的末端权重。
        6. 用 final_weight 对 strain_data 加权，得到 weighted_strain。
        7. 构造每个等级、每个采样点对应的 slope_vecs：
        - calib_shape == 'S' 时，根据 turn_segments 区分普通段和转折段；
        - 其他形状直接按 base_segments 分配 slope。
        8. 使用 masses 对 slope_vecs 加权求和，得到逐点 slope_map。
        9. 调用 _generate_dynamic_segments() 将逐点 slope_map 压缩为动态分段和分段 slope。
        10. 调用 _calculate_dynamic_angles(mode='recon') 得到最终动态通道角度。
        11. 用 weighted_strain 和 final_theta_dynamic 重新计算最终 magnitude / angle。

        输出：
        - magnitude: 最终曲率大小数组。
        - angle: 最终曲率方向角数组，单位 rad。

        说明：
        - 曲率分级影响两个东西：应变权重 final_weight 和扭转系数 slope_map。
        - soft=True 时，不同等级之间可以平滑混合；soft=False 时，每个采样点只属于一个等级。
        - calib_shape == 'S' 时，slope 通常被解释为两套分段系数：
        前 num_segments 个用于普通段，后 num_segments 个用于转折段。
        """
        # ---------- 初始准备 ----------
        base_slopes = slope[0]

        # ---------- 使用基础扭转系数计算曲率 ----------
        strain_data, magnitude, angle, turn_segments = self._get_base(keys=keys, calib_Data=calib_Data, base_slopes=base_slopes, verbose=False)

        # ---------- 进行曲率分级和分级参数计算 ----------
        score_magnitude = magnitude * magnitude_ratio
        if not self.soft:
            scores = None
            hard_level_idx = np.zeros(self.total_points, dtype=int)
            hard_regions = [None] * self.num_levels
            min_consecutive = max(1, int(self.min_consecutive))

            for level, threshold in enumerate(self.thresholds, start=1):
                consecutive_count = 0
                region_start = None
                region_indices = None

                for i, mag in enumerate(score_magnitude):
                    if mag > threshold:
                        if consecutive_count == 0:
                            region_start = i
                        consecutive_count += 1
                    else:
                        if consecutive_count >= min_consecutive:
                            region_indices = np.arange(region_start, i)
                            break
                        consecutive_count = 0
                        region_start = None

                if region_indices is None and consecutive_count >= min_consecutive:
                    region_indices = np.arange(region_start, self.total_points)

                if region_indices is not None and len(region_indices) > 0:
                    hard_level_idx[region_indices] = level
                    hard_regions[level] = region_indices

            masses = np.zeros((self.num_levels, self.total_points))
            masses[hard_level_idx, np.arange(self.total_points)] = 1.0
        else:
            scores = self._get_scores(magnitude=score_magnitude)
            masses = self._alloc_mass(scores=scores)
        if verbose:
            if scores is not None:
                print(f"scores: {scores}")
            else:
                print(f"hard level index: {hard_level_idx}")
                print(f"hard regions: {hard_regions}")
            for i in range(self.num_levels-1):
                print(f"Probability mass for curvature class {i+1}: {masses[i]}")

        # ---------- 计算加权后的应变 ----------
        weight_vecs = np.array([np.where(self.end_mask, weight[i+self.num_levels] if self.end_weights else weight[i], weight[i]) for i in range(self.num_levels)]) 
        final_weight = np.sum(masses * weight_vecs, axis=0)
        weighted_strain = strain_data * final_weight
        if verbose:
            print(f"final weight: {final_weight}")
            print(f"weighted strain: {weighted_strain}")

        # ---------- 重新分段并分配扭转系数 ----------
        slope_vecs = np.zeros((self.num_levels, self.total_points))
        if calib_shape == 'S':
            turn_masks = np.zeros(self.total_points, dtype=bool)
            for k, (t_start, t_end) in enumerate(turn_segments):
                if k % 2 != 0:
                    turn_masks[t_start:t_end] = True
            for i in range(self.num_levels):
                for j, (start, end) in enumerate(self.base_segments):
                    turn_mask = turn_masks[start:end]
                    slope_vecs[i, start:end] = np.where(turn_mask, slope[i, j + self.num_segments], slope[i, j])
        else:
            for i in range(self.num_levels):
                for j, (start, end) in enumerate(self.base_segments):
                        slope_vecs[i, start:end] = slope[i, j]
                    
        slope_map = np.sum(masses * slope_vecs, axis=0)
        final_segments, final_slope = self._generate_dynamic_segments(slope_map=slope_map)
        if verbose:
            print(f"final segments: {final_segments}")
            print(f"final slopes: {final_slope}")
            
        # ---------- 使用处理过的新应变、分段与扭转系数计算最终结果 ----------
        final_theta_dynamic = self._calculate_dynamic_angles(mode='recon', segments=final_segments, seg_slopes=final_slope)
        magnitude, angle = self._calculate_curvature_and_angle(epsilon=weighted_strain, alpha_dynamic=final_theta_dynamic)
        if verbose:
            print(f"final_theta_dynamic: {final_theta_dynamic}")
            print(f"magnitude: {magnitude}")
            print(f"angle: {angle}")
            print()

        return magnitude, angle
    
    def _get_base(self, keys, calib_Data, base_slopes, verbose=False):
        """
        使用基础扭转系数计算一组数据的基础曲率大小、方向角和转折分段。

        参数：
        - keys: 当前数据路径。
        * None: 直接使用 calib_Data.T；
        * [radius]&#58; 使用 calib_Data[radius].T；
        * [radius, idx]&#58; 使用 calib_Data[radius][idx].T。
        - calib_Data: 当前 direct 下的标定数据字典。
        - base_slopes: 基础分段扭转系数，通常为 slope[0]。
        - verbose: 是否打印 strain_data、theta_dynamic、基础 magnitude 和基础 angle。

        处理流程：
        1. 使用 self.base_segments 和 base_slopes 调用 _calculate_dynamic_angles(mode='recon')，
        得到基础动态通道角度 theta_dynamic。
        2. 根据 keys 从 calib_Data 中提取当前组应变数据，并转置为
        (num_channels_recon, num_points)。
        3. 调用 _calculate_curvature_and_angle() 得到基础 magnitude 与 angle。
        4. 对 angle 做 np.unwrap(angle, discont=self.discont)。
        5. 根据 unwrap 后相邻点角度差是否超过 self.turn_threshold 识别转折点。
        6. 根据转折点生成 turn_segments，覆盖 [0, self.total_points)。

        输出：
        - strain_data: 当前组应变矩阵，形状通常为 (num_channels_recon, total_points)。
        - magnitude: 基础曲率大小数组。
        - angle: 基础曲率方向角数组。
        - turn_segments: 根据角度突变检测得到的分段区间列表。

        说明：
        - magnitude 和 angle 主要用于后续曲率分级，不一定是最终用于重构的曲率。
        - turn_segments 主要服务于 S 形数据中普通段与转折段的 slope 选择。
        """
        theta_dynamic = self._calculate_dynamic_angles(mode='recon', segments=self.base_segments, seg_slopes=base_slopes)
        if keys is None:
            strain_data = calib_Data.T
        elif len(keys) == 1:
            radius = keys[0]
            strain_data = calib_Data[radius].T
        elif len(keys) == 2:
            radius, idx = keys
            strain_data = calib_Data[radius][idx].T
        magnitude, angle = self._calculate_curvature_and_angle(epsilon=strain_data, alpha_dynamic=theta_dynamic)
        angle_unwrap = np.unwrap(angle, discont=self.discont)
        turn_idx = [0]
        for i in range(1, len(angle)):
            if np.abs(angle_unwrap[i] - angle_unwrap[i-1]) > self.turn_threshold:
                turn_idx.append(i)
        turn_segments = [(turn_idx[i], turn_idx[i+1]) for i in range(len(turn_idx) - 1)]
        turn_segments.append((turn_idx[-1], self.total_points))
        if verbose:
            print(f"---------- radius: {'dynamic' if not keys else keys} ----------")
            print(f"strain_data: {strain_data}")
            print(f"theta_dynamic: {theta_dynamic}")
            print(f"magnitude(base): {magnitude}")
            print(f"angle(base): {angle}")
        return strain_data, magnitude, angle, turn_segments

    def _alloc_mass(self, scores):
        """
        根据各曲率等级分数分配概率质量。

        说明：
        - 从高等级到低等级逐层扣减，每一层从剩余质量 remained 中分配 score 比例的质量，最终最低等级使用剩余的全部质量。
        - 返回结果各层质量之和在每个点上应接近 1，并最终裁剪到 [0, 1]。

        输入：
        - scores: 各曲率等级的分数字段，形状通常为 (num_levels - 1, total_points)

        输出：
        - final_masses: 各等级的概率质量分布，形状为 (num_levels, total_points)
        """
        masses = []
        remained = np.ones(self.total_points)
        for score in scores[::-1]:
            mass = remained * score
            masses.append(mass)
            remained -= mass
        final_masses = np.vstack((remained, np.asarray(masses[::-1])))
        return np.clip(final_masses, 0.0, 1.0)

    def _get_scores(self, magnitude):
        """
        根据曲率大小计算各等级的软分级分数。

        说明：
        - 对每个阈值使用 sigmoid 函数计算超过该阈值的程度。
        - sharpness 控制 sigmoid 的陡峭程度。
        - 若 min_consecutive > 1，则再对每个等级分数做一次移动平均，以增强连续性。

        输入：
        - magnitude: 曲率大小数组

        输出：
        - scores: 各等级对应的分数数组，形状通常为 (num_levels - 1, total_points)
        """
        scores = []
        for i in range(self.num_levels-1):
            level_score = 1.0 / (1.0 + np.exp(-self.sharpness * (np.asarray(magnitude) - self.thresholds[i])))
            if self.min_consecutive > 1:
                level_score = self._moving_average_scipy(data=level_score, window_size=self.min_consecutive, mode='constant')
            scores.append(level_score)
        return np.asarray(scores)
    
    def _generate_dynamic_segments(self, slope_map):
        """
        根据逐点扭转系数映射生成动态分段结构。

        输入：
        - slope_map: 每个采样点处的扭转系数数组

        输出：
        - final_segments: 动态分段区间列表，格式为 [(start, end), ...]
        - final_slope: 每个分段对应的扭转系数列表
        """
        final_segments = []
        final_slope = []
        current_slope = slope_map[0]
        segment_start = 0
        for i in range(1, self.total_points):
            if slope_map[i] != current_slope:
                final_segments.append((segment_start, i))
                final_slope.append(current_slope)
                current_slope = slope_map[i]
                segment_start = i
        final_segments.append((segment_start, self.total_points))
        final_slope.append(current_slope)
        return final_segments, final_slope
    
    def _moving_average_scipy(self, data, window_size, mode):
        """
        使用 scipy.ndimage.uniform_filter1d 实现一维移动平均滤波。

        输入：
        - data: 输入的一维数组
        - window_size: 移动平均窗口大小
        - mode: 边界处理方式，如 'reflect'、'constant'、'nearest'、'mirror'、'wrap'

        输出：
        - output: 滤波后的数组
        """
        if window_size < 1:
            raise ValueError("Window size must be a positive integer.")
        if window_size > len(data):
            raise ValueError("Window size cannot be larger than the data length.")
            
        output = uniform_filter1d(data, size=window_size, mode=mode, cval=0.0, origin=0)
        return output

    def _KT_Hermit_interp_tang(self, data):
        """
        根据 self.ad_samp_dist 使用 CubicHermiteSpline对一维数据进行 Hermite 插值。

        输入：
        - data: 原始一维数据数组，其长度必须与 self.ad_samp_dist 一致

        输出：
        - interp_data: 插值后的数据数组
        - interp_samp_dist: 插值后的均匀采样距离数组
        """
        # 确保 samp_dist 是 NumPy 数组
        samp_dist = np.array(self.ad_samp_dist, dtype=float)

        # 检查数据有效性
        if not np.all(np.isfinite(samp_dist)):
            raise ValueError("samp_dist 包含非有限值（NaN 或 inf）")
        if not np.all(np.diff(samp_dist) > 0):
            raise ValueError("samp_dist 必须是递增的数组")

        # 创建插值后的样本点（根据更新后的 samp_dist 范围生成）
        interp_samp_dist = np.linspace(samp_dist.min(), samp_dist.max(), num=self.interp_num)

        data = np.array(data)
        # 检查数据和 samp_dist 的形状是否一致
        if data.shape[0] != len(samp_dist):
            raise ValueError(f"数据的长度与 samp_dist 的长度不一致")
        
        # 检查数据是否包含非有限值
        if not np.all(np.isfinite(data)):
            raise ValueError(f"数据包含非有限值（NaN 或 inf）")

        # 计算导数（数值梯度）
        try:
            dy = np.gradient(data, samp_dist, axis=0)
        except ValueError as e:
            raise ValueError(f"梯度计算失败：{e}")
        
        # 检查梯度是否包含非有限值
        if not np.all(np.isfinite(dy)):
            raise ValueError(f"梯度计算结果包含非有限值（NaN 或 inf）")

        # # 强制设置 x=0 处的导数为 0（确保在原点处与 x 轴相切）
        # dy[0] = 0

        # 创建 Hermite 插值对象并插值
        interp_data = []
        hermite_spline = CubicHermiteSpline(samp_dist, data, dy)
        # 通过均匀的 interp_samp_dist 进行重采样
        interp_data = hermite_spline(interp_samp_dist)
        
        return interp_data, interp_samp_dist

    def _interpolate_curvature(self, data, method=None, nonnegative=None):
        """按选定策略对曲率进行空间插值。

        ``hermite`` 保留历史实现；``pchip`` 使用单调保形插值，避免在
        相邻采样点之间因三次 Hermite 斜率而产生额外过冲。非负约束只在
        曲率插值结果上执行，不改变方向角，因此可单独比较插值与约束的影响。
        """
        method = self.curvature_interp if method is None else method
        nonnegative = self.nonnegative_curvature if nonnegative is None else bool(nonnegative)
        if method == 'hermite':
            interp_data, interp_samp_dist = self._KT_Hermit_interp_tang(data)
        elif method in {'pchip', 'scalar_pchip'}:
            samp_dist = np.asarray(self.ad_samp_dist, dtype=float)
            data = np.asarray(data, dtype=float)
            if samp_dist.ndim != 1 or data.ndim != 1 or data.shape[0] != samp_dist.size:
                raise ValueError("曲率数据与采样距离必须是一维且长度一致")
            if samp_dist.size < 2 or not np.all(np.isfinite(samp_dist)) or not np.all(np.diff(samp_dist) > 0):
                raise ValueError("samp_dist 必须包含至少两个严格递增的有限值")
            if not np.all(np.isfinite(data)):
                raise ValueError("曲率数据包含 NaN 或 inf")
            interp_samp_dist = np.linspace(samp_dist[0], samp_dist[-1], num=self.interp_num)
            interp_data = PchipInterpolator(samp_dist, data)(interp_samp_dist)
        else:
            raise ValueError("scalar curvature interpolation method must be 'hermite' or 'scalar_pchip'")

        if nonnegative:
            interp_data = np.maximum(np.asarray(interp_data, dtype=float), 0.0)
        return np.asarray(interp_data, dtype=float), np.asarray(interp_samp_dist, dtype=float)

    def _interpolate_curvature_vector(self, magnitude, angle, method):
        """Filter and interpolate the two circularly invariant curvature components."""
        samp_dist = np.asarray(self.ad_samp_dist, dtype=float)
        magnitude = np.asarray(magnitude, dtype=float)
        angle = np.asarray(angle, dtype=float)
        if magnitude.ndim != 1 or angle.ndim != 1 or magnitude.shape != angle.shape:
            raise ValueError("magnitude and angle must be one-dimensional arrays with equal length")
        if magnitude.size != samp_dist.size:
            raise ValueError("curvature-vector samples must match ad_samp_dist")
        if (
            samp_dist.size < 2
            or not np.all(np.isfinite(samp_dist))
            or not np.all(np.diff(samp_dist) > 0.0)
            or not np.all(np.isfinite(magnitude))
            or not np.all(np.isfinite(angle))
        ):
            raise ValueError("curvature-vector interpolation inputs must be finite and ordered")
        if method not in {'linear', 'pchip'}:
            raise ValueError("curvature-vector interpolation method must be 'linear' or 'pchip'")

        components = np.column_stack(
            (magnitude * np.cos(angle), magnitude * np.sin(angle))
        )
        filtered = np.column_stack(
            [
                self._moving_average_scipy(
                    data=components[:, component],
                    window_size=self.move_filter,
                    mode='reflect',
                )
                for component in range(2)
            ]
        )
        interp_dist = np.linspace(samp_dist[0], samp_dist[-1], num=self.interp_num)
        if method == 'linear':
            interpolated = np.column_stack(
                [np.interp(interp_dist, samp_dist, filtered[:, component]) for component in range(2)]
            )
        else:
            interpolated = PchipInterpolator(samp_dist, filtered, axis=0)(interp_dist)

        cur_interp = np.hypot(interpolated[:, 0], interpolated[:, 1])
        ang_interp = np.arctan2(interpolated[:, 1], interpolated[:, 0])
        return cur_interp, ang_interp, interp_dist
    
    def _Kalman_filter(self, data, Rk, Bk):
        """
        对一维数据执行简化 Kalman 滤波。

        输入：
        - data: 输入的一维数组
        - Rk: 观测噪声参数，越小则输出越贴近原始观测值。
        - Bk: 状态转移误差参数，越大对新观测的响应通常更快。

        输出：
        - output: 滤波后的数组
        """
        data = np.asarray(data)
        kalman_num = data.shape[0]
        data_last = data[0]
        pk_last = Bk
        output = np.zeros_like(data)
        for kal in range(kalman_num):
            xk_bar = data_last
            pk_bar = pk_last + Bk
            Kgain = pk_bar/(pk_bar+Rk)

            output[kal] = xk_bar+Kgain*(data[kal]-xk_bar)
            pk_last = pk_bar - Kgain*pk_bar

            data_last = output[kal]
        return output
    
    def _F_S_frame(self, kappa, tau, ss, init_T, init_N):
        """
        使用 Frenet-Serret 标架公式递推计算三维曲线及 T/N/B 标架。

        说明：
        - 当某点曲率小于 self.TNB_threshold 时，认为局部形状变化过小，直接沿用上一点的 T/N/B。
        - 当前实现的返回顺序为 (r, N, T, B)。

        输入：
        - kappa: 曲率数组，形状为 (num_points,)
        - tau: 扭率数组，形状通常为 (num_points - 1,) 或插入后与步长对齐
        - ss: 相邻点之间的弧长间隔数组
        - init_T: 初始切向量
        - init_N: 初始法向量

        输出：
        - r: 三维曲线位置数组，形状为 (num_points, 3)
        - N: 法向量数组，形状为 (num_points, 3)
        - T: 切向量数组，形状为 (num_points, 3)
        - B: 副法向量数组，形状为 (num_points, 3)
        """
        cal_norm = lambda v: v / np.linalg.norm(v)
        
        num_points = len(ss) + 1  #range函数会不包括这个值
        
        # 初始化 T, N, B, r
        r = np.zeros((num_points, 3))  # 三维位置向量
        T = np.zeros((num_points, 3))  # 切向量
        N = np.zeros((num_points, 3))  # 法向量
        B = np.zeros((num_points, 3))  # 副法向量
        
        # 起点的初始值
        T[0] = init_T
        N[0] = init_N
        B[0] = np.cross(init_T, init_N)

        # 在开头插入 0，保证各数组的长度相同
        ss = np.insert(ss, 0, 0)
        tau = np.insert(tau, 0, 0)
        
        # 迭代计算
        for i in range(1, num_points):
            if kappa[i] < self.TNB_threshold:
                N[i] = N[i-1]
                B[i] = B[i-1]
                T[i] = T[i-1]
            else:
                # 计算 N(i)
                numerator = ss[i] * tau[i] * B[i-1] - ss[i] * kappa[i] * T[i-1] + N[i-1]
                denominator = 1 + ss[i]**2 * tau[i]**2 + ss[i]**2 * kappa[i]**2
                N[i] = numerator / denominator
                N[i] = cal_norm(np.array(N[i]))
                
                # 计算 T(i)
                T[i] = ss[i] * kappa[i] * N[i] + T[i-1]
                T[i] = cal_norm(np.array(T[i]))

                # 计算 B(i)
                B[i] = -ss[i] * tau[i] * N[i] + B[i-1]
                B[i] = cal_norm(np.array(B[i]))

            # 计算 r(i)
            r[i] = ss[i] * T[i] + r[i-1]
        
        return r, T, N, B
    
    def _parallel_frame(self, kappa, angles, ss, init_T, init_N, return_principal_frame=False):
        """
        With ``return_principal_frame=False`` (default), return
        ``(r, T, N1, N2)`` for backward compatibility. When enabled, return
        ``(r, T, Y, Z, N1, N2)``, where Y and Z are the fiber-local y/z axes
        expressed in the global coordinate system.

        使用平行标架 / TNN 形式递推计算三维曲线及 T/N1/N2 标架。

        说明：
        - 根据 angles 相对于首点角度的变化，将曲率分解为 kappa1 与 kappa2。
        - N1 由 init_N 初始化，N2 由 np.cross(init_T, init_N) 初始化。
        - 当前实现不使用扭率 tau，也不使用 self.TNB_threshold。
        - 当前实现的返回顺序为 (r, T, N1, N2)。

        输入：
        - kappa: 曲率大小数组，形状为 (num_points,)
        - angles: 曲率方向角数组，形状为 (num_points,)
        - ss: 相邻插值点之间的弧长间隔数组，形状为 (num_points - 1,)
        - init_T: 初始切向量
        - init_N: 初始 N1 方向

        输出：
        - r: 三维曲线位置数组，形状为 (num_points, 3)
        - T: 切向量数组，形状为 (num_points, 3)
        - N1: 第一法向基数组，形状为 (num_points, 3)
        - N2: 第二法向基数组，形状为 (num_points, 3)
        """
        # Define normlize func
        cal_norm = lambda v: v / np.linalg.norm(v)
        
        num_points = len(ss) + 1  #range函数会不包括这个值
        
        # 初始化 T, N, B, r
        r = np.zeros((num_points, 3))  # 三维位置向量
        T = np.zeros((num_points, 3))  # 切向量
        N1 = np.zeros((num_points, 3))  # 法向量
        N2 = np.zeros((num_points, 3))  # 副法向量
        
        # 起点的初始值
        T[0] = init_T
        N1[0] = init_N
        N2[0] = np.cross(init_T, init_N) # 也可以反过来init_N\times init_T

        # 首个测点的 Fiber A 方向定义为局部零度；从局部 +Y
        # 向 +Z 为正方向。所以曲率分量使用相对首点的角度。
        angles_rel = angles - angles[0]
        kappa1 = kappa * np.cos(angles_rel)
        kappa2 = kappa * np.sin(angles_rel)

        # 在开头插入 0，保证各数组的长度相同
        ss = np.insert(ss, 0, 0)

        # 迭代计算
        for i in range(1, num_points):
            numerator = T[i - 1] + ss[i] * (kappa1[i] * N1[i - 1] + kappa2[i] * N2[i - 1])
            denominator = 1.0 + ss[i]**2 * (kappa1[i]**2 + kappa2[i]**2)
            T[i] = numerator / denominator
            T[i] = cal_norm(np.array(T[i]))

            N1[i] = N1[i - 1] - ss[i] * kappa1[i] * T[i]
            N1[i] = cal_norm(N1[i])

            N2[i] = N2[i - 1] - ss[i] * kappa2[i] * T[i]
            N2[i] = cal_norm(N2[i])

            r[i] = ss[i] * T[i] + r[i-1]

        if not return_principal_frame:
            return r, T, N1, N2

        # N1/N2 的初始方向相对全局 Y/Z 轴旋转了 angles[0]。
        # 将该固定初始旋转取消，得到光纤局部 y 轴在全局
        # 坐标系中的方向；再用 T x Y 得到右手系的局部 z 轴。
        initial_angle = angles[0]
        Y = np.cos(initial_angle) * N1 - np.sin(initial_angle) * N2
        Y = Y - np.sum(Y * T, axis=1, keepdims=True) * T
        Y_norm = np.linalg.norm(Y, axis=1, keepdims=True)
        eps = np.finfo(float).eps
        if np.any(Y_norm <= eps):
            raise ValueError("TNN local y axis is numerically degenerate")
        Y = Y / Y_norm

        Z = np.cross(T, Y)
        Z_norm = np.linalg.norm(Z, axis=1, keepdims=True)
        if np.any(Z_norm <= eps):
            raise ValueError("TNN local z axis is numerically degenerate")
        Z = Z / Z_norm

        return r, T, Y, Z, N1, N2

    @staticmethod
    def _build_end_pose(T, N, B, rot_matrix):
        """Return terminal T/N/B rows in the rotated curve coordinates."""
        T = np.asarray(T, dtype=float)
        N = np.asarray(N, dtype=float)
        B = np.asarray(B, dtype=float)
        rot_matrix = np.asarray(rot_matrix, dtype=float)

        if T.ndim != 2 or N.ndim != 2 or B.ndim != 2:
            raise ValueError("T, N and B must be two-dimensional frame arrays")
        if T.shape[1] != 3 or N.shape[1] != 3 or B.shape[1] != 3:
            raise ValueError("T, N and B must have shape (num_points, 3)")
        if not (len(T) == len(N) == len(B)):
            raise ValueError("T, N and B must contain the same number of points")
        if rot_matrix.shape != (3, 3):
            raise ValueError("rot_matrix must have shape (3, 3)")
        if len(T) == 0:
            return None

        return np.stack(
            (
                T[-1] @ rot_matrix.T,
                N[-1] @ rot_matrix.T,
                B[-1] @ rot_matrix.T,
            )
        )

    def _get_rot_x(self, direct, rot_dir=-1):
        """
        生成绕 x 轴旋转的旋转矩阵。

        输入：
        - direct: 当前方向角（度）

        输出：
        - rot_matrix: 3×3 的绕 x 轴旋转矩阵
        """
        correction = self.rot_ang_by_direct.get(direct, self.rot_ang_by_direct.get(str(direct), 0.0))
        sigma = np.deg2rad((direct) * rot_dir + self.rot_ang + correction)
        rot_matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, np.cos(sigma), -np.sin(sigma)],
            [0.0, np.sin(sigma), np.cos(sigma)]
        ])
        return rot_matrix
