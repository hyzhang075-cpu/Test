from copy import deepcopy

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.interpolate import CubicHermiteSpline, PchipInterpolator

from initialiser import Initialiser
from calibration_regions import validate_end_weight_config, validate_weight_group_ids

from tools.utils import dict_recur_paths, dict_recur_unflatten, dict_recur_extract_path

class Reconstructor(Initialiser):
    """
    形状重构模块
    """
    def __init__(self, soft=True, frame_rule='TNB', rot_ang=0.0, turn_threshold=2.0, init_weight=1.0, weights=None, slopes=None, min_consecutive=3, sharpness=4.8, end_start=-6, end_weights=False, thresholds=[0.8, 1.5, 2.0, 3.0, 4.0], 
                 TNB_threshold=0.15, interp_num=120, move_filter=3, kalman_params={'angle': {'Rk': 0.001, 'Bk': 0.001}, 'magnitude': {'Rk': 0.0001, 'Bk': 0.01}},
                 curvature_interp='hermite', nonnegative_curvature=False,
                 *args, move_filter_for_vector=False, multi_region_parameters=None, **kwargs):
        weight_group_ids = kwargs.pop('weight_group_ids', None)
        end5cm_independent_weight_score = kwargs.pop('end5cm_independent_weight_score', None)
        legacy_groupwise = kwargs.pop('end5cm_groupwise_weight_score', False)
        if end5cm_independent_weight_score is None:
            end5cm_independent_weight_score = legacy_groupwise
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
        self.end5cm_independent_weight_score = bool(end5cm_independent_weight_score)
        # Runtime compatibility for older callers; production code reads the canonical name.
        self.end5cm_groupwise_weight_score = self.end5cm_independent_weight_score

        self.num_levels = len(self.thresholds) + 1 
        self.base_segments = self._calculate_segments(total_points=self.total_points)
        self.end_mask = np.arange(self.total_points) >= self.total_points + end_start
        self.end_start = end_start
        self.TNB_threshold = TNB_threshold # FS重构时直接复制上一点的曲率大小阈值

        # 需要优化的应变权重、扭转系数以及旋转角度
        self.end_weights = end_weights # 是否优化末端权重
        self.weight_group_ids = validate_weight_group_ids(weight_group_ids, self.total_points)
        self.init_weight = init_weight
        if not weights:
            if self.weight_group_ids is not None:
                self.weights = {direct: init_weight*np.ones((max(self.weight_group_ids)+1)*self.num_levels)
                                for direct in self.exp_directs}
            else:
                self.weights = {direct: np.ones(2 * self.num_levels) for direct in self.exp_directs} if self.end_weights else {direct: init_weight * np.ones(self.num_levels) for direct in self.exp_directs}
        else:
            self.weights = weights

        if not slopes:
            # 若涉及S形弯优化，则准备两组扭转系数，否则一组
            self.slopes = {direct: np.array([np.concatenate((self.slopes_init[direct], self.slopes_init[direct])) for _ in range(self.num_levels)]) for direct in self.exp_directs} if 'S' in self.calib_shapes else {direct: np.array([self.slopes_init[direct] for _ in range(self.num_levels)]) for direct in self.exp_directs} 
        else:
            self.slopes = slopes
        self.rot_ang = rot_ang 

        # 滤波、插值所需参数
        self.move_filter = move_filter
        self.move_filter_for_vector = bool(move_filter_for_vector)
        self.kalman_params = kalman_params
        self.interp_num = interp_num
        self.curvature_interp = self._normalise_curvature_interp(curvature_interp)
        self.nonnegative_curvature = bool(nonnegative_curvature)
        self.multi_region_parameters = (
            self._normalise_multiregion_parameters(multi_region_parameters)
            if multi_region_parameters is not None else None
        )
        self.last_parameter_assembly = None

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

            _, _, _, interp_dist, r, _, _, _, _ = self._reconstruct_frame(keys=keys, calib_shape=calib_shape, calib_Data=calib_Data, weight=weight, slope=slope, magnitude_ratio=magnitude_ratio, init_T=[1.0, 0.0, 0.0], verbose=verbose, force_ideal_magnitude=force_ideal_magnitude, direct=direct)

            r_postrot = r @ rot_matrix.T
            flat_results[path] = r_postrot

            if verbose:
                print(f"keys: {keys}")
                print(f"r: {r}")
                print()

        # ---------- 还原为原本嵌套结构 ----------
        r_results_postrot = dict_recur_unflatten(flat_results)

        return r_results_postrot, interp_dist

    def _reconstruct_frame(self, keys, calib_shape, calib_Data, weight, slope, magnitude_ratio, init_T, verbose=False, unwrap_threshold=0.65, align_threshold=0.15, angle_prev=None, angle_unwrap_prev=None, force_ideal_magnitude=False, direct=None):
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
        5. 对 angle_unwrap 做空间移动平均，得到 ang_filter；仅标量插值路径使用它，
           向量路径仍计算、校验并保存它，但插值使用 angle_unwrap。
        6. 对 magnitude 做单帧空间 Kalman 滤波，得到 cur_kal；标量路径使用它，
           向量路径仅校验/保存该中间量，不将其用于插值。
        7. 检查滤波后的角度和曲率是否包含 NaN / inf。
        8. 按 self.ad_samp_dist 插值：标量路径对 ang_filter 做 Hermite、对 cur_kal
           按所选标量方法插值；向量路径将补齐虚拟点的 magnitude 与 angle_unwrap 转成两分量，
           根据 move_filter_for_vector 选择用分量空间平均修正方向或保留原始分量，
           恢复输入模长后再做线性/PCHIP 插值，
           最后还原曲率大小和方向。
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
        magnitude, angle = self._Strain_2_Cur(keys=keys, calib_shape=calib_shape, calib_Data=calib_Data, weight=weight, slope=slope, magnitude_ratio=magnitude_ratio, verbose=verbose, direct=direct)
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
        # 此处沿单帧的空间采样点平均，不是跨帧滤波。
        # ang_filter 仅供下方标量路径插值；向量路径只将它作为中间量校验/保存。
        ang_filter = self._moving_average_scipy(data=angle_unwrap, window_size=self.move_filter, mode='reflect')
        # 标量路径使用此空间 Kalman 输出；向量路径保留它用于中间量校验/记录，
        # 实际插值直接使用 magnitude，避免再叠加一层曲率空间滤波。
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
                    curvature_samples = magnitude
                # 使用未做角度窗口平均的 angle_unwrap；是否执行独立的分量方向窗口
                # 由 move_filter_for_vector 控制。force_ideal_magnitude 时输入理想曲率，
                # 绕过 cur_kal 输出。
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

    def _reconstruct_from_interpolated_curvature(
        self, cur_interp, ang_interp, interp_dist, init_T
    ):
        """Build the curve and local frame from the exact interpolated curvature used."""
        cur_interp = np.asarray(cur_interp, dtype=float)
        ang_interp = np.asarray(ang_interp, dtype=float)
        interp_dist = np.asarray(interp_dist, dtype=float)
        init_T = np.asarray(init_T, dtype=float)
        if (
            cur_interp.ndim != 1
            or ang_interp.ndim != 1
            or interp_dist.ndim != 1
            or cur_interp.shape != ang_interp.shape
            or cur_interp.size != interp_dist.size
            or cur_interp.size < 2
            or init_T.shape != (3,)
            or not np.all(np.isfinite(cur_interp))
            or not np.all(np.isfinite(ang_interp))
            or not np.all(np.isfinite(interp_dist))
            or not np.all(np.isfinite(init_T))
            or not np.all(np.diff(interp_dist) > 0.0)
        ):
            raise ValueError("interpolated curvature inputs must be finite, ordered, and shape-compatible")

        interp_ss = np.diff(interp_dist)
        init_N = np.array([0.0, np.cos(ang_interp[0]), np.sin(ang_interp[0])])
        if self.frame_rule == 'TNB':
            ang_diff = np.diff(ang_interp)
            torsion = (ang_diff - 2 * np.pi * np.floor((ang_diff + np.pi) / (2 * np.pi))) / interp_ss
            return self._F_S_frame(
                kappa=cur_interp,
                tau=torsion,
                ss=interp_ss,
                init_T=init_T,
                init_N=init_N,
            )
        if self.frame_rule == 'TNN':
            r, T, Y, Z, _, _ = self._parallel_frame(
                kappa=cur_interp,
                angles=ang_interp,
                ss=interp_ss,
                init_T=init_T,
                init_N=init_N,
                return_principal_frame=True,
            )
            return r, T, Y, Z
        raise ValueError(f"unsupported frame_rule: {self.frame_rule}")

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

    def _Strain_2_Cur(self, keys, calib_shape, calib_Data, weight, slope, magnitude_ratio=1.0, verbose=False, direct=None):
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
        if self.multi_region_parameters is not None:
            if direct is None:
                raise ValueError('multi-region reconstruction requires direct=0/120/240')
            if keys is None:
                strain_data = np.asarray(calib_Data).T
            elif len(keys) == 1:
                strain_data = np.asarray(calib_Data[keys[0]]).T
            elif len(keys) == 2:
                strain_data = np.asarray(calib_Data[keys[0]][keys[1]]).T
            magnitude, angle, _, _, diagnostics = self._assemble_multiregion_parameters(
                strain_data, direct, magnitude_ratio=magnitude_ratio,
            )
            self.last_parameter_assembly = diagnostics
            if verbose:
                print(f'multi-region parameter assembly: {diagnostics}')
            return magnitude, angle

        # ---------- 初始准备 ----------
        base_slopes = slope[0]

        # ---------- 使用基础扭转系数计算曲率 ----------
        strain_data, magnitude, angle, turn_segments = self._get_base(keys=keys, calib_Data=calib_Data, base_slopes=base_slopes, verbose=False)

        # ---------- 进行曲率分级和分级参数计算 ----------
        score_magnitude = magnitude * magnitude_ratio
        groups = getattr(self, 'weight_group_ids', None)
        if not self.soft:
            slope_scores = None
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

            slope_masses = np.zeros((self.num_levels, self.total_points))
            slope_masses[hard_level_idx, np.arange(self.total_points)] = 1.0
            weight_scores = slope_scores
            weight_masses = slope_masses
        else:
            slope_scores = self._get_scores(magnitude=score_magnitude)
            slope_masses = self._alloc_mass(scores=slope_scores)
            weight_scores = slope_scores
            weight_masses = slope_masses
            if getattr(self, 'end5cm_independent_weight_score', False) and groups is not None:
                weight_scores, _ = self._get_groupwise_weight_scores(
                    score_magnitude, groups,
                )
                weight_masses = self._alloc_mass(weight_scores)
        if verbose:
            if slope_scores is not None:
                print(f"slope scores: {slope_scores}")
            else:
                print(f"hard level index: {hard_level_idx}")
                print(f"hard regions: {hard_regions}")
            for i in range(self.num_levels-1):
                print(f"Probability mass for curvature class {i+1}: {slope_masses[i]}")

        # ---------- 计算加权后的应变 ----------
        if groups is not None:
            weight_vecs = np.asarray(weight).reshape(-1, self.num_levels)[np.asarray(groups)].T
        else:
            weight_vecs = np.array([np.where(self.end_mask, weight[i+self.num_levels] if self.end_weights else weight[i], weight[i]) for i in range(self.num_levels)])
        final_weight = np.sum(weight_masses * weight_vecs, axis=0)
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
                    
        slope_map = np.sum(slope_masses * slope_vecs, axis=0)
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
        scores = np.asarray(scores, dtype=float)
        remained = np.ones(scores.shape[1])
        for score in scores[::-1]:
            mass = remained * score
            masses.append(mass)
            remained -= mass
        final_masses = np.vstack((remained, np.asarray(masses[::-1])))
        return np.clip(final_masses, 0.0, 1.0)

    def _get_scores(self, magnitude, *, thresholds=None, sharpness=None,
                    min_consecutive=None, boundary_mode='constant'):
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
        thresholds = self.thresholds if thresholds is None else thresholds
        sharpness = self.sharpness if sharpness is None else sharpness
        min_consecutive = self.min_consecutive if min_consecutive is None else min_consecutive
        scores = []
        for threshold in thresholds:
            level_score = 1.0 / (1.0 + np.exp(-sharpness * (np.asarray(magnitude) - threshold)))
            if min_consecutive > 1:
                level_score = self._moving_average_scipy(
                    data=level_score, window_size=min_consecutive, mode=boundary_mode,
                )
            scores.append(level_score)
        return np.asarray(scores)

    def _normalise_multiregion_parameters(self, config):
        """校验并规范化多区域参数包，建立 0/120/240 方向的 NumPy 参数表。

        每个区域的 support 点用于局部评分，owned 点决定最终写入范围；所有 owned
        点必须无重叠地覆盖完整传感器，防止拼接时出现未赋值或重复赋值。
        """
        config = deepcopy(config)
        meta = config.get('multi_region', config)
        regions = config.get('regions')
        order = list(meta.get('region_order', ()))
        directions = list(meta.get('directions', ()))
        if directions != [0, 120, 240]:
            raise ValueError(f'multi-region direct 必须恰好为 0、120、240；收到 {directions}')
        if not order or not isinstance(regions, dict) or set(order) != set(regions):
            raise ValueError('multi-region region_order 与 regions 不一致')

        sensor_points = [int(point) for point in np.asarray(self.global_point_ids).tolist()]
        owned_all = []
        for name in order:
            block = regions[name]
            thresholds = np.asarray(block.get('thresholds'), dtype=float)
            segmentation = np.asarray(block.get('local_segmentation'), dtype=int)
            support = [int(point) for point in block.get('support_point_ids', ())]
            owned = [int(point) for point in block.get('owned_point_ids', ())]
            segment_ids = [int(segment) for segment in block.get('global_segment_ids', ())]
            if (thresholds.ndim != 1 or np.any(~np.isfinite(thresholds))
                    or np.any(thresholds <= 0) or np.any(np.diff(thresholds) <= 0)):
                raise ValueError(f'{name} thresholds 必须严格递增')
            if (segmentation.ndim != 1 or len(segmentation) != len(segment_ids)
                    or np.any(segmentation <= 0) or int(segmentation.sum()) != len(support)):
                raise ValueError(f'{name} local segmentation/support 不一致')
            if not set(owned).issubset(support) or not set(support).issubset(sensor_points):
                raise ValueError(f'{name} owned/support points 无效')
            levels = len(thresholds) + 1
            enabled, end_start = validate_end_weight_config(
                block.get('end_weights', False), block.get('end_start', -5), len(support))
            groups = validate_weight_group_ids(block.get('weight_group_ids'), len(support))
            expected_weights = levels * (max(groups)+1 if groups is not None else (2 if enabled else 1))
            normalized_weights = {}
            normalized_slopes = {}
            for direct in directions:
                key = str(direct) if str(direct) in block['weights'] else direct
                weights = np.asarray(block['weights'][key], dtype=float)
                slopes = np.asarray(block['slopes'][key], dtype=float)
                if weights.shape != (expected_weights,) or not np.all(np.isfinite(weights)):
                    raise ValueError(f'{direct}/{name} weights shape 应为 {(expected_weights,)}')
                if slopes.shape != (levels, len(segmentation)) or not np.all(np.isfinite(slopes)):
                    raise ValueError(
                        f'{direct}/{name} slopes shape 应为 {(levels, len(segmentation))}'
                    )
                normalized_weights[direct] = weights
                normalized_slopes[direct] = slopes
            block['thresholds'] = thresholds
            block['local_segmentation'] = segmentation
            block['support_point_ids'] = support
            block['owned_point_ids'] = owned
            block['global_segment_ids'] = segment_ids
            block['weights'] = normalized_weights
            block['end_weights'] = enabled
            block['end_start'] = end_start
            block['weight_group_ids'] = groups
            block['slopes'] = normalized_slopes
            block['sharpness'] = float(block.get('sharpness', self.sharpness))
            block['score_window'] = max(1, int(block.get('score_window', self.min_consecutive)))
            block['score_boundary_mode'] = block.get('score_boundary_mode', 'constant')
            block['weight_score_mode'] = block.get('weight_score_mode', 'spatial_window')
            if block['weight_score_mode'] not in ('spatial_window', 'group_mean'):
                raise ValueError(f'{name} weight_score_mode 不合法: {block["weight_score_mode"]!r}')
            if block['weight_score_mode'] == 'group_mean' and groups is None:
                raise ValueError(f'{name} weight_score_mode=group_mean 需要 weight_group_ids')
            owned_all.extend(owned)
        if sorted(owned_all) != sorted(sensor_points) or len(owned_all) != len(set(owned_all)):
            raise ValueError(
                f'multi-region owned points 必须无重叠覆盖全部传感点；收到 {owned_all}'
            )
        return {'region_order': order, 'directions': directions, 'regions': regions,
                'use_full_transported_phase': bool(meta.get('use_full_transported_phase', False)),
                'phase_reference_directions': list(meta.get('phase_reference_directions', directions))}

    @staticmethod
    def _local_segment_labels(segmentation):
        """把局部分段长度展开成逐点的局部分段编号。"""
        return np.repeat(np.arange(len(segmentation)), segmentation.astype(int))

    def _get_groupwise_weight_scores(self, magnitude, group_ids, *, thresholds=None, sharpness=None):
        """Score each independent weight group from its own base-magnitude mean."""
        magnitude = np.asarray(magnitude, dtype=float)
        groups = np.asarray(group_ids, dtype=int)
        if magnitude.ndim != 1 or groups.shape != magnitude.shape:
            raise ValueError('groupwise weight scoring requires one group id per magnitude point')
        if groups.size == 0:
            raise ValueError('groupwise weight scoring requires at least one point')
        thresholds = self.thresholds if thresholds is None else thresholds
        sharpness = self.sharpness if sharpness is None else sharpness
        scores = np.empty((len(thresholds), magnitude.size), dtype=float)
        group_base_magnitude = {}
        for group in sorted(set(groups.tolist())):
            members = groups == group
            mean_magnitude = float(np.mean(magnitude[members]))
            group_base_magnitude[str(int(group))] = mean_magnitude
            group_score = self._get_scores(
                np.asarray([mean_magnitude]), thresholds=thresholds,
                sharpness=sharpness, min_consecutive=1,
            )[:, 0]
            scores[:, members] = group_score[:, None]
        return scores, group_base_magnitude

    def _assemble_multiregion_parameters(self, strain_data, direct, magnitude_ratio=1.0):
        """使用各区域自己的曲率阈值和 sigmoid 配置装配逐点参数。

        先用每个区域第 0 档 slope 形成全长基础相位并估计评分曲率，再在各区域
        support 点计算等级质量；最终只把混合后的 weight 和 slope 写入该区域的
        owned 点。``direct`` 是字面方向角 0、120 或 240。
        """
        config = self.multi_region_parameters
        if config is None:
            raise ValueError('multi_region_parameters 未配置')
        if direct not in config['directions']:
            raise ValueError(f'direct 必须为 0、120、240；收到 {direct}')
        strain_data = np.asarray(strain_data, dtype=float)
        if strain_data.ndim != 2 or strain_data.shape[1] != self.total_points:
            raise ValueError(
                f'strain_data 应为 (channels, {self.total_points})，收到 {strain_data.shape}'
            )
        point_index = {int(point): index for index, point in enumerate(self.global_point_ids)}
        base_slope_map = np.empty(self.total_points, dtype=float)

        for name in config['region_order']:
            block = config['regions'][name]
            support_labels = self._local_segment_labels(block['local_segmentation'])
            support_lookup = {
                point: local_index for local_index, point in enumerate(block['support_point_ids'])
            }
            base_slopes = block['slopes'][direct][0]
            for point in block['owned_point_ids']:
                local_index = support_lookup[point]
                base_slope_map[point_index[point]] = base_slopes[support_labels[local_index]]

        transported = bool(config.get('use_full_transported_phase', False))
        fixed_bridges = False
        base_segments, base_slopes = self._generate_dynamic_segments(base_slope_map)
        base_angles = self._calculate_dynamic_angles(
            mode='recon', segments=base_segments, seg_slopes=base_slopes,
        )
        base_magnitude, _ = self._calculate_curvature_and_angle(
            epsilon=strain_data, alpha_dynamic=base_angles,
        )
        score_magnitude = np.asarray(base_magnitude, dtype=float) * magnitude_ratio

        final_weight = np.empty(self.total_points, dtype=float)
        slope_map = np.empty(self.total_points, dtype=float)
        diagnostics = {
            'direct': direct,
            'base_slope_map': base_slope_map.tolist(),
            'fixed_full_level0_bridges': bool(fixed_bridges),
            'base_magnitude': np.asarray(base_magnitude).tolist(),
        }
        for name in config['region_order']:
            block = config['regions'][name]
            support_indices = np.asarray([point_index[p] for p in block['support_point_ids']], dtype=int)
            owned_indices = np.asarray([point_index[p] for p in block['owned_point_ids']], dtype=int)
            support_lookup = {
                point: local_index for local_index, point in enumerate(block['support_point_ids'])
            }
            owned_local = np.asarray([support_lookup[p] for p in block['owned_point_ids']], dtype=int)
            support_score = score_magnitude[support_indices]
            slope_scores = self._get_scores(
                support_score,
                thresholds=block['thresholds'],
                sharpness=block['sharpness'],
                min_consecutive=block['score_window'],
                boundary_mode=block['score_boundary_mode'],
            )
            slope_masses = self._alloc_mass(slope_scores)
            if block['weight_score_mode'] == 'group_mean':
                weight_scores, group_base_magnitude = self._get_groupwise_weight_scores(
                    support_score,
                    block['weight_group_ids'],
                    thresholds=block['thresholds'],
                    sharpness=block['sharpness'],
                )
                weight_masses = self._alloc_mass(weight_scores)
            else:
                weight_scores = slope_scores
                weight_masses = slope_masses
                group_base_magnitude = None
            weights = block['weights'][direct]
            levels = weight_masses.shape[0]
            weight_vectors = np.broadcast_to(weights[:levels, None], weight_masses.shape).copy()
            if block['weight_group_ids'] is not None:
                weight_vectors = weights.reshape(-1, levels)[np.asarray(block['weight_group_ids'])].T
            elif block['end_weights']:
                # 负索引相对于区域support真实点，虚拟点随后复制补偿后的末点。
                weight_vectors[:, block['end_start']:] = weights[levels:, None]
            support_weights = np.sum(weight_masses * weight_vectors, axis=0)
            labels = self._local_segment_labels(block['local_segmentation'])
            slopes = block['slopes'][direct]
            slope_vectors = slopes[:, labels]
            support_slopes = np.sum(slope_masses * slope_vectors, axis=0)
            final_weight[owned_indices] = support_weights[owned_local]
            slope_map[owned_indices] = support_slopes[owned_local]
            diagnostics[name] = {
                'support_point_ids': list(block['support_point_ids']),
                'owned_point_ids': list(block['owned_point_ids']),
                'thresholds': block['thresholds'].tolist(),
                'score_mode': block['weight_score_mode'],
                'weight_score_mode': block['weight_score_mode'],
                'group_base_magnitude': group_base_magnitude,
                'scores': slope_scores.tolist(),
                'masses': slope_masses.tolist(),
                'slope_scores': slope_scores.tolist(),
                'slope_masses': slope_masses.tolist(),
                'weight_scores': weight_scores.tolist(),
                'weight_masses': weight_masses.tolist(),
                'mass_shape': list(weight_masses.shape),
                'end_weights': block['end_weights'],
                'end_start': block['end_start'],
                'weight_group_ids': block['weight_group_ids'],
                'effective_weights': support_weights.tolist(),
                'effective_support_slopes': support_slopes.tolist(),
            }

        if transported:
            from calibration_phase_reference import _mixed_slopes, anchor_full_mixed_phases
            # self retains full's independent score/window/threshold configuration.
            full_mixed = _mixed_slopes(self, strain_data.T, direct)
            bridges = anchor_full_mixed_phases(slope_map, full_mixed, self.samp_dist,
                                               config, self.global_point_ids,
                                               {name: diagnostics[name]['effective_support_slopes']
                                                for name in config['region_order']})
            diagnostics['full_mixed_phase_anchors'] = bridges
            diagnostics['full_independent_mixed_slopes'] = full_mixed.tolist()
        weighted_strain = strain_data * final_weight
        final_segments, final_slopes = self._generate_dynamic_segments(slope_map)
        final_angles = self._calculate_dynamic_angles(
            mode='recon', segments=final_segments, seg_slopes=final_slopes,
        )
        magnitude, angle = self._calculate_curvature_and_angle(
            epsilon=weighted_strain, alpha_dynamic=final_angles,
        )
        diagnostics['final_weight'] = final_weight.tolist()
        diagnostics['slope_map'] = slope_map.tolist()
        diagnostics['final_magnitude'] = np.asarray(magnitude).tolist()
        diagnostics['final_angle'] = np.asarray(angle).tolist()
        diagnostics['final_theta_dynamic'] = np.asarray(final_angles).tolist()
        return magnitude, angle, final_weight, slope_map, diagnostics
    
    def export_point_phases(self, output_path, *, direct):
        """Export sample-specific real-point phases before display rotation."""
        import csv
        from pathlib import Path
        if self.multi_region_parameters is None:
            raise ValueError('Phase export currently requires multi-region reconstruction')
        rows = []
        for shape in self.calib_shapes:
            for radius, frame in self.processed_Data[shape][direct].items():
                _, _, _, _, diagnostic = self._assemble_multiregion_parameters(
                    np.asarray(frame).T, direct)
                phase = np.asarray(diagnostic['final_theta_dynamic'])[0]
                for j, point in enumerate(self.global_point_ids):
                    rows.append([direct, shape, radius, int(point), self.samp_dist[j],
                                 phase[j], np.degrees(phase[j]), diagnostic['slope_map'][j],
                                 diagnostic['final_weight'][j], diagnostic['final_magnitude'][j],
                                 np.degrees(diagnostic['final_angle'][j])])
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['direct','shape','radius_mm','point','distance_m','phase_rad',
                             'phase_deg_unwrapped','slope_rad_per_m','weight',
                             'curvature_m_inv','bend_direction_deg'])
            writer.writerows(rows)
        return path

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

        在重构调用中，数组下标表示空间采样点，因此这是按点数等权的空间平均，
        不考虑相邻点的实际物理间距，也不保存跨帧状态。window_size=1 不做平滑。
        size=3、reflect 时，内部点取左右邻点和自身的均值；末点取
        (倒数第二点 + 2 * 末点) / 3，首点同理。

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

    def _smooth_curvature_direction(self, magnitude, angle,
                                    coherence_low=0.25, coherence_high=0.75,
                                    antipodal_start=np.deg2rad(150.0)):
        """用当前帧的邻域向量修正方向，保留每个点的原始曲率模长。

        不读取或更新上一帧状态，静态标定/优化与动态重构使用同一规则。
        magnitude、angle 为已经过调用方校验的一维等长数组，模长须非负。
        窗口内的曲率大小自然成为方向平均的权重，低曲率角度噪声影响较小。

        rho = |平均向量| / 平均模长衡量方向一致性。rho 低时保留当前点方向，
        高时采用平均方向，中间用 smoothstep 连续过渡，避免优化时硬切换。
        修正角接近 ±pi 时逐渐退回原方向，避免反向分支选择不稳定。
        默认 rho 阈值 0.25/0.75 和反向保护起点150度是可调初值，非标定结果；
        连续权重并不意味着整条 PCHIP/参数优化链处处可微。

        如果领域方向一致性很低，保持原方向不变，避免在零曲率/数值抵消处制造不可靠的方向。
        如果领域方向接近当前方向的反向，逐渐退回原方向，避免在 ±π 处不稳定的分支选择。
        """
        if not 0 <= coherence_low < coherence_high <= 1:
            raise ValueError('coherence thresholds must satisfy 0 <= low < high <= 1')
        if not 0 < antipodal_start < np.pi:
            raise ValueError('antipodal_start must be between 0 and pi')
        # 曲率向量的两分量表示，便于窗口平均和插值。cos/sin 对 2π 周期不变，可避免直接插值角度时的 ±π 分支跳变。
        components = magnitude[:, None] * np.column_stack((np.cos(angle), np.sin(angle)))
        averaged = np.column_stack([
            self._moving_average_scipy(components[:, j], self.move_filter, 'reflect')
            for j in range(2)
        ])
        # 平均模长用于计算方向一致性，避免零曲率点的噪声影响。平均向量模长用于计算最终的方向修正。
        mean_magnitude = self._moving_average_scipy(magnitude, self.move_filter, 'reflect')
        # 计算平均向量的模长，用于衡量方向一致性。
        resultant = np.hypot(averaged[:, 0], averaged[:, 1])
        # 零曲率/数值抵消处不计算有效方向，不用 epsilon 归一化来制造方向。
        tolerance = 32 * np.finfo(float).eps * np.maximum(1.0, mean_magnitude)
        # 仅在平均模长和平均向量模长都大于阈值时才计算方向一致性，否则保持原方向。如果曲率接近零，方向本身没有可靠物理意义，因此不进行方向修正。
        valid = (mean_magnitude > tolerance) & (resultant > tolerance)
        # 方向一致性计算
        coherence = np.zeros_like(magnitude)
        np.divide(resultant, mean_magnitude, out=coherence, where=valid)
        # 根据阈值归一化到 [0, 1]，并使用 smoothstep 函数平滑过渡。
        fraction = np.clip((coherence - coherence_low) / (coherence_high - coherence_low), 0., 1.)
        weight = fraction * fraction * (3. - 2. * fraction) #smoothstep function: 3f^2 - 2f^3
        # 计算当前点与平均方向的角度差，并用arctan2将其限制在 [-π, π] 范围内，避免 ±π 分支跳变。
        delta = np.zeros_like(angle)
        difference = np.arctan2(averaged[valid, 1], averaged[valid, 0]) - angle[valid]
        delta[valid] = np.arctan2(np.sin(difference), np.cos(difference))
        # 当 delta 接近 ±π 时，逐渐退回原方向，避免反向分支选择不稳定。
        fraction = np.clip((np.pi - np.abs(delta)) / (np.pi - antipodal_start), 0., 1.)
        weight *= fraction * fraction * (3. - 2. * fraction)
        corrected_angle = angle + weight * delta
        # 只借用平均后的方向；零模长仍为零，不把邻点的大曲率摊到当前点。
        return magnitude[:, None] * np.column_stack((np.cos(corrected_angle), np.sin(corrected_angle)))

    def _interpolate_curvature_vector(self, magnitude, angle, method):
        """对局部弯曲平面内的曲率向量进行空间滤波和插值。

        输入 magnitude 是补齐虚拟点、未经 Kalman 滤波的曲率；理想曲率模式传入理论值。
        angle 是 angle_unwrap，不是预先做过角度窗口平均的 ang_filter。
        两者均与 ad_samp_dist 一一对应，含调用方添加的虚拟点。

        流程：极坐标转两分量 → 可选窗口估计方向并保护抵消/反向情况 → 恢复原始模长
        → 各分量线性/PCHIP 插值
        → 还原模长与方向。分量不是最终三维曲线的全局 X、Y 坐标。
        cos/sin 对 2π 周期不变，可避免直接插值角度时的 ±π 分支跳变。

        注意：move_filter_for_vector=True 时，本函数显式执行窗口平均；这不是 PCHIP
        内部操作。窗口仅修正方向，输入节点的模长保持不变；PCHIP点间向量仍可能抵消，
        因此本方法不保证点间模长或最终形状半径完全无偏。不需要上一帧数据。
        返回 cur_interp（曲率模长）、ang_interp（弧度）、interp_dist（米）。
        """
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
        if np.any(magnitude < 0):
            raise ValueError('curvature magnitude must be nonnegative')
        # 可选三点窗口只提供方向候选；关闭时直接插值原始曲率向量分量。
        # 两种路径都保留调用方输入的 magnitude，且静态/动态没有历史状态依赖。
        if self.move_filter_for_vector:
            components = self._smooth_curvature_direction(magnitude, angle)
        else:
            components = magnitude[:, None] * np.column_stack((np.cos(angle), np.sin(angle)))
        interp_dist = np.linspace(samp_dist[0], samp_dist[-1], num=self.interp_num)
        if method == 'linear':
            interpolated = np.column_stack(
                [np.interp(interp_dist, samp_dist, components[:, component]) for component in range(2)]
            )
        else:
            # axis=0 沿空间点插值，两列分量独立处理。PCHIP 本身不做窗口平均，
            # 输入节点由 move_filter_for_vector 决定；点间向量模长仍可能因方向变化而下降。
            # 等距输出网格未必包含原采样节点，输出峰值可能低于输入节点峰值。
            interpolated = PchipInterpolator(samp_dist, components, axis=0)(interp_dist)

        # 将插值后的局部曲率向量还原成后续标架重构需要的曲率大小和方向。
        cur_interp = np.hypot(interpolated[:, 0], interpolated[:, 1])
        ang_interp = np.arctan2(interpolated[:, 1], interpolated[:, 0])
        return cur_interp, ang_interp, interp_dist
    
    def _Kalman_filter(self, data, Rk, Bk):
        """
        对一维数据执行简化 Kalman 滤波。

        _reconstruct_frame 传入单帧 magnitude，因此循环沿光纤空间点推进，
        每次调用重新初始化，不是对同一传感点进行跨帧 Kalman 滤波。
        输出为当前观测与前一空间点滤波结果的加权组合，仅向后传递信息。
        默认 Rk=0.0001、Bk=0.01 时稳态增益约 0.9902，空间平滑较弱。
        当前重构入口只调用 magnitude 的 Kalman，未调用 angle 的 Kalman。

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
    def _build_end_pose(T, Y, Z, rot_matrix, rot_ang_deg):
        """Rotate the terminal frame globally, then undo rot_ang about its rotated T axis."""
        T = np.asarray(T, dtype=float)
        Y = np.asarray(Y, dtype=float)
        Z = np.asarray(Z, dtype=float)
        rot_matrix = np.asarray(rot_matrix, dtype=float)
        rot_ang_deg = float(rot_ang_deg)

        if T.ndim != 2 or Y.ndim != 2 or Z.ndim != 2:
            raise ValueError("T, Y and Z must be two-dimensional frame arrays")
        if T.shape[1] != 3 or Y.shape[1] != 3 or Z.shape[1] != 3:
            raise ValueError("T, Y and Z must have shape (num_points, 3)")
        if not (len(T) == len(Y) == len(Z)):
            raise ValueError("T, Y and Z must contain the same number of points")
        if rot_matrix.shape != (3, 3) or not np.all(np.isfinite(rot_matrix)):
            raise ValueError("rot_matrix must be a finite matrix with shape (3, 3)")
        if not np.isfinite(rot_ang_deg):
            raise ValueError("rot_ang_deg must be finite")
        if len(T) == 0:
            return None

        terminal_t = T[-1] @ rot_matrix.T
        terminal_y = Y[-1] @ rot_matrix.T
        terminal_z = Z[-1] @ rot_matrix.T
        t_norm = float(np.linalg.norm(terminal_t))
        if not np.isfinite(t_norm) or t_norm <= np.finfo(float).eps:
            raise ValueError("terminal T axis must be finite and non-zero")
        local_axis = terminal_t / t_norm
        theta = np.deg2rad(-rot_ang_deg)
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        def rotate_about_terminal_t(vector):
            return (
                vector * cos_theta
                + np.cross(local_axis, vector) * sin_theta
                + local_axis * np.dot(local_axis, vector) * (1.0 - cos_theta)
            )

        return np.stack(
            (
                terminal_t,
                rotate_about_terminal_t(terminal_y),
                rotate_about_terminal_t(terminal_z),
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
        sigma = np.deg2rad((direct) * rot_dir + self.rot_ang)
        rot_matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, np.cos(sigma), -np.sin(sigma)],
            [0.0, np.sin(sigma), np.cos(sigma)]
        ])
        return rot_matrix
