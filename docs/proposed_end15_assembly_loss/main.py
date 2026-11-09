import argparse
import ast
from copy import deepcopy
from email import parser
import time
import sys
import threading
import numpy as np
from pathlib import Path

from calibration_regions import resolve_calibration_region, validate_calibration_parameters
from calibration_batch import optimizer_parameters, prepare_calibration_jobs, run_calibration_jobs
from tools.sensor_parameter_package import (
    load_sensor_package, package_deployment_ready, package_parser_defaults,
)

from PyQt5.QtWidgets import QApplication

from optimiser import Optimiser
from visualisor import Visualisor
# from proto_demonstrator import Demonstrator 完整样机展示代码
from demonstrator import Demonstrator




def configure_calibration_args(args):
    """解析区域后再构造 Optimiser，确保非法分段在数据读取/优化前报错。

区域字典联动数据、半径、阈值、裁剪和局部分段。CLI 可覆盖所选区域的
数据与参数，但不能用不一致的 ideal_len/straight_trim 绕过几何校验。
返回的上下文保留全局点位映射；不把配置控制字段传给 Sensor 构造器。
"""
    if args.task == 'recon' and not args.multi_region_calib:
        # A single-region replay reconstructs only args.direct. Keep an explicit
        # experiment scope, but do not require unused parameter directions by default.
        if 'exp_directs' not in getattr(args, '_explicit_cli_parameters', ()):
            args.exp_directs = [args.direct]
        if args.direct not in args.exp_directs:
            raise ValueError('recon的direct必须包含在exp_directs中')
    if args.task in ('recon', 'demo') and args.multi_region_calib:
        if getattr(args, '_sensor_package', None) is None:
            raise ValueError('multi_region_calib=True 的全长 recon/demo 需要 --sensor_params 参数包')
        if args.task == 'demo' and not package_deployment_ready(args._sensor_package):
            direct = args.direction_reference_direct
            state = args._sensor_package.get('multi_region', {}).get(
                'direction_deployment', {}
            ).get(str(direct), {})
            print(
                '[WARNING] multi-region demo 使用尚未通过部署门禁的参数包: '
                f'deployment_ready=False, direction_reference_direct={direct}, '
                f'failures={state.get("failures", [])}。'
                '本次运行仅用于动态验证区域拼接效果。'
            )
        args.optimization_region = 'full'
        if args.use_full_transported_phase and not args._sensor_package.get(
                'multi_region', {}).get('use_full_transported_phase', False):
            raise ValueError('固定跨界模式需要重新优化并导出的参数包，不能直接启用于旧参数')
        args.multi_region_parameters = deepcopy(args._sensor_package)
        args.multi_region_parameters['multi_region']['use_full_transported_phase'] = args.use_full_transported_phase
    if (args.task == 'recon' and not args.multi_region_calib
            and args.optimization_region != 'full' and args.use_full_transported_phase):
        package = getattr(args, '_sensor_package', None)
        reference = (package or {}).get('regions', {}).get(args.optimization_region, {}).get(
            'phase_reference', {}).get(str(args.direct))
        if not reference:
            raise ValueError('固定局部相位recon需要使用新模式优化导出的sensor_params')
        args.global_phases_set = reference['phase_at_first_point_rad']
    if getattr(args, 'end15cm_assembly_loss', False):
        if (args.task != 'optim' or args.multi_region_calib
                or args.optimization_region != 'end15cm'
                or not args.end15cm_point_calib or args.use_full_transported_phase
                or args.optim_weights_only or args._sensor_package is None):
            raise ValueError('assembly loss仅支持来源包+独立end15cm optim，point_calib=True、transported_phase=False、weights_only=False')
        if args.reverse:
            raise ValueError('assembly loss试验仅支持正向点位')
        if not np.isfinite(args.end15cm_assembly_loss_weight) or args.end15cm_assembly_loss_weight <= 0:
            raise ValueError('assembly loss系数必须有限且大于0')
    profiles = deepcopy(args.calibration_regions)
    if args.optimization_region not in profiles:
        raise ValueError(f'未知 optimization_region={args.optimization_region!r}')
    full_segments = args.full_segmentation
    if args.optimization_region == 'full' and args.segmentation is not None:
        if getattr(args, '_full_segmentation_explicit', False) and args.segmentation != args.full_segmentation:
            raise ValueError('全长 segmentation 与 full_segmentation 分段不一致')
        full_segments = args.segmentation
    profiles['full']['segmentation'] = list(full_segments)
    selected = profiles[args.optimization_region]
    # CLI覆盖仅作用于所选区域；None表示使用区域配置。旧包缺字段时保持关闭。
    for key, fallback in (('end_weights', False), ('end_start', -5)):
        override = getattr(args, key)
        selected[key] = selected.get(key, fallback) if override is None else override
        setattr(args, key, selected[key])
    explicit_cli = set(getattr(args, '_explicit_cli_parameters', ()))
    if selected.get('sharpness') is not None and 'sharpness' not in explicit_cli:
        args.sharpness = selected['sharpness']
    if selected.get('score_window') is not None and 'min_consecutive' not in explicit_cli:
        args.min_consecutive = selected['score_window']
    root = Path(args.calibration_data_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    for profile in profiles.values():
        folder = Path(profile['folder_path'])
        if not folder.is_absolute():
            profile['folder_path'] = str(root / folder)
    for key in ('radii', 'thresholds', 'segmentation'):
        value = getattr(args, key)
        if value is not None:
            selected[key] = value
    if args.folder_path is not None:
        folder = Path(args.folder_path)
        selected['folder_path'] = str(folder if folder.is_absolute() else root / folder)
    # 显式 --weights None/--slopes None 表示重新初始化，覆盖区域保存的初值。
    for key in ('weights', 'slopes'):
        if getattr(args, key) is None and key not in getattr(args, '_explicit_seed_parameters', []):
            setattr(args, key, deepcopy(selected.get(key)))
    if getattr(args, 'optim_weights_only', False):
        explicit_seeds = set(getattr(args, '_explicit_seed_parameters', ()))
        has_package_source = getattr(args, '_sensor_package', None) is not None
        has_explicit_source = 'slopes' in explicit_seeds
        if args.slopes is None or not (has_package_source or has_explicit_source):
            raise ValueError('optim_weights_only=True 必须通过 --sensor_params 或显式 --slopes 提供slopes')
    if args.global_phases_set is None and selected.get('global_phases_set') is not None:
        args.global_phases_set = selected['global_phases_set']

    if args.interrogator == 'LUNA':
        # OFDR 不使用 FBG 预设跨度。保留全长入口，局部 FBG 区域映射不适用。
        if args.multi_region_calib or args.optimization_region != 'full':
            raise ValueError('当前区域定标配置仅支持 FiberTecc/Hippo FBG 数据')
        for key in ('folder_path', 'radii', 'thresholds', 'segmentation'):
            setattr(args, key, selected[key])
        args.ideal_len = 1.35 if args.ideal_len is None else args.ideal_len
        args.straight_trim = 0.0 if args.straight_trim is None else args.straight_trim
        args.weights, args.slopes = validate_calibration_parameters(
            args.weights, args.slopes, args.thresholds, args.segmentation, args.exp_directs,
            end_weights=args.end_weights, s_shape='S' in args.radii,
        )
        return None

    preset = args.samp_dist_preset
    if args.interlaced_grating:
        if args.samp_dist_preset_sub is None:
            raise ValueError('交错刻栅需要 samp_dist_preset_sub')
        preset = sorted(list(preset) + list(args.samp_dist_preset_sub))
    common = dict(start_value=args.start_value, end_value=args.end_value,
                  samp_dist_preset=preset, full_segmentation=full_segments,
                  profiles=profiles, multi_region_calib=args.multi_region_calib)
    context = resolve_calibration_region(optimization_region=args.optimization_region, **common)
    end5_point_calib = (getattr(args, 'end5cm_point_calib', False)
                        and args.optimization_region == 'end5cm')
    end15_point_calib = (getattr(args, 'end15cm_point_calib', False)
                         and args.optimization_region == 'end15cm')
    point_calib = end5_point_calib or end15_point_calib
    if getattr(args, 'optim_weights_only', False) and not end5_point_calib:
        raise ValueError('optim_weights_only=True 需要 end5cm_point_calib=True')
    context['calibration_objective'] = 'real_points' if point_calib else 'geometry'
    independent = (getattr(args, 'end5cm_independent_weights', False)
                   and args.optimization_region == 'end5cm')
    if (getattr(args, 'end5cm_independent_weight_score', False)
            and args.optimization_region != 'end5cm'
            and args.task not in ('recon', 'demo')
            and 'end5cm_independent_weight_score' in explicit_cli):
        raise ValueError('end5cm_independent_weight_score 仅允许 optimization_region=end5cm')
    groupwise = bool(getattr(args, 'end5cm_independent_weight_score', False)
                     and args.optimization_region == 'end5cm')
    if groupwise and not independent and args.task not in ('recon', 'demo'):
        raise ValueError('end5cm_independent_weight_score 需要 end5cm_independent_weights=True')
    coverage_configured = bool(getattr(args, 'end5cm_coverage_aware_weights', False))
    if (coverage_configured and args.optimization_region != 'end5cm'
            and args.task not in ('recon', 'demo')
            and 'end5cm_coverage_aware_weights' in explicit_cli):
        raise ValueError('end5cm_coverage_aware_weights 仅允许 optimization_region=end5cm')
    coverage_aware = coverage_configured and (
        args.optimization_region == 'end5cm' or args.task in ('recon', 'demo'))
    # Coverage-aware support selection controls which end5cm weights are free
    # during optimisation. Recon/demo consume the already-expanded 30-weight
    # package and therefore must not be constrained by the active runtime region.
    if coverage_aware and args.task not in ('recon', 'demo'):
        if not end5_point_calib:
            raise ValueError('end5cm_coverage_aware_weights 需要 end5cm_point_calib=True')
        if not independent:
            raise ValueError('end5cm_coverage_aware_weights 需要 end5cm_independent_weights=True')
        if not groupwise:
            raise ValueError('end5cm_coverage_aware_weights 需要 end5cm_independent_weight_score=True')
        if not args.soft:
            raise ValueError('end5cm_coverage_aware_weights 需要 soft=True')
        if args.end5cm_uncovered_weight_policy != 'interpolate_neutral_edges':
            raise ValueError(f'不支持的 end5cm_uncovered_weight_policy: {args.end5cm_uncovered_weight_policy!r}')
    context['end5cm_coverage_aware_weights'] = coverage_aware
    context['end5cm_min_weight_effective_samples'] = float(
        getattr(args, 'end5cm_min_weight_effective_samples', 1.0))
    context['end5cm_min_weight_max_mass'] = float(
        getattr(args, 'end5cm_min_weight_max_mass', 0.05))
    context['end5cm_uncovered_weight_policy'] = getattr(
        args, 'end5cm_uncovered_weight_policy', 'interpolate_neutral_edges')
    context['weight_group_ids'] = None
    if independent:
        point_ids = context['global_point_ids']

        if args.reverse or point_ids not in (
            [19,20,21,22],
            [18,19,20,21,22],
        ):
            raise ValueError('end5cm三组weights要求正向真实点19–22或18–22')

        if not args.end_weights:
            raise ValueError('end5cm三组weights需要该区域end_weights=True')

        context['weight_group_ids'] = [0] * (len(point_ids) - 2) + [1,2]
    configured_mode = selected.get('weight_score_mode')
    if 'end5cm_independent_weight_score' in explicit_cli:
        configured_mode = 'group_mean' if groupwise and independent else 'spatial_window'
    elif configured_mode is None:
        configured_mode = 'group_mean' if groupwise and independent else 'spatial_window'
    if configured_mode not in ('spatial_window', 'group_mean'):
        raise ValueError(f'weight_score_mode 不合法: {configured_mode!r}')
    if configured_mode == 'group_mean' and context['weight_group_ids'] is None:
        raise ValueError('weight_score_mode=group_mean 需要 end5cm_independent_weights=True')
    context['weight_score_mode'] = configured_mode
    args._resolved_weight_group_ids = context['weight_group_ids']
    if point_calib:
        if set(context['radii']) != {'circ'}:
            raise ValueError(f'{args.optimization_region}真实点定标目前仅支持circ圆弧数据')
        radii = np.asarray(context['radii']['circ'], dtype=float)
        if not np.all(np.isfinite(radii)) or np.any(radii < 0) or not np.any(radii > 0):
            raise ValueError(f'{args.optimization_region}真实点定标需要有限正半径；0仅表示直线状态')
    if args.multi_region_calib:
        # 开启区域模式时，所有已配置长度都必须与同一全长分段相容。
        for region in profiles:
            resolve_calibration_region(optimization_region=region, **common)
    for key in ('ideal_len', 'straight_trim'):
        supplied = getattr(args, key)
        if supplied is not None and not np.isclose(supplied, context[key], rtol=0, atol=1e-12):
            raise ValueError(f'{key}={supplied} 与所选区域的几何计算值 {context[key]} 不一致')
    for key in ('ideal_len', 'folder_path', 'radii', 'thresholds', 'straight_trim', 'segmentation'):
        setattr(args, key, context[key])
    if args.reverse:
        # Sensor 裁剪后才反序：空间段顺序也必须反转，才能保留全局对应。
        args.segmentation = args.segmentation[::-1]
        context['segmentation'] = args.segmentation
        for key in ('global_point_ids', 'global_segment_ids', 'global_sample_dist_m'):
            context[key] = context[key][::-1]
        samples = np.asarray(context['sample_dist_m'])
        context['sample_dist_m'] = ((samples[-1] - samples)[::-1] + args.end_value / 1000).tolist()
        # 当前反向路径仅在起点补虚拟点，不延伸反向终点。
        context['reconstruction_length_m'] = context['sample_dist_m'][-1]
    args.weights, args.slopes = validate_calibration_parameters(
        args.weights, args.slopes, args.thresholds, args.segmentation, args.exp_directs,
        end_weights=args.end_weights, s_shape='S' in args.radii,
        weight_group_ids=context['weight_group_ids'],
    )
    print(f'定标区域: {args.optimization_region}; ideal_len={args.ideal_len:.6f} m; '
          f'全局真实点={context["global_point_ids"]}; segmentation={args.segmentation}')
    return context



def compute_error_ang(optim, vis, init):
    errs = {}
    for direct in optim.exp_directs:
        optim.direct = direct
        rs = {}
        for calib_shape in optim.calib_shapes:
            r_results_postrot, interp_dist = optim.reconstruct_shapes(calib_shape=calib_shape, direct=direct, verbose=False)
            rs[calib_shape] = r_results_postrot
        optim._compute_error(interp_dist=interp_dist, rs=rs)
        errs[direct] = optim.avg_point_err['calib'] + optim.k_end * optim.avg_end_err['calib'] + optim.k_pitch * optim.avg_pitch_err

        if init:
            print(f"---------- {direct}方向初始化完成 ----------")
            vis.init_visualise(direct=direct)
            vis.show_reconstruction(direct=direct, rs=rs, interp_dist=interp_dist, showanime=True)
            optim._print_errors()
    return errs
        
def optim_ang(rot_ang, ang_step, ang_range, optim, vis):
    # 计算初始误差并绘制初始图像
    prev_errs = compute_error_ang(optim=optim, vis=vis, init=False)

    print(f"---------- 旋转角度优化开始 ----------")
    start = time.time()
    best_rot_ang = rot_ang
    for ang in np.arange(rot_ang - ang_range, rot_ang + ang_range, ang_step):
        optim.rot_ang = ang
        ang_errs = compute_error_ang(optim=optim, vis=None, init=False)
        if sum([ang_errs[direct] for direct in ang_errs]) < sum([prev_errs[direct] for direct in prev_errs]):
            best_rot_ang = ang
            prev_errs = ang_errs
    end = time.time()
    print(f"---------- 旋转角度优化完成 ----------")
    print(f"优化耗时: {end - start}")
    print(f"最优旋转角度: {best_rot_ang}")
    print(f"最小误差: {prev_errs}")

    return prev_errs

def _str2bool(v):
    """argparse 布尔取值：显式支持 True/False，避免 type=bool 时 'False' 被当成 True 的陷阱。"""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('true', '1', 'yes')


def _finite_nonnegative_float(value):
    number = float(value)
    if not np.isfinite(number) or number < 0.0:
        raise argparse.ArgumentTypeError("must be a finite nonnegative value")
    return number


def add_vector_filter_arguments(parser):
    """注册向量方向空间滤波开关，供主入口及轻量参数测试共用。"""
    parser.add_argument(
        '--move_filter_for_vector',
        type=_str2bool,
        default=True,
        help='向量曲率插值前是否启用空间方向窗口滤波；默认False，直接插值原始kx/ky',
    )
    return parser


def add_anchor_arguments(parser):
    """Register startup settings for the protocol-independent entrance anchor."""
    class _EnableFullAnchor(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, True)
            setattr(namespace, 'anchor_translation_enabled', True)
            setattr(namespace, 'anchor_rotation_enabled', True)

    parser.add_argument(
        '--anchor_translation_enabled',
        action='store_true',
        help='启用入口位置平移锚定，将当前入口点平移到首帧固定入口坐标',
    )
    parser.add_argument(
        '--anchor_rotation_enabled',
        action='store_true',
        help='启用入口姿态旋转锚定，使当前入口T/Y/Z与首帧入口标架对齐',
    )
    parser.add_argument(
        '--anchor_constraint_enabled',
        action=_EnableFullAnchor,
        nargs=0,
        help='兼容旧参数：同时启用入口平移锚定和旋转锚定',
    )
    parser.add_argument(
        '--anchor_offset_m',
        type=_finite_nonnegative_float,
        default=0.06,
        help='末端到主隆突/支气管入口的初始距离，单位为m；运行中可通过进程接口修改',
    )
    return parser


class _StoreCalibrationParameter(argparse.Action):
    """区分未传初值与显式传入 None，保证旧命令仍可强制重新初始化。"""
    def __call__(self, parser, namespace, values, option_string=None):
        """保存 weights/slopes，并记录该初值由命令行显式提供。"""
        setattr(namespace, self.dest, values)
        explicit = list(getattr(namespace, '_explicit_seed_parameters', []))
        explicit.append(self.dest)
        namespace._explicit_seed_parameters = explicit


class _StoreFullSegmentation(argparse.Action):
    """记录全长分段是否由命令行显式给出，而非仅采用传感器默认值。"""
    def __call__(self, parser, namespace, values, option_string=None):
        """保存全长分段，并设置显式覆盖标记供区域一致性校验使用。"""
        setattr(namespace, self.dest, values)
        namespace._full_segmentation_explicit = True


def build_argument_parser():
    """创建主程序参数解析器，集中定义硬件、定标、优化和展示参数。"""
# ---------- 初始化 ----------
    parser = argparse.ArgumentParser()
    # 以下区域配置也属于传感器参数；复制整个 parser 区块即可保留、迁移。
    parser.add_argument('--end15cm_assembly_loss', type=_str2bool, default=False,
                        help='独立end15cm：在真实点slopes目标中加入全长实测拼接损失')
    parser.add_argument('--end15cm_assembly_loss_weight', type=float, default=1.0,
                        help='拼接平方几何损失系数，仅试验使用')
    parser.add_argument('--sensor_params', type=str, default=None,
                        help='有序传感器参数包 JSON；显式 CLI 参数优先')
    parser.add_argument('--use_full_transported_phase', type=_str2bool, default=False,
                        help='局部优化使用非零弯曲状态的固定上游相位；区域跨界固定使用full第0档slope')
    parser.add_argument('--end15cm_point_calib', type=_str2bool, default=True,
                        help='仅end15cm：使用真实点方向一致性优化slopes、已知半径曲率优化weights；默认沿用几何优化')
    parser.add_argument('--end5cm_point_calib', type=_str2bool, default=True,
                        help='仅end5cm：固定区域相位后优化真实点方向一致性，再按真实radii优化曲率幅值；默认沿用几何优化')
    parser.add_argument('--end5cm_independent_weights', type=_str2bool, default=True,
                        help='仅end5cm：19–20普通组、21独立组、22独立组；weights为三组，旧布局默认不变')
    parser.add_argument('--end5cm_independent_weight_score', '--end5cm_groupwise_weight_score',
                        dest='end5cm_independent_weight_score', type=_str2bool, default=True,
                        help='仅end5cm独立三组weights：19–20用组内base曲率均值，21/22各自评分；旧groupwise名称为兼容别名')
    parser.add_argument('--end5cm_coverage_aware_weights', type=_str2bool, default=True,
                        help='仅end5cm真实点+独立组均值评分：只优化有实测覆盖的weight档位，其他档位由相邻自由档位对数插值')
    parser.add_argument('--end5cm_min_weight_effective_samples', type=_finite_nonnegative_float, default=1.0,
                        help='coverage-aware weight档位的最小有效样本数')
    parser.add_argument('--end5cm_min_weight_max_mass', type=_finite_nonnegative_float, default=0.05,
                        help='coverage-aware weight档位的最小最大组质量')
    parser.add_argument('--end5cm_uncovered_weight_policy', type=str,
                        choices=['interpolate_neutral_edges'], default='interpolate_neutral_edges',
                        help='coverage-aware weight未覆盖档位的派生策略')
    parser.add_argument('--optim_weights_only', type=_str2bool, default=False,
                        help='只优化weights并固定继承的slopes；必须来自sensor_params或显式--slopes')
    parser.add_argument('--multi_region_calib', type=_str2bool, default=False,
                        help='True时optim/score遍历optimization_regions；False时仅全长')
    parser.add_argument('--optimization_region', type=str, default='full',
                        help='init/recon/demo等单区域任务使用的数据区域')
    parser.add_argument('--optimization_regions', type=ast.literal_eval, default=['full', 'end15cm', 'end5cm'],
                        help='区域模式下optim/score依次处理的区域列表')
    parser.add_argument('--full_segmentation', type=ast.literal_eval, action=_StoreFullSegmentation,
                        default=[2,2,3,2,4,2,2,3,2],
                        help='全长真实点分段列表；局部区域必须由其完整空间段组成')
    parser.add_argument('--calibration_data_root', type=str, default="./09B7",
                        help='定标数据根目录；相对路径以main.py所在目录为基准')
    parser.add_argument('--calibration_regions', type=ast.literal_eval, default={
        'full': {
            'length_m': None,
            'folder_path': '全段测试',
            'radii': {'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200]},
            'thresholds': [0.8, 1.2, 2.0, 3.0, 4.0],
            'end_weights': False, 'end_start': -5,
            'weights': None, 'slopes': None,
        },
        'end15cm': {
            'length_m': 0.15,
            'folder_path': '末端测试/15cm',
            'radii': {'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200, 100, 75, 50, 30]},
            'thresholds': [0.8, 1.2, 2.0, 3.0, 4.0, 10.0, 20.0, 33.0],
            'end_weights': False, 'end_start': -5,
            'segmentation': [2, 3, 2],
            'weights': None, 'slopes': None,
        },
        'end5cm': {
            'length_m': 0.05,
            'folder_path': '末端测试/5cm',
            'radii': {'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200, 100, 75, 50, 30, 20, 15]},
            # score(0/120/240) 显示 20/15 mm 在 35 m^-1 最高档饱和；
            # 45 m^-1 用于下一轮重新优化，不得与旧 9 组参数混用。
            'thresholds': [0.8, 1.2, 2.0, 3.0, 4.0, 10.0, 20.0, 35.0, 45.0, 70.0],
            'end_weights': True, 'end_start': -1,
            'segmentation': [3, 2],
            'weights': None, 'slopes': None,
        },
    }, help='各区域独立配置；阈值暂保留旧值，可先通过task score检查实际评分分布')
    parser.add_argument('--calibration_output_dir', type=str, default='calibration_results',
                        help='批量优化/评分诊断输出目录，按传感器、本地时间和优化角度创建新目录')
    # 硬件参数
    parser.add_argument('--sensor_id', type=str, default='09B7', help='传感器编号')
    parser.add_argument('--start_value', type=float, default=19.0, help='传感器第一个传感点到固定件的距离, 单位为mm')
    parser.add_argument('--end_value', type=float, default=6.0, help='传感器最后一个传感点到末端的距离, 单位为mm')
    # parser.add_argument('--R', type=float, default=0.235e-3, help='传感器半径, 单位为m') #肠镜
    parser.add_argument('--R', type=float, default=0.1e-3, help='传感器半径, 单位为m') # 支气管镜
    parser.add_argument('--ideal_len', type=float, default=None, help='FBG总长自动计算(m)；显式传值必须与几何一致')
    # parser.add_argument('--ideal_len', type=float, default=1.35, help='传感器长度, 单位为m') #肠镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 540, 570, 630, 710, 810, 910, 1010, 1110, 1210, 1310, 1410, 1510, 1610, 1710, 1815], help='FBG传感点位置(A组及中心), 单位为mm') #肠镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 520, 530, 540, 550, 580, 610, 640, 670, 720, 770, 850, 930, 1010, 1110, 1230], help='FBG传感点位置, 单位为mm')# 16点支气管镜
    parser.add_argument('--samp_dist_preset', type=ast.literal_eval, default=[510, 521, 532, 543, 554, 588, 622, 656, 707, 758, 809, 860, 911, 962, 1013, 1064, 1115, 1166, 1217, 1268, 1319, 1370], help='FBG传感点位置, 单位为mm')# 22点支气管镜
    # parser.add_argument('--samp_dist_preset', type=ast.literal_eval, default=[510, 521, 533, 543, 577, 611, 645, 696, 746, 797, 847, 899, 950, 1001, 1053, 1104, 1155, 1207, 1257, 1308, 1359, 1410], help='FBG传感点位置, 单位为mm')# 22点支气管镜位置错误版本
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 521, 532, 543, 554, 579, 604, 629, 654, 696, 738, 780, 822, 864, 906, 948, 990, 1032, 1074, 1116, 1158, 1200], help='FBG传感点位置, 单位为mm')# 22点支气管镜，69cm
    parser.add_argument('--samp_dist_preset_sub', type=ast.literal_eval, default=[120, 160, 200, 295, 445, 595, 745, 895], help='FBG传感点位置(B组), 单位为mm')
    parser.add_argument('--centre_fibre', type=bool, default=True, help='是否为1+x构型')
    parser.add_argument('--interlaced_grating', type=bool, default=False, help='栅区是否交错排列')
    parser.add_argument('--interlaced_offset', type=float, default=np.pi/3, help='交错排列时的角度偏移，单位为度')
    # parser.add_argument('--global_phases_set', type=float, default=-0.20541970186130923, help='全局相位，初始值为None') #全段相位
    parser.add_argument('--global_phases_set', type=float, default=None, help='全局相位，初始值为None')
    # 标定实验参数
    parser.add_argument('--interrogator', type=str, default='FiberTecc', choices=['FiberTecc', 'Hippo', 'LUNA'], help='解调仪器')
    parser.add_argument('--active_channels', type=list, default=[1,2,3,4], help='传感器连接解调仪的通道以及其顺序')
    parser.add_argument('--channel_change', type=bool, default=False, help='通道排布是否变化')
    parser.add_argument('--channel_layout', type=list, default=[(5, [2, 1, 4, 3, 7, 5, 6]), (7, [5, 1, 4, 3, 2, 7, 6]), (4, [7, 1, 4, 3, 2, 5, 6])], help='当通道排布出现错序，每一段的长度及其排布顺序(列表嵌套元组格式)')
    parser.add_argument('--active_angles', type=list, default=None, help='外围通道角度排布(度数)，若为None则默认均匀排布')
    # parser.add_argument('--folder_path', type=str, default="./0908-06B6/全段测试", help='数据存储路径')
    # parser.add_argument('--folder_path', type=str, default="./0908-06B6/末端测试/15cm", help='数据存储路径')
    parser.add_argument('--folder_path', type=str, default=None, help='覆盖所选区域的数据目录；默认由 calibration_regions 提供')
    parser.add_argument('--rot_dir', type=list, default={0:-1,120:-1,240:-1}, help='各个标定实验按逆(1)还是顺(-1)顺时针调整的方向')
    parser.add_argument('--exp_directs', type=ast.literal_eval, default=[0, 120, 240],
                        help='实验使用的字面方向角列表，如[0]或[0,120,240]；单区域recon默认只使用direct')
    # parser.add_argument('--radii', type=list, default={'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200]}, help='标定圆弧形状半径')
    # parser.add_argument('--radii', type=list, default={'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200, 100, 75, 50, 30]}, help='标定圆弧形状半径')
    parser.add_argument('--radii', type=ast.literal_eval, default=None, help='覆盖所选区域半径字典(mm)')
    parser.add_argument('--end_len', type=float, default=0.05, help='end形状中进入末端大曲率弧圈的包含长度')
    # 优化使用的超参数
    parser.add_argument('--direct', type=int, default=0, help='优化曲率权重与扭转系数的标定方向')
    parser.add_argument('--freeze', type=list, default=None, help='冻结部分分区的参数，使得它们不参与优化。如果不需要冻结则调整为None。分区index从0开始。')
    parser.add_argument('--weight_bounds', type=ast.literal_eval, default=(0.6, 5.0), help='曲率权重范围')
    parser.add_argument('--slope_upper_bound', type=float, default=50.0, help='扭转系数大小上限')
    parser.add_argument('--thresholds', type=ast.literal_eval, default=None, help='覆盖所选区域曲率阈值列表(m^-1)')

    parser.add_argument('--max_iter', type=int, default=20, help='优化的最大轮次')
    parser.add_argument('--k_point', type=float, default=1.0, help='优化目标中末端误差的权重')
    parser.add_argument('--k_end', type=float, default=0.5, help='优化目标中末端误差的权重')
    parser.add_argument('--k_pitch', type=float, default=1.0, help='优化目标中螺距误差的权重')
    parser.add_argument('--k_radius', type=float, default=1.0, help='优化目标中半径误差的权重')
    parser.add_argument('--method', type=str, default="Powell", help='优化算法, 用于输入scipy.optimize.minimimze')
    parser.add_argument('--hyper_params', type=dict, default=[20000, 1e-6, 1e-6], help='优化算法使用的超参数')
    parser.add_argument('--min_loss_diff', type=float, default=1e-4, help='收敛判定')
    parser.add_argument('--ss', type=float, default=2.6e-3, help='LUNA传感点间隔, 单位为m')
    # 动态展示参数
    parser.add_argument('--IP', type=str, default='192.168.1.75', choices=['192.168.1.75', '10.0.0.122'], help='FiberTecc使用192.168.1.75, Hippo使用10.0.0.122')
    parser.add_argument('--PORT', type=int, default=26546, choices=[26546, 4010], help='FiberTecc使用26546, Hippo使用4010')
    parser.add_argument('--maxsize', type=int, default=10, choices=[10, 2], help='FiberTecc使用10, Hippo使用2')
    parser.add_argument('--data_freq', type=int, default=100, help='解调仪频率')
    parser.add_argument('--use_stored_zero', type=_str2bool, default=True, help='demo 是否使用文件中的绝对波长零状态；False 时使用首帧归零')
    parser.add_argument('--zero_reference_path', type=str, default='./params/06B6_NeTi_v2_ftube_zero_reference.json', help='统一零状态 JSON 文件路径，文件中的 SensorID、通道及栅点数必须与当前配置一致')
    parser.add_argument('--wavelength_jump_guard_enabled', type=_str2bool, default=True,
                        help='启用逐 FBG 跨帧波长连续性检查（True/False；默认开启）')
    parser.add_argument('--wavelength_jump_threshold_pm', type=float, default=12000.0,
                        help='逐 FBG 跨帧波长跳变阈值，单位 pm；超过阈值的单帧跳变先安全保持，默认 12000 pm')
    parser.add_argument('--total_scale', type=float, default=1.0, help='动态显示大小')
    parser.add_argument('--imu', type=bool, default=False, help='是否启用IMU')
    parser.add_argument('--imu_com', type=str, default='COM6', help='IMU接口')
    parser.add_argument('--imu_maxlen', type=int, default=10)
    parser.add_argument('--demo_recorder', type=bool, default=True, help='是否在动态展示时记录数据')
    parser.add_argument('--unwrap_threshold', type=float, default=0.65, help='若两帧同一点角度变化小于该阈值，则统一unwrap方向')
    parser.add_argument('--align_threshold', type=float, default=0.20, help='若某帧第一点角度变化小于该阈值，则将第一点角度与上一帧对齐')
    parser.add_argument('--direction_blend_enabled', action='store_true', help='动态展示中启用0/120/240度参数半余弦软过渡；应在rot_ang确定后再打开')
    parser.add_argument('--direction_reference_direct', type=int, default=240, choices=[0, 120, 240], help='动态第一遍方向估计及关闭软过渡时使用的最高精度参数方向')
    parser.add_argument('--direction_min_curvature', type=float, default=0.5, help='动态方向估计的有效弯曲点最小曲率，低于该值时冻结上一帧方向质量')
    parser.add_argument('--direction_min_consecutive', type=int, default=3, help='动态方向估计中近端稳定弯曲区要求的最少连续点数')
    parser.add_argument('--direction_consistency_threshold', type=float, default=0.6, help='曲率加权圆周平均的最小方向一致性，低于该值时冻结上一帧方向质量')
    parser.add_argument('--direction_smooth_alpha', type=float, default=0.15, help='动态方向质量跨帧指数平滑系数，范围(0,1]')
    parser.add_argument('--demo_kalman_enabled', type=_str2bool, default=True, help='动态展示中对插值后的局部曲率向量启用跨帧卡尔曼滤波（True开启，开启后替代原有的curve_history滑动平均；False关闭）')
    parser.add_argument('--demo_kalman_Rk', type=float, default=1e-4, help='局部曲率向量跨帧卡尔曼观测噪声参数，越大越平滑、响应越慢；保持默认 1e-4')
    parser.add_argument('--demo_kalman_Bk', type=float, default=1e-5, help='局部曲率向量跨帧卡尔曼状态转移误差参数，越大对新观测响应越快；保持默认 1e-5')
    add_anchor_arguments(parser)
    # 动态样机展示相关参数
    # parser.add_argument('--body_model_path', type=str, default="./model.stl", help='人体STL模型路径')
    # parser.add_argument('--entry_length_cm', type=float, default=0.0, help='初始手动入体长度，单位cm')
    # parser.add_argument('--max_curvature', type=float, default=2.3, help='曲率入口识别阈值')
    # parser.add_argument('--back_num', type=int, default=8, help='曲率入口识别后向前回退的点数')
    # parser.add_argument('--entry_exclude', type=int, default=20, help='曲率入口识别时忽略前若干点')
    # parser.add_argument('--enable_t_align', type=bool, default=True, help='是否启用入口T向量对齐')
    # parser.add_argument('--t2_smooth_window', type=int, default=3, help='入口T向量滤波窗口大小')
    # parser.add_argument('--clip_pct', type=float, default=0.38, help='显示人体模型时的帧间位移截断比例')
    # parser.add_argument('--clip_k', type=float, default=3.0, help='显示人体模型时的帧间位移截断倍率')
    # parser.add_argument('--still_rms_th', type=float, default=0.05, help='静止冻结的RMS位移阈值')
    # parser.add_argument('--still_hold_frames', type=int, default=10, help='触发静止冻结所需连续帧数')
    # 重构使用的超参数
    parser.add_argument('--soft', type=bool, default=True, help='是否使用软化判定')
    parser.add_argument('--reverse', type=bool, default=False, help='是否反向重构')
    parser.add_argument('--discont', type=float, default=np.pi, help='np.unwrap跳变判断阈值')
    parser.add_argument('--frame_rule', type=str, default='TNN', choices=['TNB', 'TNN'], help="选择使用FS标架还是平行传递标架")
    parser.add_argument('--straight_threshold', type=float, default=2.0, help='零螺距形状中判断直线段的曲率阈值')
    parser.add_argument('--rot_threshold', type=float, default=4.0, help='零螺距形状中判断螺旋段的曲率阈值')
    parser.add_argument('--min_consecutive', type=int, default=3, help='曲率分级判定前平滑滤波窗口大小')
    parser.add_argument('--move_filter', type=int, default=3, help='动/静态重构前平滑滤波窗口大小')
    add_vector_filter_arguments(parser)
    parser.add_argument('--kalman_params', type=dict, default={'angle': {'Rk': 0.001, 'Bk': 0.001}, 'magnitude': {'Rk': 0.0001, 'Bk': 0.01}}, help='卡尔曼滤波参数')
    parser.add_argument('--smoothing_params', type=dict, default={'window_length': 21,'polyorder': 3}, help='LUNA数据平滑参数')
    parser.add_argument('--interp_num', type=int, default=120, help='插值目标点数')
    parser.add_argument(
        '--curvature_interp',
        type=str,
        default='vector_pchip',
        choices=['hermite', 'pchip', 'scalar_pchip', 'vector_linear', 'vector_pchip'],
        help=(
            '曲率空间插值方法：hermite为原始基线；pchip是scalar_pchip的兼容别名；'
            'vector_linear/vector_pchip分别对曲率向量分量做线性/PCHIP插值'
        ),
    )
    parser.add_argument('--nonnegative_curvature', action='store_true', help='对插值后的曲率施加非负约束')
    parser.add_argument('--sharpness', type=float, default=4.8, help='sigmoid软评分硬度')
    # parser.add_argument('--end_weights', type=bool, default=False, help='是否对末端另算权重') #肉眼看穿过标准圆圈的点数（前后段weight不一致），然后在直线段看见的点数来判断在距离多少（旁边有格尺），然后回到init图中看看离末端有几个fbg（例如9个），那就在下面'--end_start', type=int, default=-6, help='末端起点')这里改成-9
    parser.add_argument('--end_weights', type=_str2bool, default=None, help='覆盖所选区域末端权重开关；默认使用calibration_regions')
    parser.add_argument('--end_start', type=int, default=None, help='覆盖所选区域末端起点负索引；仅计真实点')
    parser.add_argument('--TNB_threshold', type=float, default=0.0, help='TNB重构直线判定阈值')
    # 初始化时必须手动调整的超参数
    parser.add_argument('--straight_trim', type=float, default=None, help='由优化区域长度计算；显式值必须一致')
    # parser.add_argument('--segmentation', type=list, default=[2, 3, 5, 2, 3, 7], help='对扭转角度-传感点位置曲线的点数')#优先调分段
    # parser.add_argument('--segmentation', type=list, default=[2, 2, 3], help='对扭转角度-传感点位置曲线的点数')#末端15cm
    # parser.add_argument('--segmentation', type=list, default=[2, 3, 5, 2, 3, 2, 2, 3], help='对扭转角度-传感点位置曲线的点数')#优先调分段
    parser.add_argument('--segmentation', type=ast.literal_eval, default=None, help='所选区域分段，必须与全长对应空间段相同')
    # parser.add_argument('--segmentation', type=list, default=[2, 3, 5, 2, 3, 2, 5], help='对扭转角度-传感点位置曲线的点数')#优先调分段
    parser.add_argument('--connect', type=bool, default=False, help='拟合初始分段时是否令各分段首尾相连')
    parser.add_argument('--turn_threshold', type=float, default=2.0, help='判断形状弯曲方向是否改变的阈值')
    parser.add_argument('--sensing_ranges', type=dict, default={1: (583, 1048), 3: (678, 1146), 4: (749, 1215)}, help='LUNA各通道使用的传感点范围')
    # 角度优化初始值
    # parser.add_argument('--rot_ang', type=float, default=-30, help='绕x轴旋转角度, 初始为0.0')  #动态上机角度
    # parser.add_argument('--rot_ang', type=float, default=31.8, help='绕x轴旋转角度, 初始为0.0')
    parser.add_argument('--rot_ang', type=float, default=0, help='绕x轴旋转角度, 初始为0.0')
    # ===============================不带窗======================================
    # # 曲率权重与扭转系数相关初始值, 曲率向量插值, 全段参数, 不带窗, 末端调weight
    # parser.add_argument('--weights', default={0: np.array([0.769604441191232, 0.8609085601489306, 0.8629575251635755, 0.8879480275090127, 0.8882273817193517, 0.923250790081014, 0.10000062686770492, 4.547478524913153, 1.022984574255862, 1.9443742771509285, 1.642872707914389, 1.4723019459684745]), 
    #                                                       120: np.array([0.8834070763118534, 0.85251461024247, 0.986924957649386, 0.9452724668609392, 0.9725634153903076, 0.9499982676616073, 0.2974572176118146, 2.364679449655484, 0.10000000152172318, 1.0604064407338645, 0.44551347690428705, 0.8243089591676417]), 
    #                                                       240: np.array([0.7867436848812638, 0.9969041223121436, 0.8298518879670551, 1.1115326395320613, 0.5702994386370039, 1.5798283235946788, 3.400371328236248, 0.10000062173304661, 2.231475970279864, 0.4183739322611567, 1.8996450745922804, 0.953123821823926])}, help='曲率权重')
    # parser.add_argument('--slopes', default={0: np.array([[-17.361934010361534, -8.82238254566271, 7.207829434831414, -9.595849723933986, 14.62280505053963, 22.792119944827345, 34.63000410782396, -49.99996678126025], [-11.466844544774519, -9.542111645281352, 7.473971848619946, -9.574458003913163, 12.765503948305406, -30.32781318509315, -21.489108292265627, -49.99996678126025], [-11.177337608667585, -10.613413137393325, 7.344066858002307, -8.353171259486155, 11.530895595951453, 8.133686858720994, 14.603601985527936, -49.99996678126025], [-14.076504600793399, -8.6827846514447, 7.2807790354324995, -9.37176595282542, 12.118638136057404, -1.5131516974382306, 14.264218129781927, -49.99996678126025], [-14.08705663876613, -9.36395608794576, 7.164849583091598, -8.685413809522705, 12.02135620905823, -0.20583722175423258, 11.876897682867167, -49.99996678126025], [-15.93521219355464, -8.439348289171864, 7.418592922967558, -9.260429966030355, 11.716247954097707, 0.37765461259160993, 12.872813578701445, -11.372883465593455]]), 
    #                                                     120: np.array([[-12.828408552287456, -9.660210787817029, 7.630721934225222, -8.316378424133006, 12.236550095184619, -2.11845516753808, 4.292688546499804, -49.99996678126025], [-19.017298802057717, -8.283278169308197, 6.84716400284566, -7.810189078511994, 10.897955534508188, 4.31129970066748, 18.252710691946287, -49.99996678126025], [-10.379083471278523, -10.499107406535098, 8.140460016747564, -10.060627404919888, 12.115878315219163, -0.32677593994438586, 18.381835450609323, 37.27395612992368], [-17.262023839969302, -9.271997381518112, 7.191153873790344, -8.464842710567064, 11.45512337608043, 2.6066960851053635, -5.461988110978801, -49.99996678126025], [-11.394338619612483, -10.205125424779862, 8.139901885790902, -10.248509615140962, 12.169985962386189, 1.2800595891063282, 16.32310983367443, 0.700059917491817], [-18.831696568554584, -8.874357643498374, 7.399052192216785, -8.757061443787114, 11.474403534989582, 2.7496901433051244, 10.509198644192884, -49.99996678126025]]),
    #                                                                   240: np.array([[-15.753437734255483, -7.492630557400586, 6.82487052400456, -6.8520500684282375, 8.83024792338105, 1.212951049305152, -41.57405355972927, 22.964181519257913], [-20.66799438844964, -6.776705896728184, 5.63496372120728, -7.163143253184144, 12.5093612759363, 2.1380952602362466, 65.76230411056459, 65.76229958173887], [-15.712141723954192, -7.706921023867793, 7.398354249496547, -8.36463954191213, 10.36247070157027, 1.700805506504947, -19.981830727317664, 65.76229958173887], [-15.345600369190322, -8.181994005709742, 4.255236139128114, -5.782931675570792, 10.901804326393206, 3.8229293012945336, 10.828218342063177, -65.76229958173887], [-15.577545930269098, -7.171362441835742, 14.180824405901827, -11.472368985281506, 10.711070932314414, 2.816920692241342, -4.005981333883456, -65.76229958173887], [-12.76053019437769, -9.686897178718416, -22.267853719660234, 5.292893501952441, 8.507735902044905, 5.538954429081346, 6.1033067320378915, 65.76229958173887]])}, help='扭转系数')
    # # 曲率权重与扭转系数相关初始值, 曲率向量插值, 不带窗, 15cm
    # parser.add_argument('--weights', default={0: np.array([1.9604606143354646, 0.7484982315455317, 0.7576778315763791, 1.0983414309980577, 0.8497160917055625, 0.9575616794202598]), 
    #                                                           120: np.array([1.0491833576658416, 0.4217299264915794, 1.1247458231243672, 0.7673906124650715, 0.7825216051165368, 0.8973279211845339]), 
    #                                                           240: np.array([0.39350565350589717, 3.202594405377135, 0.9841428904670104, 0.7044141486352334, 1.0446691739828895, 0.9604685665349445])}, help='曲率权重')
    # parser.add_argument('--slopes', default={0: np.array([
    # [47.90778065030887, -4.582170240463005, -91.64943459619103], 
    # [37.323927731433486, -43.2979459870466, -91.64943459619103], 
    # [-2.255392722267323, 32.1547638847326, -15.457689899568509], 
    # [16.57276789843122, -0.5147171395048441, -91.64943459619103], 
    # [3.5325020008558807, 25.892801016455977, -91.64943459619103], 
    # [1.269843025805914, 14.625902847259198, -31.787662859088524]]), 
    #                                                         120: np.array([
    # [49.99996678126025, -49.99996678126025, -25.334326484801107], 
    # [49.99996678126025, -49.99996678126025, -49.99996678126025], 
    # [-7.9984669300057165, -3.599333917493265, -49.99996678126025], 
    # [19.579722624670005, -7.494459234565948, -49.99996678126025], 
    # [7.123911239837365, -7.195938619193081, -49.99996678126025], 
    # [1.4846251148964162, 10.216438067446596, -27.15908669125657]]),
    #                                                                       240: np.array([
    # [16.3556019396367, -17.023575263528258, -33.951741995792304], 
    # [49.99996678126025, -19.382936593069093, -49.99996678126025], 
    # [1.151912126695345, 10.539655479129028, 10.629349965296365], 
    # [25.255485433375302, -21.424664569673933, -49.99996678126025], 
    # [-3.9152431142714064, 29.28640869533861, -49.99996678126025], 
    # [26.30525541308219, 11.520823752630669, -15.23477938406701]])}, help='扭转系数')

    # 曲率权重与扭转系数相关初始值, 曲率向量插值, 不带窗, 5cm
    # parser.add_argument('--weights', default={0: np.array([1.553407546131768, 0.6000005582908989, 1.9183242010029995, 0.6000004670227347, 0.6216559685516176, 1.596270023444882]), 
    #                                                               120: np.array([0.6000005582908392, 0.6000005582908392, 0.6000005582908392, 0.6000005582908392, 0.6000000000002461, 1.2693399508811423]), 
    #                                                               240: np.array([1.274133095311955, 1.3903603998788605, 0.6000005583028791, 1.5309897399643118, 0.6000005583028792, 1.5504596861327944])}, help='曲率权重')
    parser.add_argument('--weights', type=ast.literal_eval, action=_StoreCalibrationParameter, default=None, help='所选区域已定标权重；None表示重新初始化')
    # parser.add_argument('--slopes', default={0: np.array([[-82.30284714775718, -82.30284714775718], [82.30290022121412, -82.30284714775709], [-82.30284714775718, -82.30284714775718], [52.14041053619512, -82.30284714775718], [-82.30284714775718, 50.78023258070863], [-82.30284714775718, -24.85696313654812]]), 
    #                                                             120: np.array([[49.99999985683793, -49.999966781260134], [-28.019167865012612, -49.99996678126025], [-6.124846724061082, -49.99996678126025], [-49.999994927442934, -49.99996678126025], [-49.99996678126025, -49.99996678126025], [-49.99996678053954, -49.99996678126025]]),
    #                                                                           240: np.array([[-49.99996678126025, -21.65933609449623], [-49.99996678126025, -25.847530761739417], [-49.99996678126025, -49.99996678126025], [-49.99996678126025, -49.99996678126025], [-49.99996678126025, -49.99996678175147], [49.99996678126025, 3.652742029815776]])}, help='扭转系数')
    parser.add_argument('--slopes', type=ast.literal_eval, action=_StoreCalibrationParameter, default=None, help='所选区域已定标扭转参数；None表示重新初始化')

    # # 曲率权重与扭转系数相关初始值, 曲率向量插值, 全段参数, 不带窗, combined
    # parser.add_argument('--weights', default={0: np.array([0.769604441191232, 0.8609085601489306, 0.8629575251635755, 0.8879480275090127, 0.8882273817193517, 0.923250790081014, 1.9604606143354646, 0.7484982315455317, 0.7576778315763791, 1.0983414309980577, 0.8497160917055625, 0.9575616794202598]), 
    #                                                           120: np.array([0.8834070763118534, 0.85251461024247, 0.986924957649386, 0.9452724668609392, 0.9725634153903076, 0.9499982676616073, 1.0491833576658416, 0.4217299264915794, 1.1247458231243672, 0.7673906124650715, 0.7825216051165368, 0.8973279211845339]), 
    #                                                           240: np.array([0.7867436848812638, 0.9969041223121436, 0.8298518879670551, 1.1115326395320613, 0.5702994386370039, 1.5798283235946788, 0.39350565350589717, 3.202594405377135, 0.9841428904670104, 0.7044141486352334, 1.0446691739828895, 0.9604685665349445])}, help='曲率权重')
    # parser.add_argument('--slopes', default={0: np.array([
    #     [-17.361934010361534, -8.82238254566271, 7.207829434831414, -9.595849723933986, 14.62280505053963, 47.90778065030887, -4.582170240463005, -91.64943459619103], 
    #     [-11.466844544774519, -9.542111645281352, 7.473971848619946, -9.574458003913163, 12.765503948305406, 37.323927731433486, -43.2979459870466, -91.64943459619103], 
    #     [-11.177337608667585, -10.613413137393325, 7.344066858002307, -8.353171259486155, 11.530895595951453, -2.255392722267323, 32.1547638847326, -15.457689899568509], 
    #     [-14.076504600793399, -8.6827846514447, 7.2807790354324995, -9.37176595282542, 12.118638136057404, 16.57276789843122, -0.5147171395048441, -91.64943459619103], 
    #     [-14.08705663876613, -9.36395608794576, 7.164849583091598, -8.685413809522705, 12.02135620905823, 3.5325020008558807, 25.892801016455977, -91.64943459619103], 
    #     [-15.93521219355464, -8.439348289171864, 7.418592922967558, -9.260429966030355, 11.716247954097707, 1.269843025805914, 14.625902847259198, -31.787662859088524]]), 
    #                                                         120: np.array([
    #                                                             [-12.828408552287456, -9.660210787817029, 7.630721934225222, -8.316378424133006, 12.236550095184619, 49.99996678126025, -49.99996678126025, -25.334326484801107], 
    #                                                             [-19.017298802057717, -8.283278169308197, 6.84716400284566, -7.810189078511994, 10.897955534508188, 49.99996678126025, -49.99996678126025, -49.99996678126025], 
    #                                                             [-10.379083471278523, -10.499107406535098, 8.140460016747564, -10.060627404919888, 12.115878315219163, -7.9984669300057165, -3.599333917493265, -49.99996678126025], 
    #                                                             [-17.262023839969302, -9.271997381518112, 7.191153873790344, -8.464842710567064, 11.45512337608043, 19.579722624670005, -7.494459234565948, -49.99996678126025], 
    #                                                             [-11.394338619612483, -10.205125424779862, 8.139901885790902, -10.248509615140962, 12.169985962386189, 7.123911239837365, -7.195938619193081, -49.99996678126025], 
    #                                                             [-18.831696568554584, -8.874357643498374, 7.399052192216785, -8.757061443787114, 11.474403534989582, 1.4846251148964162, 10.216438067446596, -27.15908669125657]]),
    #                                                                       240: np.array([
    #                                                                           [-15.753437734255483, -7.492630557400586, 6.82487052400456, -6.8520500684282375, 8.83024792338105, 16.3556019396367, -17.023575263528258, -33.951741995792304], 
    #                                                                           [-20.66799438844964, -6.776705896728184, 5.63496372120728, -7.163143253184144, 12.5093612759363, 49.99996678126025, -19.382936593069093, -49.99996678126025], 
    #                                                                           [-15.712141723954192, -7.706921023867793, 7.398354249496547, -8.36463954191213, 10.36247070157027, 1.151912126695345, 10.539655479129028, 10.629349965296365], 
    #                                                                           [-15.345600369190322, -8.181994005709742, 4.255236139128114, -5.782931675570792, 10.901804326393206, 25.255485433375302, -21.424664569673933, -49.99996678126025], 
    #                                                                           [-15.577545930269098, -7.171362441835742, 14.180824405901827, -11.472368985281506, 10.711070932314414, -3.9152431142714064, 29.28640869533861, -49.99996678126025], 
    #                                                                           [-12.76053019437769, -9.686897178718416, -22.267853719660234, 5.292893501952441, 8.507735902044905, 26.30525541308219, 11.520823752630669, -15.23477938406701]])}, help='扭转系数')

    # # 曲率权重与扭转系数相关初始值, 曲率向量插值, 全段参数, 不带窗, combined+5cm
    # parser.add_argument('--weights', default={0: np.array([0.769604441191232, 0.8609085601489306, 0.8629575251635755, 0.8879480275090127, 0.8882273817193517, 0.923250790081014, 1.553407546131768, 0.6000005582908989, 1.9183242010029995, 0.6000004670227347, 0.6216559685516176, 1.596270023444882]),
    #                                                               120: np.array([0.8834070763118534, 0.85251461024247, 0.986924957649386, 0.9452724668609392, 0.9725634153903076, 0.9499982676616073, 0.6000005582908392, 0.6000005582908392, 0.6000005582908392, 0.6000005582908392, 0.6000000000002461, 1.2693399508811423]),
    #                                                               240: np.array([0.7867436848812638, 0.9969041223121436, 0.8298518879670551, 1.1115326395320613, 0.5702994386370039, 1.5798283235946788, 1.274133095311955, 1.3903603998788605, 0.6000005583028791, 1.5309897399643118, 0.6000005583028792, 1.5504596861327944])}, help='曲率权重')
    # parser.add_argument('--slopes', default={0: np.array([[-17.36193401,  -8.82238255,   7.20782943,  -9.59584972,
    #      14.62280505,  47.90778065, -82.30284715, -82.30284715],
    #    [-11.46684454,  -9.54211165,   7.47397185,  -9.574458  ,
    #      12.76550395,  37.32392773,  82.30290022, -82.30284715],
    #    [-11.17733761, -10.61341314,   7.34406686,  -8.35317126,
    #      11.5308956 ,  -2.25539272, -82.30284715, -82.30284715],
    #    [-14.0765046 ,  -8.68278465,   7.28077904,  -9.37176595,
    #      12.11863814,  16.5727679 ,  52.14041054, -82.30284715],
    #    [-14.08705664,  -9.36395609,   7.16484958,  -8.68541381,
    #      12.02135621,   3.532502  , -82.30284715,  50.78023258],
    #    [-15.93521219,  -8.43934829,   7.41859292,  -9.26042997,
    #      11.71624795,   1.26984303, -82.30284715, -24.85696314]]),
    #                                                             120: np.array([[-12.82840855,  -9.66021079,   7.63072193,  -8.31637842,
    #      12.2365501 ,  49.99996678,  49.99999986, -49.99996678],
    #    [-19.0172988 ,  -8.28327817,   6.847164  ,  -7.81018908,
    #      10.89795553,  49.99996678, -28.01916787, -49.99996678],
    #    [-10.37908347, -10.49910741,   8.14046002, -10.0606274 ,
    #      12.11587832,  -7.99846693,  -6.12484672, -49.99996678],
    #    [-17.26202384,  -9.27199738,   7.19115387,  -8.46484271,
    #      11.45512338,  19.57972262, -49.99999493, -49.99996678],
    #    [-11.39433862, -10.20512542,   8.13990189, -10.24850962,
    #      12.16998596,   7.12391124, -49.99996678, -49.99996678],
    #    [-18.83169657,  -8.87435764,   7.39905219,  -8.75706144,
    #      11.47440353,   1.48462511, -49.99996678, -49.99996678]]),
    #                                                                           240: np.array([[-15.75343773,  -7.49263056,   6.82487052,  -6.85205007,
    #       8.83024792,  16.35560194, -49.99996678, -21.65933609],
    #    [-20.66799439,  -6.7767059 ,   5.63496372,  -7.16314325,
    #      12.50936128,  49.99996678, -49.99996678, -25.84753076],
    #    [-15.71214172,  -7.70692102,   7.39835425,  -8.36463954,
    #      10.3624707 ,   1.15191213, -49.99996678, -49.99996678],
    #    [-15.34560037,  -8.18199401,   4.25523614,  -5.78293168,
    #      10.90180433,  25.25548543, -49.99996678, -49.99996678],
    #    [-15.57754593,  -7.17136244,  14.18082441, -11.47236899,
    #      10.71107093,  -3.91524311, -49.99996678, -49.99996678],
    #    [-12.76053019,  -9.68689718, -22.26785372,   5.2928935 ,
    #       8.5077359 ,  26.30525541,  49.99996678,   3.65274203]])}, help='扭转系数')
    # # ======================     带窗   =================================
    # # 曲率权重与扭转系数相关初始值, 曲率向量插值, 全段参数, 带窗, 末端调weight
    # parser.add_argument('--weights', default={0: np.array([0.7230207588198502, 0.8464147546817855, 0.8341251537138975, 0.8525467941513734, 0.8588064689991122, 0.8832014239146625, 2.283739386043281, 2.9999994911828556, 0.9744899811410087, 1.8377590653245708, 1.3289634033080926, 1.1482336457470586]), 
    #                                                           120: np.array([0.8478325573279618, 0.8363772546848545, 0.9093072826923914, 0.909220204410606, 0.9188720626053519, 0.9065608385514671, 0.6000004639164158, 0.7265035414413212, 1.1667163513703993, 0.6000004639164164, 0.6000004639164158, 0.6000004639164158]), 
    #                                                           240: np.array([0.7620206010313488, 0.9425110076345642, 0.8281181044251186, 1.0402442825792928, 0.6193392382303656, 1.3972219062460878, 2.9999995397427623, 0.6000004639164158, 1.1332517145947116, 0.6000004639164158, 1.5539252638837064, 0.6000004639164158])}, help='曲率权重')
    # parser.add_argument('--slopes', default={0: np.array([[-21.99572588642002, -6.157113404932542, 5.732417333131552, -3.624767843478101, 8.355806838480612, 41.16245397380852, 49.99996678126028], [-15.404538270528784, -6.775696535031964, 5.871326652455135, -9.500359886506986, 15.690319602401257, -43.39446422884729, -38.41535774526294], [-14.024868730387524, -8.847690663097268, 6.633806657867956, -5.880155584664104, 9.370537115834734, 11.446922558941962, -7.089144548335126], [-15.539266944118774, -7.612300101057546, 6.332745113822027, -7.802278608237254, 11.713812740905324, -0.156250123670756, 12.578156505047689], [-17.533454434648128, -7.296739639305564, 5.976769584394863, -6.686046432888714, 11.343214239238565, -2.877498550132855, 7.055829327215786], [-19.608041332990414, -6.053807796027346, 6.147431058227072, -7.3531173615404875, 11.803284123941102, -4.1714518448573665, 13.013362230180375]]), 
    #                                                         120: np.array( [[-10.664812736015174, -10.623339300836212, 9.301733363053302, -14.44652163165244, 17.269201601349568, 0.2722171852930969, -18.988868347685802], [-24.176550104474586, -6.059682677717179, 4.657077627196834, 0.443839273197092, 2.5317603519110383, 11.468909529569505, 5.62213332233313], [-7.862312619449908, -10.863961138334217, 8.391701611872314, -12.599199208511944, 16.335027431749324, -13.177358007960146, 29.2173327206655], [-23.364898744335676, -6.781983114687132, 5.436248109637838, -5.785797309945551, 9.93819687272675, 2.042917312311661, -12.612452279732306], [-6.183898676961737, -10.768619778513257, 8.487794363810902, -11.61136351426979, 14.236992789641558, -5.1643179990304, 23.94345876703349], [-24.35411760230042, -7.292857202132169, 6.554850441981716, -7.98876927243725, 12.348383738810178, -4.224710594945594, 14.99926503493694]]),
    #                                                                       240: np.array([[-18.0572074057512, -6.6741979652677, 6.697489332747131, -8.105492053853402, 9.881245949675385, 20.137585912085754, 1.5883976506143516], [-20.31076374178319, -6.431819420808289, 5.196088017613206, -6.029167172933978, 14.974302991598677, -32.74077406738238, -65.81663862047878], [-17.371263267744933, -6.400716310795336, 6.208875060466032, -6.382086704704831, 6.541009487620292, 15.421693839564846, -36.569877691695396], [-17.21632340199352, -6.679827934760619, 3.4911498453006753, -2.648722506838495, 14.15459310514768, -0.5922025484675825, 65.81663862047878], [-17.647572247352432, -5.84788063221774, 13.399334325162279, -15.538794434737795, 9.759947228432459, -7.801882895774606, -3.203449031587574], [-14.853974197588073, -7.63648717606176, -26.36680139049186, 20.861483031417155, -0.23877939249754931, 17.713238411572426, -4.896348621567681]])}, help='扭转系数')
    
    # 不传入Optimiser的参数
    parser.add_argument('--task', type=str, required=True, choices=['init', 'ang', 'optim', 'recon', 'demo', 'score'], help='选择运行目的为初始化、旋转角度优化、曲率权重与扭转系数优化、重构、动态展示或评分诊断')
    parser.add_argument('--ang_step', type=float, default=0.1, help='旋转角度搜索步长, 初始为0.1')
    parser.add_argument('--ang_range', type=float, default=1.0, help='旋转角度搜索距离, 初始为180.0')
    return parser


def _explicit_cli_destinations(parser, argv):
    """返回本次命令行显式指定的 argparse 目标名，用于覆盖参数包默认值。"""
    option_destinations = {
        option: action.dest
        for action in parser._actions
        for option in action.option_strings
    }
    result = set()
    for token in argv:
        option = token.split('=', 1)[0]
        if option in option_destinations:
            result.add(option_destinations[option])
    return result


def parse_main_args(argv=None):
    """Load package defaults before the full parse, preserving CLI precedence."""
    argv = list(sys.argv[1:] if argv is None else argv)
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument('--sensor_params')
    bootstrap.add_argument('--sensor_id')
    bootstrap_args, _ = bootstrap.parse_known_args(argv)

    parser = build_argument_parser()
    explicit = _explicit_cli_destinations(parser, argv)
    package = None
    if bootstrap_args.sensor_params:
        package = load_sensor_package(
            bootstrap_args.sensor_params,
            expected_sensor_id=(bootstrap_args.sensor_id if 'sensor_id' in explicit else None),
        )
        defaults = package_parser_defaults(package)
        # A package records the parser default for auditability, but cannot
        # provide the required action selected for this invocation.
        defaults.pop('task', None)
        parser.set_defaults(**defaults)
    args = parser.parse_args(argv)
    args._explicit_cli_parameters = sorted(explicit)
    args._sensor_package = package
    if (package is not None and not args.multi_region_calib
            and args.optimization_region != 'full'
            and 'global_phases_set' not in explicit):
        local_phases = package.get('provenance', {}).get('local_global_phases_set', {})
        region_phases = local_phases.get(args.optimization_region, {})
        local_phase = region_phases.get(str(args.direct), region_phases.get(args.direct))
        if local_phase is not None:
            args.global_phases_set = local_phase
    return args


def main():
    """解析任务配置，并分派 init、optim、score、recon、ang 或 demo 流程。"""
    args = parse_main_args()

    # 存储零状态只作用于动态展示；其他任务保持原有静态数据流程。
    if args.task != 'demo':
        args.use_stored_zero = False

    # 避免Terminal指令读取错误
    if args.weights == "None":
        args.weights = None
    if args.slopes == "None":
        args.slopes = None

    if args.task in ('optim', 'score'):
        jobs = prepare_calibration_jobs(args, configure_calibration_args)
        output_root = Path(args.calibration_output_dir)
        if not output_root.is_absolute():
            output_root = Path(__file__).resolve().parent / output_root
        return run_calibration_jobs(jobs, Optimiser, output_root=output_root)

    calibration_context = configure_calibration_args(args)
    
    # 只传给 Demonstrator 的参数，不传给 Optimiser
    # demo_param_keys = ['total_scale', 'imu', 'imu_com', 'imu_maxlen', 'demo_recorder', 'unwrap_threshold', 'align_threshold',
    #                    'body_model_path', 'entry_length_cm', 'max_curvature', 'back_num', 'entry_exclude', 'enable_t_align', 't2_smooth_window', 'clip_pct', 'clip_k', 'still_rms_th', 'still_hold_frames'] # 用于完整样机展示
    demo_param_keys = [
        'total_scale', 'imu', 'imu_com', 'imu_maxlen', 'demo_recorder', 'unwrap_threshold', 'align_threshold',
        'direction_blend_enabled', 'direction_reference_direct', 'direction_min_curvature', 'direction_min_consecutive',
        'direction_consistency_threshold', 'direction_smooth_alpha',
        'demo_kalman_enabled', 'demo_kalman_Rk', 'demo_kalman_Bk',
        'anchor_constraint_enabled', 'anchor_translation_enabled',
        'anchor_rotation_enabled', 'anchor_offset_m',
    ]

    params = optimizer_parameters(args)

    demo_params = {k: getattr(args, k) for k in demo_param_keys}

    # 初始化优化器与可视化工具
    optim = Optimiser(**params)
    optim.calibration_context = calibration_context
    print(f"curvature interpolation mode: {optim.curvature_interp}")


    if args.task == 'demo':
        app = QApplication(sys.argv)
        demo = Demonstrator(recon=optim, **demo_params)
        demo.show()
        
        if demo.imu: 
            IMU_thread = threading.Thread(target=demo.receive_IMU)
            IMU_thread.daemon = True
            IMU_thread.start()
            print("---------- 开始接收IMU数据 ----------")       
        else:
            print("---------- 未启用IMU ----------")

        if optim.interrogator == 'FiberTecc':
            data_receiver_thread = threading.Thread(target=optim.receive_data_FiberTecc, daemon=True)
        elif optim.interrogator == 'Hippo':
            data_receiver_thread = threading.Thread(target=optim.receive_data_Hippo, daemon=True)
        data_receiver_thread.start()
        sys.exit(app.exec_())

    else:
        vis = Visualisor(recon=optim)
        if args.task == 'init':
            compute_error_ang(optim=optim, vis=vis, init=True)
        elif args.task == 'ang':
            optim_ang(rot_ang=args.rot_ang, ang_step=args.ang_step, ang_range=args.ang_range, optim=optim, vis=vis)
        elif args.task in ['optim']:
            optim.optim_coeff(verbose=True)            
        elif args.task == 'recon':
            rs = {}
            for calib_shape in optim.calib_shapes:
                r_results_postrot, interp_dist = optim.reconstruct_shapes(calib_shape=calib_shape, direct=args.direct, verbose=False)
                rs[calib_shape] = r_results_postrot
            optim._compute_error(interp_dist=interp_dist, rs=rs)
            vis.show_reconstruction(direct=args.direct, rs=rs, interp_dist=interp_dist, showanime=True)
            optim._print_errors()
    

if __name__ == '__main__':
    main()
