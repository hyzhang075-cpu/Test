import numpy as np
import time
import bisect
import copy
from scipy.optimize import minimize

from reconstructor import Reconstructor

from tools.utils import dict_recur_operate, dict_recur_extract, dict_recur_value, dict_recur_extract_path, fit_radius

class Optimiser(Reconstructor):
    def __init__(self, direct=0, end_len=0.05, max_iter=5, min_loss_diff=1e-6, hyper_params=[10000, 1e-6, 1e-6], freeze=None, method='Powell', straight_threshold=2.0, rot_threshold=4.0, k_point=1.0, k_end=0.0, k_pitch=1.0, k_radius=1.0, weight_bounds=(0.5, 1.0), slope_upper_bound=20.0, *args, end5cm_point_calib=False, real_point_calib=False, **kwargs):
        self.optim_weights_only = bool(kwargs.pop('optim_weights_only', False))
        self.preserve_first_point = bool(kwargs.pop('preserve_first_point', False))
        self.real_point_absolute_direction = bool(kwargs.pop('real_point_absolute_direction', False))
        self.end5cm_coverage_aware_weights = bool(kwargs.pop('end5cm_coverage_aware_weights', False))
        self.end5cm_min_weight_effective_samples = float(
            kwargs.pop('end5cm_min_weight_effective_samples', 1.0))
        self.end5cm_min_weight_max_mass = float(
            kwargs.pop('end5cm_min_weight_max_mass', 0.05))
        self.end5cm_uncovered_weight_policy = kwargs.pop(
            'end5cm_uncovered_weight_policy', 'interpolate_neutral_edges')
        self.source_sensor_params = kwargs.pop('source_sensor_params', None)
        self.assembled_phase_context = None
        super().__init__(*args, **kwargs)
        self.direct = direct
        self.end5cm_point_calib = end5cm_point_calib
        self.real_point_calib = bool(real_point_calib or end5cm_point_calib)
        self.end_len = end_len
        self.max_iter = max_iter
        self.min_loss_diff = min_loss_diff
        self.hyper_params = hyper_params

        self.method = method
        self.straight_threshold = straight_threshold
        self.rot_threshold = rot_threshold
        self.k_point = k_point
        self.k_end = k_end
        self.k_pitch = k_pitch
        self.k_radius = k_radius
        self.weight_bounds = [(weight_bounds[0] * self.init_weight, weight_bounds[1] * self.init_weight)]
        self.slope_upper_bound = slope_upper_bound
        self.slopes_shape = np.asarray(self.slopes[self.direct], dtype=float).shape

        self.freeze = freeze
        self._coverage_support_map = None
        self._get_freeze_idx()

    def _reconstruct_frame(self, *args, **kwargs):
        """Keep optimization diagnostics on the same per-sample phase reference."""
        context = getattr(self, 'assembled_phase_context', None)
        if context is None:
            return super()._reconstruct_frame(*args, **kwargs)
        keys = kwargs.get('keys', args[0] if args else None)
        data = kwargs.get('calib_Data', args[2] if len(args) > 2 else None)
        if data is None:
            raise ValueError('Missing calibration frame for assembled-phase replay')
        frame = data
        for key in keys or ():
            frame = frame[key]
        from calibration_phase_reference import assembled_sample_entry_phase
        full, upstream = context
        old_phase = self.global_phases_set
        try:
            self.global_phases_set = assembled_sample_entry_phase(
                full, upstream, self.calibration_context, self.direct, np.asarray(frame))
            return super()._reconstruct_frame(*args, **kwargs)
        finally:
            self.global_phases_set = old_phase

    def _uses_real_point_objective(self):
        """Support older callers that set only end5cm_point_calib."""
        return bool(getattr(self, 'real_point_calib', False)
                    or getattr(self, 'end5cm_point_calib', False))

    @staticmethod
    def _normalise_radius_key(value):
        """Use stable numeric keys when comparing configured and loaded radii."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        if np.isfinite(numeric) and numeric.is_integer():
            return int(numeric)
        return numeric

    def validate_calibration_data_radii(self):
        """Reject configured/data radius drift before scoring or optimization."""
        problems = []
        directs = [getattr(self, 'direct', 0)]
        for direct in directs:
            configured_shapes = self.radii.get(direct, {})
            loaded_shapes = self.processed_Data.get('circ', {}) if isinstance(
                self.processed_Data, dict) else {}
            loaded_direct = loaded_shapes.get(direct, {}) if isinstance(loaded_shapes, dict) else {}
            for shape, configured in configured_shapes.items():
                if not isinstance(configured, (list, tuple, np.ndarray)):
                    continue
                configured_keys = [self._normalise_radius_key(value) for value in configured]
                loaded = loaded_direct if shape == 'circ' else (
                    self.processed_Data.get(shape, {}).get(direct, {})
                    if isinstance(self.processed_Data, dict) else {}
                )
                if not isinstance(loaded, dict):
                    actual_keys = []
                else:
                    actual_keys = [self._normalise_radius_key(value) for value in loaded]
                configured_set = set(configured_keys)
                actual_set = set(actual_keys)
                missing = [value for value in configured_keys if value not in actual_set]
                unexpected = [value for value in actual_keys if value not in configured_set]
                if missing or unexpected:
                    problems.append(
                        f'direct={direct}, shape={shape}: '
                        f'missing configured radii={missing}; '
                        f'unexpected data radii={unexpected}'
                    )
        if problems:
            raise ValueError(
                '定标数据半径与配置不一致；请显式设置 --radii。' + ' | '.join(problems)
            )

    def _get_freeze_idx(self):
        if self.freeze is None:
            return np.array([], dtype=int)

        freeze_idx = np.unique(np.atleast_1d(self.freeze).astype(int))

        n_weights = len(self.weights[self.direct])
        n_slopes = self.slopes_shape[0]

        if np.any(freeze_idx < 0):
            raise ValueError(f"freeze 中不应包含负 index: {freeze_idx}")

        if np.any(freeze_idx >= n_weights):
            raise ValueError(f"freeze index 超出 weights 范围: freeze={freeze_idx}, weights长度={n_weights}")

        if np.any(freeze_idx >= n_slopes):
            raise ValueError(f"freeze index 超出 slopes 范围: freeze={freeze_idx}, slopes第一维长度={n_slopes}")

        return freeze_idx
    
    def _get_weight_freeze_mask(self):
        if getattr(self, 'end5cm_coverage_aware_weights', False):
            mask = np.ones(len(self.weights[self.direct]), dtype=bool)
            mask[self._get_weight_optim_indices()] = False
            return mask
        mask = np.zeros(len(self.weights[self.direct]), dtype=bool)
        freeze_idx = self._get_freeze_idx()
        mask[freeze_idx] = True

        if getattr(self, 'weight_group_ids', None) is not None:
            for group in range(1, max(self.weight_group_ids)+1):
                mask[freeze_idx + group*self.num_levels] = True
        elif self.end_weights:
            mask[freeze_idx + int(len(self.weights[self.direct]) / 2)] = True

        if self.preserve_first_point:
            if (not self.end_weights or self.end_start != -(self.total_points - 1)
                    or len(mask) != 2 * self.num_levels
                    or self.real_point_absolute_direction):
                raise ValueError('首点保留需要full首点/其余点两组weights，且关闭绝对方向目标')
            mask[:self.num_levels] = True
        return mask

    def _ensure_coverage_support_map(self):
        """Build one fixed support map from the production score inputs."""
        if not getattr(self, 'end5cm_coverage_aware_weights', False):
            return None
        if self._coverage_support_map is None:
            from calibration_batch import diagnose_score_distribution
            from tools.end5_weight_coverage import build_groupwise_support_map

            report = diagnose_score_distribution(self)
            self._coverage_support_map = build_groupwise_support_map(
                report['samples'], thresholds=self.thresholds,
                group_ids=self.weight_group_ids,
                min_effective_samples=self.end5cm_min_weight_effective_samples,
                min_max_mass=self.end5cm_min_weight_max_mass,
            )
            self._coverage_support_map['policy'] = self.end5cm_uncovered_weight_policy
        return self._coverage_support_map

    def _get_weight_optim_indices(self):
        """Return flat weight indices exposed to scipy in stable group/level order."""
        if not getattr(self, 'end5cm_coverage_aware_weights', False):
            return np.flatnonzero(~self._get_weight_freeze_mask())
        support = self._ensure_coverage_support_map()
        indices = []
        for group_name in sorted(support['groups'], key=int):
            group_index = int(group_name)
            indices.extend(
                group_index * self.num_levels + int(level)
                for level in support['groups'][group_name].get('free_levels', ())
            )
        return np.asarray(indices, dtype=int)

    def _expand_coverage_weight_candidate(self, free_values):
        from tools.end5_weight_coverage import expand_groupwise_weights

        support = self._ensure_coverage_support_map()
        values = np.asarray(free_values, dtype=float).reshape(-1)
        free_weights = {}
        cursor = 0
        for group_name in sorted(support['groups'], key=int):
            levels = [int(level) for level in support['groups'][group_name].get('free_levels', ())]
            free_weights[group_name] = {
                level: values[cursor + offset] for offset, level in enumerate(levels)
            }
            cursor += len(levels)
        if cursor != values.size:
            raise ValueError(f'coverage-aware free weight count mismatch: expected {cursor}, got {values.size}')
        return expand_groupwise_weights(free_weights, support).reshape(-1)

    def _get_slope_freeze_mask(self):
        mask = np.zeros(self.slopes_shape, dtype=bool)
        freeze_idx = self._get_freeze_idx()
        mask[freeze_idx, ...] = True
        return mask
    
    def optim_coeff(self, verbose=True):
        """
        按固定顺序执行两阶段优化：先优化 slopes，再优化 weights。

        处理流程：
        1. 根据 self.method 和 self.hyper_params 构造 scipy.optimize.minimize 的 options；
        2. 第一阶段优化 slopes，并设置 force_ideal_magnitude=True：
        - 重构时强制使用理论曲率大小；
        - 主要让 slopes 优化集中于曲率方向、扭转系数和空间形状；
        3. 第二阶段优化 weights，并设置 force_ideal_magnitude=False：
        - 恢复正常由应变估计 magnitude 的重构流程；
        - 主要调整不同曲率等级下的应变幅值权重；
        4. 使用最终参数对所有 calib_shapes 正常重构一次；
        5. 调用 _compute_error() 计算并打印最终误差统计。

        输出：
        - 参数仍写回 self.weights/self.slopes；返回两阶段状态，供区域批量任务保存。

        说明：
        - 第二阶段 init_loss 必须重新计算，不能沿用 slopes 阶段 loss；
        - 两个阶段的 loss 定义不同，因为第一阶段强制使用理论 magnitude；
        - 最终误差始终使用正常重构，即 force_ideal_magnitude=False。
        """
        self.validate_calibration_data_radii()
        self._ensure_coverage_support_map()
        if self.method == 'Powell':
            max_evals, xtol, ftol = self.hyper_params
            options = {"maxiter": int(max_evals), "xtol": float(xtol), "ftol": float(ftol), "disp": bool(verbose),}
        else:
            options = None

        start = time.time()
        if self._uses_real_point_objective():
            # Validate data before entering a potentially expensive optimization.
            fixed_slope_loss = self._real_point_loss(direction_only=True)
            if self.optim_weights_only:
                print('真实点 weights-only：固定继承slopes，仅优化weights(真实半径曲率)')
            else:
                print('真实点模式：slopes(首个真实点方向参考) -> weights(真实半径曲率)；最终仍报告几何误差')
        else:
            fixed_slope_loss = None
        if self.optim_weights_only:
            stage_order = 'fixed slopes, optimize weights only'
        else:
            stage_order = ('slopes(真实点方向) -> weights(真实点曲率幅值)' if self._uses_real_point_objective()
                           else 'slopes(强制理想曲率) -> weights(正常曲率)')
        print(f"-------------------- 优化开始, 方向: {self.direct}, 旋转角度: {self.rot_ang}, 顺序: {stage_order} --------------------")

        # ---------- 第一阶段：优化 slopes，强制使用理想 magnitude ----------
        if self.optim_weights_only:
            slopes_loss = fixed_slope_loss
            slopes_start_loss = fixed_slope_loss
            slopes_status = 'fixed'
            slopes_recoveries = []
        else:
            slopes_loss, slopes_status, slopes_start_loss, slopes_recoveries = self._optim_one_coeff_until_stop(coeff="slopes", init_loss=None, options=options, verbose=verbose, force_ideal_magnitude=True,)

        print(f"slopes 阶段结束: status={slopes_status}, start_loss={slopes_start_loss}, final_loss={slopes_loss}")
        print()

        # ---------- 第二阶段：优化 weights，恢复正常 magnitude ----------
        # 注意：这里必须 init_loss=None，不能沿用 slopes_loss。
        # 因为 slopes 阶段和 weights 阶段使用的是不同 loss 定义。
        weights_loss, weights_status, weights_start_loss, weights_recoveries = self._optim_one_coeff_until_stop(coeff="weights", init_loss=None, options=options, verbose=verbose, force_ideal_magnitude=False,)

        print(f"weights 阶段结束: status={weights_status}, start_loss={weights_start_loss}, final_loss={weights_loss}")
        print()

        current_loss = weights_loss

        end = time.time()
        print(f"优化耗时: {end - start}")
        end_label = 'weights-only优化结束' if self.optim_weights_only else '两阶段优化结束'
        print(f"-------------------- {end_label}, 方向: {self.direct}, 旋转角度: {self.rot_ang} --------------------")
        print()

        # ---------- 最终误差：必须使用正常重构，不强制 magnitude ----------
        rs = {}
        for calib_shape in self.calib_shapes:
            r_results_postrot, interp_dist = self.reconstruct_shapes(calib_shape=calib_shape, direct=self.direct, verbose=False, force_ideal_magnitude=False)
            rs[calib_shape] = r_results_postrot

        self._compute_error(interp_dist=interp_dist, rs=rs)

        print(f"当前最优应变权重: {self.weights[self.direct].tolist()}")
        print(f"当前最优扭转系数: {self.slopes[self.direct].tolist()}")
        print(f"最小误差: {current_loss}")
        self._print_errors()
        # 两阶段 loss 的曲率来源不同，分别保存；最终验收误差由正常重构统计获得。
        slope_loss_definition = (
            'fixed source slopes; not optimized' if self.optim_weights_only else
            ('mean circular direction error to first real point (1-cos)'
             if self._uses_real_point_objective() else 'ideal-magnitude geometry')
        )
        weight_loss_definition = (
            'mean squared relative real-point curvature error'
            if self._uses_real_point_objective() else 'measured-magnitude geometry'
        )
        slope_stage = {'status': slopes_status, 'start_loss': slopes_start_loss,
                       'final_loss': slopes_loss, 'source_sensor_params': self.source_sensor_params}
        weight_stage = {'status': weights_status, 'start_loss': weights_start_loss,
                        'final_loss': weights_loss}
        if slopes_recoveries:
            slope_stage['recoveries'] = slopes_recoveries
        if weights_recoveries:
            weight_stage['recoveries'] = weights_recoveries
        return {'objective': ('real_points' if self._uses_real_point_objective() else 'geometry'),
                'loss_definitions': {'slopes': slope_loss_definition,
                                      'weights': weight_loss_definition},
                'stages': {'slopes': slope_stage, 'weights': weight_stage}}

    def _optim_one_coeff_until_stop(self, coeff, init_loss, options, verbose=True, force_ideal_magnitude=False):
        """
        对单一参数类型连续优化，直到收敛、无改善、数值发散或达到最大轮数。

        参数：
        - coeff: 要优化的参数类型，只能为 'slopes' 或 'weights'。
        - init_loss: 本阶段已知的初始 loss；为 None 时由 _optim_coeff_iter() 内部计算。
        - options: 传递给 scipy.optimize.minimize 的 options。
        - verbose: 是否打印详细优化信息。当前主要由外层 optim_coeff() 控制 options。
        - force_ideal_magnitude: 当前阶段重构时是否强制使用理论曲率大小。

        处理流程：
        1. 保存每轮开始前的 weights 和 slopes，用于发散回滚；
        2. 将当前 slopes 按 slope_upper_bound 归一化；
        3. 调用 _optim_coeff_iter() 执行一轮优化；
        4. 若出现 ``SystemError: unknown opcode``，先回滚并重试当前轮一次；
        5. 重试仍失败且已有成功轮时，回退最近成功轮并结束当前阶段；
        6. 若本轮 loss 为非有限值，则认为数值发散并回滚；
        7. 若本轮得到有限但更差的 loss，则标记无改善并回滚；
        8. 若 loss 改善量处于 [0, min_loss_diff]，则认为收敛；
        9. 否则继续下一轮，直到达到 max_iter。

        输出：
        - current_loss: 阶段结束时的最佳 loss。
        - status: 字符串，取值为 'diverge'、'no_improvement'、'converge'、
          'max_iter' 或 'runtime_error_fallback'。
        - first_loss: 本阶段第一次实际计算得到的初始 loss。
        - recoveries: 可恢复 ``unknown opcode`` 事件列表；无事件时为空列表。

        说明：
        - 该函数负责阶段级别的循环、回滚和停止判定；
        - 单轮参数向量构造、bounds 和 scipy minimize 调用由 _optim_coeff_iter() 完成。
        """
        coeff_name = "扭转系数" if coeff == "slopes" else "应变权重"

        current_loss = init_loss
        best_loss = init_loss
        first_loss = init_loss
        last_successful_iteration = None
        recoveries = []

        print(f"-------------------- {coeff_name}连续优化开始 --------------------")

        for i in range(self.max_iter):
            prev_weights = copy.deepcopy(self.weights[self.direct])
            prev_slopes = copy.deepcopy(self.slopes[self.direct])

            slopes_flattened = np.asarray(self.slopes[self.direct], dtype=float).reshape(-1)
            slope_upper_bound = max(np.max(np.abs(slopes_flattened)), self.slope_upper_bound)
            slopes_normalised = slopes_flattened / slope_upper_bound

            first_unknown_opcode = None
            for attempt in range(2):
                try:
                    new_loss, iter_init_loss = self._optim_coeff_iter(coeff=coeff, i=i, init_loss=best_loss, slopes_normalised=slopes_normalised, slope_upper_bound=slope_upper_bound, options=options, force_ideal_magnitude=force_ideal_magnitude,)
                except SystemError as exc:
                    if 'unknown opcode' not in str(exc).lower():
                        raise
                    self.weights[self.direct] = copy.deepcopy(prev_weights)
                    self.slopes[self.direct] = copy.deepcopy(prev_slopes)
                    if first_unknown_opcode is None:
                        first_unknown_opcode = exc
                    if attempt == 0:
                        print(f"{coeff_name}第{i}轮遇到 SystemError: unknown opcode，已回滚并重试本轮一次")
                        continue
                    if last_successful_iteration is None:
                        print(f"{coeff_name}第{i}轮重试仍失败，且没有可回退的成功轮次")
                        raise
                    recovery = {
                        'iteration': i,
                        'exception_type': type(first_unknown_opcode).__name__,
                        'message': str(first_unknown_opcode),
                        'retry_count': 1,
                        'occurrences': 2,
                        'outcome': 'fallback_previous_iteration',
                        'fallback_iteration': last_successful_iteration,
                        'fallback_loss': float(best_loss),
                    }
                    recoveries.append(recovery)
                    print(
                        f"{coeff_name}第{i}轮重试仍遇到 unknown opcode；"
                        f"已回退第{last_successful_iteration}轮结果并结束当前阶段"
                    )
                    return best_loss, "runtime_error_fallback", first_loss, recoveries
                else:
                    if first_unknown_opcode is not None:
                        recoveries.append({
                            'iteration': i,
                            'exception_type': type(first_unknown_opcode).__name__,
                            'message': str(first_unknown_opcode),
                            'retry_count': 1,
                            'occurrences': 1,
                            'outcome': 'retry_succeeded',
                        })
                        print(f"{coeff_name}第{i}轮重试成功")
                    break

            # 核心改动：第一次进入时，best_loss 可能还是 None
            if best_loss is None:
                best_loss = iter_init_loss
                current_loss = iter_init_loss

            if first_loss is None:
                first_loss = iter_init_loss

            prev_loss = best_loss

            if not np.isfinite(new_loss):
                self.weights[self.direct] = prev_weights
                self.slopes[self.direct] = prev_slopes
                current_loss = prev_loss

                print(f"{coeff_name}优化出现非有限 loss，已回滚")
                return current_loss, "diverge", first_loss, recoveries

            if new_loss > prev_loss:
                self.weights[self.direct] = prev_weights
                self.slopes[self.direct] = prev_slopes
                current_loss = prev_loss

                print(f"{coeff_name}优化未改善，已回滚")
                return current_loss, "no_improvement", first_loss, recoveries

            current_loss = new_loss
            best_loss = new_loss
            last_successful_iteration = i

            improvement = prev_loss - current_loss

            if 0 <= improvement <= self.min_loss_diff:
                print(f"{coeff_name}优化已收敛")
                return current_loss, "converge", first_loss, recoveries

        print(f"{coeff_name}优化已达最大轮数")
        return current_loss, "max_iter", first_loss, recoveries
    
    def _optim_coeff_iter(self, coeff, i, init_loss, slopes_normalised, slope_upper_bound,options, force_ideal_magnitude=False):
        """
        执行一轮指定参数类型的 scipy 优化，并将最优结果写回对象状态。

        参数：
        - coeff: 要优化的参数类型，只能为 'slopes' 或 'weights'。
        - i: 当前连续优化轮次编号，仅用于打印日志。
        - init_loss: 本轮初始 loss；若为 None，则先用当前参数计算一次 loss。
        - slopes_normalised: 当前 slopes 展平并归一化后的数组。
        - slope_upper_bound: slopes 归一化和恢复原始量级使用的尺度。
        - options: 传递给 scipy.optimize.minimize 的 options。
        - force_ideal_magnitude: 本轮 loss 计算时是否强制使用理论曲率大小。

        处理流程：
        1. 复制当前 weights 与归一化 slopes，作为本轮优化基准；
        2. 根据 coeff 生成冻结掩码和待优化掩码：
        - coeff == 'slopes': 优化未冻结的归一化 slope 元素，bounds 为 [-1, 1]；
        - coeff == 'weights': 优化未冻结的 weight 元素，bounds 为 self.weight_bounds；
        3. 构造只接收自由变量 x 的 loss_fn，并在内部还原完整 weights/slopes；
        4. 若所有变量都被冻结，则跳过 minimize 并直接返回 init_loss；
        5. 调用 scipy.optimize.minimize；
        6. 将最优自由变量写回完整 weights 或 slopes，并保存到 self。

        输出：
        - current_loss: 本轮优化结束后的 loss。
        - init_loss: 本轮优化开始时的 loss。

        异常：
        - coeff 不是 'slopes' 或 'weights' 时抛出 ValueError；
        - bounds 数量与自由变量数量不一致时抛出 ValueError。

        说明：
        - slopes 始终以归一化形式交给优化器，写回 self.slopes 时再乘以 slope_upper_bound；
        - weights 不做额外归一化，直接在实际数值边界内优化。
        """
        print(f"---------- 第{i}轮优化开始 ----------")
        start = time.time()

        base_weights = np.asarray(self.weights[self.direct], dtype=float).copy()
        base_slopes_normalised = np.asarray(slopes_normalised, dtype=float).reshape(self.slopes_shape).copy()

        if coeff == "slopes":
            freeze_mask = self._get_slope_freeze_mask()
            optimise_mask = ~freeze_mask

            x0 = base_slopes_normalised[optimise_mask]
            coeff_bounds = [(-1.0, 1.0)] * len(x0)

            def loss_fn(x):
                slopes_full = base_slopes_normalised.copy()
                slopes_full[optimise_mask] = x
                return self._loss_fn(self.rot_ang, base_weights, slopes_full.reshape(-1), slope_upper_bound, force_ideal_magnitude=force_ideal_magnitude)

        elif coeff == "weights":
            if getattr(self, 'end5cm_coverage_aware_weights', False):
                optimise_indices = self._get_weight_optim_indices()
                x0 = base_weights[optimise_indices]
            else:
                freeze_mask = self._get_weight_freeze_mask()
                optimise_indices = None
                optimise_mask = ~freeze_mask
                x0 = base_weights[optimise_mask]
            coeff_bounds = self.weight_bounds * len(x0)

            def loss_fn(x):
                if getattr(self, 'end5cm_coverage_aware_weights', False):
                    weights_full = self._expand_coverage_weight_candidate(x)
                else:
                    weights_full = base_weights.copy()
                    weights_full[optimise_mask] = x
                return self._loss_fn(self.rot_ang, weights_full, base_slopes_normalised.reshape(-1), slope_upper_bound, force_ideal_magnitude=force_ideal_magnitude)

        else:
            raise ValueError(f"Unknown coeff: {coeff}")

        if len(coeff_bounds) != len(x0):
            raise ValueError(f"bounds 长度({len(coeff_bounds)})与{coeff}长度({len(x0)})不一致")

        if init_loss is None:
            init_loss = float(loss_fn(x0))
        else:
            init_loss = float(init_loss)

        if len(x0) == 0:
            if coeff == "weights" and getattr(self, 'end5cm_coverage_aware_weights', False):
                self.weights[self.direct] = self._expand_coverage_weight_candidate(x0)
            current_loss = init_loss
            best_param = self.slopes[self.direct] if coeff == "slopes" else self.weights[self.direct]

            end = time.time()
            print(f"{coeff} 对应变量全部被冻结，跳过本轮优化")
            print(f"第{i}轮优化耗时: {end - start}")
            print(f"当前最优: {best_param}")
            print(f"当前最小误差: {current_loss}")
            print(f"提升幅度: {init_loss - current_loss}")
            print(f"---------- 第{i}轮优化结束 ----------")
            print()

            return current_loss, init_loss

        res = minimize(fun=loss_fn, x0=x0, method=self.method, options=options, bounds=coeff_bounds)
        current_loss = float(res.fun)

        if coeff == "slopes":
            slopes_best = base_slopes_normalised.copy()
            slopes_best[optimise_mask] = res.x
            self.slopes[self.direct] = (slopes_best * slope_upper_bound).reshape(self.slopes_shape)
            best_param = self.slopes[self.direct]

        elif coeff == "weights":
            if getattr(self, 'end5cm_coverage_aware_weights', False):
                weights_best = self._expand_coverage_weight_candidate(res.x)
            else:
                weights_best = base_weights.copy()
                weights_best[optimise_mask] = res.x
            self.weights[self.direct] = weights_best
            best_param = self.weights[self.direct]

        end = time.time()
        print(f"第{i}轮优化耗时: {end - start}")
        print(f"当前最优: {best_param}")
        print(f"当前最小误差: {current_loss}")
        print(f"提升幅度: {init_loss - current_loss}")
        print(f"---------- 第{i}轮优化结束 ----------")
        print()

        return current_loss, init_loss

    def _print_errors(self):
        """
        打印当前保存的各类重构误差统计结果。

        打印内容包括：
        - self.point_errors_avg: 各标定形状内部各半径（及嵌套形状下各二级参数）的平均逐点误差
        - self.end_errors: 各标定形状内部各半径（及嵌套形状下各二级参数）的末端误差
        - self.avg_point_err: 各标定形状的平均逐点误差，以及键 'calib' 对应的校准形状总体平均逐点误差
        - self.avg_end_err: 各标定形状的平均末端误差，以及键 'calib' 对应的校准形状总体平均末端误差
        - self.rot0_pitch_errors / self.rot0_radius_errors: rot0 形状的螺距误差与半径误差
        - self.avg_pitch_err / self.avg_radius_err: rot0 螺距误差与半径误差的平均值

        说明：
        - 当前实现中的 'calib' 仅汇总 circ、S、rot0 三类形状
        """
        print(f"各标定形状初始平均误差: {self.point_errors_avg}")
        print(f"各标定形状末端误差: {self.end_errors}")
        print(f"各零螺距标定形状螺距误差: {self.rot0_pitch_errors}")
        print(f"每点误差: {self.avg_point_err}")
        print(f"末端误差: {self.avg_end_err}")    
        print(f"螺距误差: {self.avg_pitch_err}")
        print(f"半径误差: {self.avg_radius_err}")
        print()

    def _real_point_loss(self, *, direction_only):
        """Use circular-bend measurements, excluding virtual points and straight states.

        Assembled mode evaluates each sample with its actual upstream phase and
        known planar bend direction. Legacy mode uses the first real point as
        its relative direction reference. No interpolation or smoothing enters
        this loss. Each radius and each valid real point has equal
        influence. Amplitude errors are normalized by that radius's curvature.
        """
        if self.calib_shapes != ['circ']:
            raise ValueError('真实点定标目前仅支持circ圆弧数据')
        radii = np.asarray(self.radii[self.direct]['circ'], dtype=float)
        if not np.all(np.isfinite(radii)) or np.any(radii < 0) or not np.any(radii > 0):
            raise ValueError('真实点定标需要有限正半径；0仅表示直线状态')
        losses = []
        for radius in radii[radii > 0]:
            saved_phase = self.global_phases_set
            if getattr(self, 'assembled_phase_context', None) is not None:
                from calibration_phase_reference import assembled_sample_entry_phase
                full, upstream = self.assembled_phase_context
                frame = np.asarray(self.processed_Data['circ'][self.direct][radius])
                self.global_phases_set = assembled_sample_entry_phase(
                    full, upstream, self.calibration_context, self.direct, frame)
            try:
                magnitude, angle = self._Strain_2_Cur(
                    keys=[radius], calib_shape='circ',
                    calib_Data=self.processed_Data['circ'][self.direct],
                    weight=self.weights[self.direct], slope=self.slopes[self.direct],
                    direct=self.direct,
                )
            finally:
                self.global_phases_set = saved_phase
            magnitude = np.asarray(magnitude, dtype=float)
            angle = np.asarray(angle, dtype=float)
            if (magnitude.shape != (self.total_points,) or angle.shape != magnitude.shape
                    or not np.all(np.isfinite(magnitude)) or not np.all(np.isfinite(angle))):
                raise ValueError('真实点曲率/方向包含非法数据')
            if direction_only:
                valid = magnitude > 1e-12
                if not np.any(valid):
                    raise ValueError('真实点没有有效曲率，不能评价方向')
                if (getattr(self, 'assembled_phase_context', None) is not None
                        or getattr(self, 'real_point_absolute_direction', False)):
                    target = -np.deg2rad(self.direct * self.rot_dir[0] + self.rot_ang)
                    losses.append(float(np.mean(1. - np.cos(angle[valid] - target))))
                else:
                    if not valid[0]:
                        raise ValueError('首个真实点无有效曲率，不能确定方向参考')
                    losses.append(float(np.mean(1. - np.cos(angle[valid] - angle[0]))))
            else:
                target_curvature = 1000. / radius
                evaluated = magnitude[1:] if self.preserve_first_point else magnitude
                losses.append(float(np.mean((evaluated / target_curvature - 1.) ** 2)))
        return float(np.mean(losses))

    def _loss_fn(self, rot_ang, weights, slopes_normalised, slope_upper_bound, force_ideal_magnitude=False):
        """
        给定当前候选参数，计算优化器使用的总损失值。

        参数：
        - rot_ang: 当前旋转角补偿，单位为度。
        - weights: 当前候选应变权重向量。
        - slopes_normalised: 当前候选归一化 slopes，通常为展平数组。
        - slope_upper_bound: 将 slopes_normalised 恢复为实际 slopes 的尺度。
        - force_ideal_magnitude: 重构时是否强制使用理论曲率大小。

        处理流程：
        1. 将 rot_ang 写回 self.rot_ang；
        2. 将 weights 写回 self.weights[self.direct]；
        3. 将 slopes_normalised * slope_upper_bound reshape 为 self.slopes_shape，并写回 self.slopes[self.direct]；
        4. 使用当前参数对 self.calib_shapes 中的所有形状执行重构；
        5. 调用 _compute_error() 更新逐点误差、末端误差、rot0 螺距误差和半径误差；
        6. 返回加权总损失：
        k_point * avg_point_err['calib']
        + k_end * avg_end_err['calib']
        + k_pitch * avg_pitch_err
        + k_radius * avg_radius_err。

        输出：
        - loss: 标量浮点数，总优化损失。

        说明：
        - force_ideal_magnitude=True 时，曲率大小不再来自应变幅值估计，主要用于 slopes 阶段；
        - real_point_calib=True时，此布尔字段改为区分真实点方向/幅值目标，不进入几何重构；
        - 当前 'calib' 汇总误差由 _compute_error() 中的 calib_error_shapes 决定，通常包括 circ、S、end、end3；
        - rot0 不参与 'calib' 的逐点/末端误差汇总，而通过 avg_pitch_err 与 avg_radius_err 单独进入损失。
        """
        # ---------- unpack parameters ----------
        self.rot_ang = rot_ang
        self.weights[self.direct] = weights
        # self.weights[self.direct] = np.ones(self.num_levels)
        self.slopes[self.direct] = (slopes_normalised * slope_upper_bound).reshape(self.slopes_shape)
        if self._uses_real_point_objective():
            return self._real_point_loss(direction_only=force_ideal_magnitude)
        # ---------- 计算误差 ----------
        rs = {}
        for calib_shape in self.calib_shapes:
            r_results_postrot, interp_dist = self.reconstruct_shapes(calib_shape=calib_shape, direct=self.direct, verbose=False, force_ideal_magnitude=force_ideal_magnitude,)
            rs[calib_shape] = r_results_postrot

        self._compute_error(interp_dist=interp_dist, rs=rs)

        return self.k_point * self.avg_point_err['calib'] + self.k_end * self.avg_end_err['calib'] + self.k_pitch * self.avg_pitch_err + self.k_radius * self.avg_radius_err

    def _compute_error(self, interp_dist, rs):
        """
        计算各类标定形状下的重构结果相对于理论标定曲线的误差。

        当前版本假设 straight_trim 已经在 Sensor 阶段直接裁剪：
        - self.Data / self.processed_Data / self.plot_Data 已经只保留有效段；
        - self.samp_dist / self.ad_samp_dist 已经对应有效段；
        - 因此这里不再使用 trim_mask，也不再对重构结果做二次裁剪。

        参数：
        - interp_dist: 当前重构使用的插值弧长坐标数组，单位为 m。
        - rs: 按标定形状组织的重构结果字典，通常由 reconstruct_shapes() 生成。

        处理流程：
        1. 初始化各类误差缓存字典；
        2. 将 interp_dist 转为相对弧长，并检查有效评估长度；
        3. 对 rot0：
        - 根据 self.cur_interp 识别旋转段；
        - 估计旋转轴；
        - 计算螺距误差和半径误差；
        4. 对其他标定形状：
        - 调用 _construct_ideals() 构造理论曲线；
        - 调用 _compute_point_err() 计算归一化逐点误差；
        - 提取末端误差和平均逐点误差；
        5. 汇总 circ、S、end、end3 的 calib 平均逐点误差和末端误差。

        副作用：
        - 更新 self.point_errors；
        - 更新 self.point_errors_avg；
        - 更新 self.end_errors；
        - 更新 self.avg_point_err；
        - 更新 self.avg_end_err；
        - 更新 self.rot0_pitch_errors；
        - 更新 self.rot0_radius_errors；
        - 更新 self.avg_pitch_err；
        - 更新 self.avg_radius_err。

        异常：
        - interp_dist 为空、有效长度非正，或 rot0 段识别失败时会抛出 ValueError。
        """
        self.point_errors = {}
        self.point_errors_avg = {}
        self.end_errors = {}
        self.avg_point_err = {}
        self.avg_end_err = {}

        self.rot0_pitch_errors = None
        self.rot0_radius_errors = None
        self.avg_pitch_err = 0
        self.avg_radius_err = 0

        # 现在 interp_dist 本身已经对应裁剪后的有效段
        interp_dist_eval = np.asarray(interp_dist, dtype=float)

        if len(interp_dist_eval) == 0:
            raise ValueError("interp_dist 为空，无法计算误差")

        # 保险起见，统一从 0 开始；如果 Sensor 中已经归零，这里不会改变结果
        interp_dist_eval = interp_dist_eval - interp_dist_eval[0]

        if len(interp_dist_eval) == 1:
            val_len = 0.0
        else:
            val_len = float(interp_dist_eval[-1])

        if val_len <= 0:
            raise ValueError(
                f"有效评估长度 val_len={val_len} 非正，"
                f"请检查裁剪后的 samp_dist / interp_dist 是否至少包含两个不同位置的点。"
            )

        for calib_shape in self.calib_shapes:
            if calib_shape not in rs:
                continue

            results = rs[calib_shape]

            if calib_shape == "rot0":
                cur_interp_eval = np.asarray(self.cur_interp, dtype=float)
                rot0_errors = dict_recur_extract_path(d=results, f=lambda x, path: self._compute_rot0_err(result=x, cur_interp=cur_interp_eval, radius_m=path[-2] * 0.001))
                pitch_errors = dict_recur_extract(d=rot0_errors, f=lambda x: x[0])
                radius_errors = dict_recur_extract(d=rot0_errors, f=lambda x: x[1])

                self.rot0_pitch_errors = pitch_errors
                self.rot0_radius_errors = radius_errors

                pitch_vals = dict_recur_value(pitch_errors)
                radius_vals = dict_recur_value(radius_errors)

                self.avg_pitch_err = np.nanmean(pitch_vals)
                self.avg_radius_err = np.nanmean(radius_vals)

            else:
                ideals = self._construct_ideals(calib_shape=calib_shape, interp_dist=interp_dist_eval, val_len=val_len)
                point_errors = dict_recur_operate(d1=results, d2=ideals, f=lambda x, y: self._compute_point_err(result=x, ideal=y, interp_dist=interp_dist_eval, val_len=val_len) )
                end_errors = dict_recur_extract(d=point_errors, f=lambda x: x[-1])
                point_errors_avg = dict_recur_extract(d=point_errors, f=lambda x: np.nanmean(x))

                self.point_errors[calib_shape] = point_errors
                self.end_errors[calib_shape] = end_errors
                self.point_errors_avg[calib_shape] = point_errors_avg

                point_vals = dict_recur_value(point_errors_avg)
                end_vals = dict_recur_value(end_errors)

                self.avg_point_err[calib_shape] = np.nanmean(point_vals)
                self.avg_end_err[calib_shape] = np.nanmean(end_vals)

        calib_error_shapes = ["circ", "S", "end", "end3"]
        calib_point_errors_avg = {k: self.point_errors_avg[k] for k in calib_error_shapes if k in self.point_errors_avg}
        calib_end_errors = {k: self.end_errors[k] for k in calib_error_shapes if k in self.end_errors}

        calib_point_vals = dict_recur_value(calib_point_errors_avg)
        calib_end_vals = dict_recur_value(calib_end_errors)

        self.avg_point_err["calib"] = np.nanmean(calib_point_vals)
        self.avg_end_err["calib"] = np.nanmean(calib_end_vals)

    def _construct_ideals(self, calib_shape, interp_dist, val_len):
        """
        计算各类标定形状下的重构结果相对于理论标定曲线的误差。

        当前版本假设 straight_trim 已经在 Sensor 阶段直接裁剪：
        - self.Data / self.processed_Data / self.plot_Data 已经只保留有效段；
        - self.samp_dist / self.ad_samp_dist 已经对应有效段；
        - 因此这里不再使用 trim_mask，也不再对重构结果做二次裁剪。

        参数：
        - interp_dist: 当前重构使用的插值弧长坐标数组，单位为 m。
        - rs: 按标定形状组织的重构结果字典，通常由 reconstruct_shapes() 生成。

        处理流程：
        1. 初始化各类误差缓存字典；
        2. 将 interp_dist 转为相对弧长，并检查有效评估长度；
        3. 对 rot0：
        - 根据 self.cur_interp 识别旋转段；
        - 估计旋转轴；
        - 计算螺距误差和半径误差；
        4. 对其他标定形状：
        - 调用 _construct_ideals() 构造理论曲线；
        - 调用 _compute_point_err() 计算归一化逐点误差；
        - 提取末端误差和平均逐点误差；
        5. 汇总 circ、S、end、end3 的 calib 平均逐点误差和末端误差。

        副作用：
        - 更新 self.point_errors；
        - 更新 self.point_errors_avg；
        - 更新 self.end_errors；
        - 更新 self.avg_point_err；
        - 更新 self.avg_end_err；
        - 更新 self.rot0_pitch_errors；
        - 更新 self.rot0_radius_errors；
        - 更新 self.avg_pitch_err；
        - 更新 self.avg_radius_err。

        异常：
        - interp_dist 为空、有效长度非正，或 rot0 段识别失败时会抛出 ValueError。
        """
        ideals = {}
        for radius in self.radii[self.direct][calib_shape]:
            radius_m = radius * 0.001
            if calib_shape == 'circ':
                ideals[radius] = self._construct_ideal_shape(calib_shape=calib_shape, interp_dist=interp_dist, val_len=val_len, radius_m=radius_m, idx_m=None)
            elif calib_shape == 'S':
                ideals[radius] = self._construct_ideal_shape(calib_shape=calib_shape, interp_dist=interp_dist, val_len=2*np.pi*radius_m+0.1, radius_m=radius_m, idx_m=None)
            elif calib_shape in ['end', 'rot0', 'up', 'down']:
                ideals[radius] = {}
                for idx in self.radii[self.direct][calib_shape][radius]:
                    idx_m = idx * 0.001
                    ideals[radius][idx] = self._construct_ideal_shape(calib_shape=calib_shape, interp_dist=interp_dist, val_len=val_len, radius_m=radius_m, idx_m=idx_m)
            elif calib_shape == 'end3':
                ideals[radius] = {}
                for angle_deg in self.radii[self.direct][calib_shape][radius]:
                    ideals[radius][angle_deg] = self._construct_ideal_shape(calib_shape=calib_shape, interp_dist=interp_dist, val_len=val_len, radius_m=radius_m, idx_m=None, angle_deg=angle_deg)
        return ideals
                
    def _construct_ideal_shape(self, calib_shape, interp_dist, val_len, radius_m, idx_m, angle_deg=None):
        ideal_shape = []
        for arc_len in interp_dist:
            if arc_len <= val_len:
                if radius_m == 0:
                    real_point = np.array([arc_len, 0, 0])
                else:
                    if calib_shape == 'circ':
                        real_point = self._construct_ideal_circ(radius_m=radius_m, arc_len=arc_len)
                    elif calib_shape == 'S':
                        real_point = self._construct_ideal_S(radius_m=radius_m, arc_len=arc_len)
                    elif calib_shape == 'end':
                        real_point = self._construct_ideal_end(radius_m=radius_m, radius_end_m=idx_m, arc_len=arc_len)
                    elif calib_shape == 'rot0':
                        real_point = self._construct_ideal_rot0(radius_m=radius_m, rot_pos=idx_m, arc_len=arc_len)
                    elif calib_shape in ['up', 'down']:
                        real_point = self._construct_ideal_rot(radius_m=radius_m, pitch=idx_m, dir=calib_shape, arc_len=arc_len)
                    elif calib_shape == 'end3':
                        real_point = self._construct_ideal_end3(radius_m=radius_m, angle_deg=angle_deg, arc_len=arc_len)
                ideal_shape.append(real_point)
        return np.array(ideal_shape)

    def _construct_ideal_circ(self, radius_m, arc_len):
        x = radius_m * np.sin(arc_len / radius_m)
        y = radius_m * (1.0 - np.cos(arc_len / radius_m))
        real_point = np.array([x, y, 0.0])
        return real_point

    def _construct_ideal_end3(self, radius_m, angle_deg, arc_len):
        """
        构造 x-y-z-end3 的理论圆弧。

        约定：
        - x 已经作为 direct 进入外层数据结构；
        - y 是圆弧半径，已在调用处转换为 radius_m；
        - z 是圆弧平面相对 +y 方向的顺时针夹角，单位为度；
        - z=0 时退化为现有 circ 基准，即位于 x-y 平面并向 +y 弯曲。
        """
        if angle_deg is None:
            raise ValueError("end3 ideal requires angle_deg, but got None")

        base_point = self._construct_ideal_circ(radius_m=radius_m, arc_len=arc_len)
        angle_rad = np.deg2rad(float(angle_deg))

        x = base_point[0]
        lateral = base_point[1]
        y = lateral * np.cos(angle_rad)
        z = -lateral * np.sin(angle_rad)

        return np.array([x, y, z])

    def _construct_ideal_S(self, radius_m, arc_len):
        straight_len = 0.1
        half_arc_len = np.pi * radius_m
        total_S_len = 2 * half_arc_len

        if arc_len <= straight_len:
            real_point = np.array([arc_len, 0.0, 0.0])

        elif arc_len <= straight_len + half_arc_len:
            theta = (arc_len - straight_len) / radius_m
            x = straight_len + radius_m * np.sin(theta)
            y = radius_m * (1.0 - np.cos(theta))
            real_point = np.array([x, y, 0.0])

        elif arc_len <= straight_len + total_S_len:
            theta = (arc_len - straight_len - half_arc_len) / radius_m
            x = straight_len - radius_m * np.sin(theta)
            y = 2.0 * radius_m + radius_m * (1.0 - np.cos(theta))
            real_point = np.array([x, y, 0.0])
        return real_point
    
    def _construct_ideal_end(self, radius_m, radius_end_m, arc_len):
        if arc_len <= self.samp_dist[-1] - self.end_len:
            real_point = self._construct_ideal_circ(radius_m=radius_m, arc_len=arc_len)
        else:
            # 第一段在拼接点的末端位置
            p0 = self._construct_ideal_circ(radius_m=radius_m, arc_len=self.samp_dist[-1]-self.end_len)
            # 第二段使用局部弧长
            p_local = self._construct_ideal_circ(radius_m=radius_end_m, arc_len=arc_len-(self.samp_dist[-1]-self.end_len))
            # 将第二段局部圆弧旋转到第一段末端切向方向，再平移到拼接点
            x = p0[0] + np.cos((self.samp_dist[-1] - self.end_len) / radius_m) * p_local[0] - np.sin((self.samp_dist[-1] - self.end_len) / radius_m) * p_local[1]
            y = p0[1] + np.sin((self.samp_dist[-1] - self.end_len) / radius_m) * p_local[0] + np.cos((self.samp_dist[-1] - self.end_len) / radius_m) * p_local[1]
            real_point = np.array([x, y, 0.0])
        return real_point
    
    def _construct_ideal_rot0(self, radius_m, rot_pos, arc_len):
        if arc_len < rot_pos:
            real_point = np.array([arc_len, 0, 0])
        elif rot_pos <= arc_len <= rot_pos + 2*np.pi*radius_m:
            circ_point = self._construct_ideal_circ(radius_m=radius_m, arc_len=arc_len-rot_pos)
            real_point = circ_point + np.array([rot_pos, 0, 0])
        else:
            real_point = np.array([arc_len - rot_pos - 2*np.pi*radius_m, 0, 0])
        return real_point
    
    def _construct_ideal_rot(self, dir, radius_m, pitch, arc_len):
        theta = arc_len / np.sqrt(radius_m**2 + (pitch / (2 * np.pi))**2)
        x = radius_m * np.sin(theta)
        y = radius_m * (1.0 - np.cos(theta))
        if dir in ["up", "down"]:
            dir = 1 if dir == "up" else -1
        else:
            raise ValueError(f"Unknown dir: {dir}")
        z = dir * theta * pitch / (2 * np.pi)
        real_point = np.array([x, y, z])
        return real_point
        
    def _compute_point_err(self, result, ideal, interp_dist, val_len):
        eval = min(bisect.bisect_right(interp_dist, val_len), len(result), len(ideal))
        if eval <= 0:
            return np.array([np.nan])

        # trim 后用剩余区间长度归一化；无 trim 时等价于原来的 interp_dist[-1]。
        norm_len = max(float(interp_dist[eval - 1] - interp_dist[0]), 1e-12)
        return np.linalg.norm(result[:eval] - ideal[:eval], axis=1) / norm_len
    
    def _compute_rot0_err(self, result, cur_interp, radius_m):
        rot_start, rot_end = self._find_rot_segment(cur_interp=cur_interp)
        points = result[rot_start:rot_end+1]
        rot_axis = self._find_rot_axis(points=points)
        rot_axis /= np.linalg.norm(rot_axis)

        real_radius = real_radius = np.linalg.norm(np.cross(points - points.mean(axis=0), rot_axis), axis=1).mean()
        radius_err = np.abs(real_radius - radius_m)
        pitch_err = np.abs(np.dot(points[-1] - points[0], rot_axis))

        return pitch_err, radius_err

    def _find_rot_segment(self, cur_interp, min_straight_len=3, min_consecutive_rot=5):
        pri_straight_end = min_straight_len
        while pri_straight_end < self.interp_num - min_straight_len - min_consecutive_rot and np.all(cur_interp[:pri_straight_end] < self.straight_threshold):
            pri_straight_end += 1

        post_straight_start = self.interp_num - min_straight_len
        while post_straight_start > pri_straight_end + min_consecutive_rot and np.all(cur_interp[post_straight_start:] < self.straight_threshold):
            post_straight_start -= 1

        rot_start = pri_straight_end + 1
        while pri_straight_end < rot_start < post_straight_start - min_consecutive_rot and np.all(cur_interp[rot_start:rot_start+min_consecutive_rot] < self.rot_threshold):
            rot_start += 1

        rot_end = post_straight_start - 1
        while pri_straight_end + min_consecutive_rot < rot_end < post_straight_start and np.all(cur_interp[rot_end-min_consecutive_rot:rot_end] < self.rot_threshold):
            rot_end -= 1

        if rot_end - rot_start < min_consecutive_rot - 1:
            raise ValueError(f"螺旋段长度不足: rot_start={rot_start}, rot_end={rot_end}, length={rot_end - rot_start + 1}, min_required={min_consecutive_rot}")
        else: 
            return rot_start, rot_end

    def _find_rot_axis(self, points, max_x_to_yz_ratio=0.5):
        centred_points = points - points.mean(axis=0)
        if np.allclose(centred_points, 0.0, atol=1e-9):
            raise ValueError("所有点重合，无法确定轴向")

        _, _, vh = np.linalg.svd(centred_points, full_matrices=False)

        # vh[0] 是最大方差方向，vh[-1] 是最小方差方向
        axis = vh[-1]
        axis = axis / np.linalg.norm(axis)

        x_comp, y_comp, z_comp = axis
        yz_magnitude = np.sqrt(y_comp**2 + z_comp**2)

        if yz_magnitude < 1e-12:
            ratio = np.inf
        else:
            ratio = abs(x_comp) / yz_magnitude

        # if ratio >= max_x_to_yz_ratio:
        #     print(f"警告 (PCA): 估计轴 [{x_comp:.3f}, {y_comp:.3f}, {z_comp:.3f}] 的 X 分量偏大，|x| / sqrt(y^2 + z^2) = {ratio:.3f} >= {max_x_to_yz_ratio}。")

        # 统一方向，避免 pitch 符号随机翻转
        if axis[2] < 0:
            axis = -axis

        return axis
