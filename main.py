import argparse
from email import parser
import time
import sys
import threading
import numpy as np
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from optimiser import Optimiser
from visualisor import Visualisor
# from proto_demonstrator import Demonstrator 完整样机展示代码
from demonstrator import Demonstrator




# Verified 11B8 calibration: each direction uses its own spatial segments.
CALIBRATION_SEGMENTATION_11B8 = {0: [10, 10, 10, 10], 120: [10, 10, 10, 10], 240: [7, 7, 7, 7, 6, 6]}

def compute_error_ang(optim, vis, init):
    errs = {}
    for direct in optim.exp_directs:
        optim.direct = direct
        if optim.sensor_id == "11B8":
            optim.segmentation = CALIBRATION_SEGMENTATION_11B8[direct]
            optim.num_segments = len(optim.segmentation)
            optim.base_segments = optim._calculate_segments(optim.total_points)
            vis.segmentation = optim.segmentation
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

def main():
# ---------- 初始化 ----------
    # ---------- 初始化 ----------
    parser = argparse.ArgumentParser()
    # 硬件参数
    parser.add_argument('--sensor_id', type=str, default='11B8', help='传感器编号')
    parser.add_argument('--start_value', type=float, default=175.0, help='传感器第一个传感点到固定件的距离, 单位为mm')
    parser.add_argument('--end_value', type=float, default=8.0, help='传感器最后一个传感点到末端的距离, 单位为mm')
    # parser.add_argument('--R', type=float, default=0.235e-3, help='传感器半径, 单位为m') #肠镜
    parser.add_argument('--R', type=float, default=0.0001, help='传感器半径, 单位为m') # 支气管镜
    parser.add_argument('--ideal_len', type=float, default=0.900, help='传感器长度, 单位为m') # 支气管镜
    # parser.add_argument('--ideal_len', type=float, default=1.35, help='传感器长度, 单位为m') #肠镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 540, 570, 630, 710, 810, 910, 1010, 1110, 1210, 1310, 1410, 1510, 1610, 1710, 1815], help='FBG传感点位置(A组及中心), 单位为mm') #肠镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 520, 530, 540, 550, 580, 610, 640, 670, 720, 770, 850, 930, 1010, 1110, 1230], help='FBG传感点位置, 单位为mm')# 16点支气管镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 520, 530, 540, 550, 580, 610, 640, 670, 720, 770, 850, 930, 1010, 1110, 1230], help='FBG传感点位置, 单位为mm')# 16点支气管镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 521, 532, 543, 554, 579, 604, 629, 654, 696, 738, 780, 822, 864, 906, 948, 990, 1032, 1074, 1116, 1158, 1200], help='FBG传感点位置, 单位为mm') # 22点支气管镜
    # parser.add_argument('--samp_dist_preset', type=list, default=[530, 602, 720, 852, 984, 1116, 1248, 1380], help='FBG传感点位置, 单位为mm') # 8点支气管镜08C1特殊参数
    # parser.add_argument('--samp_dist_preset_sub', type=list, default=[120, 160, 200, 295, 445, 595, 745, 895], help='FBG传感点位置(B组), 单位为mm')
    # parser.add_argument('--samp_dist_preset', type=list, default=[510, 550, 654, 786, 918, 1050, 1182, 1314], help='FBG传感点位置, 单位为mm') # 22点支气管镜特殊参数Fibertecc  # 三组交错刻栅使用下方A/B/C配置；兼容参数在解析后生成
    parser.add_argument('--samp_dist_preset_a', type=list, default=[510, 524, 538, 552, 566, 580, 594, 608, 622, 636, 650, 664, 678, 692, 706, 720, 820, 920, 1020, 1220], help='外围A组位置（CH2/4/6），按原始FBG列顺序，mm')
    parser.add_argument('--samp_dist_preset_b', type=list, default=[517, 531, 545, 559, 573, 587, 601, 615, 629, 643, 657, 671, 685, 699, 713, 727, 827, 927, 1027, 1227], help='外围B组位置（CH1/3/5），按原始FBG列顺序，mm')
    parser.add_argument('--samp_dist_preset_c', type=list, default=[510, 524, 538, 552, 566, 580, 594, 608, 622, 636, 650, 664, 678, 692, 706, 720, 820, 920, 1020, 1220], help='CH0中心纤芯原始位置，mm')
    parser.add_argument('--centre_fibre', type=bool, default=True, help='是否为1+x构型')
    parser.add_argument('--interlaced_grating', type=bool, default=True, help='栅区是否交错排列')
    parser.add_argument('--interlaced_offset', type=float, default=np.pi/3, help='交错排列时的角度偏移，单位为度')
    parser.add_argument('--global_phases_set', type=float, default=None, help='全局相位，初始值为None')
    # 标定实验参数
    parser.add_argument('--interrogator', type=str, default='FiberTecc', help='解调仪器')
    parser.add_argument('--active_channels', type=list, default=[1, 2, 3, 4, 5, 6, 7], help='传感器连接解调仪的通道以及其顺序')
    parser.add_argument('--channel_change', type=bool, default=False, help='通道排布是否变化')
    parser.add_argument('--channel_layout', type=list, default=[(5, [2, 1, 4, 3, 7, 5, 6]), (7, [5, 1, 4, 3, 2, 7, 6]), (4, [7, 1, 4, 3, 2, 5, 6])], help='当通道排布出现错序，每一段的长度及其排布顺序(列表嵌套元组格式)')
    parser.add_argument('--active_angles', type=list, default=[0, 60, 120, 180, 240, 300], help='外围通道角度排布(度数)，若为None则默认均匀排布')
    parser.add_argument('--folder_path', type=str, default=str(Path(__file__).resolve().parent / '1118-11B8-自研（1+3）18点79.7cmFBG'), help='数据存储路径')
    parser.add_argument('--rot_dir', type=list, default={0: -1, 120: -1, 240: -1}, help='各个标定实验按逆(1)还是顺(-1)顺时针调整的方向')
    parser.add_argument('--exp_directs', type=list, default=[0, 120, 240], help='实验使用的方向')
    parser.add_argument('--radii', type=list, default={'circ': [0, 2000, 1500, 1000, 800, 600, 400, 300, 200]}, help='标定圆弧形状半径')
    parser.add_argument('--end_len', type=float, default=0.05, help='end形状中进入末端大曲率弧圈的包含长度')
    # 优化使用的超参数
    parser.add_argument('--direct', type=int, default=0, help='优化曲率权重与扭转系数的标定方向')
    parser.add_argument('--freeze', type=list, default=None, help='冻结部分分区的参数，使得它们不参与优化。如果不需要冻结则调整为None。分区index从0开始。')
    parser.add_argument('--weight_bounds', type=tuple, default=(0.6, 2.0), help='曲率权重范围')
    parser.add_argument('--slope_upper_bound', type=tuple, default=50.0, help='扭转系数大小上限')
    parser.add_argument('--thresholds', type=list, default=[0.8, 1.2, 2.0, 3.0, 4.0], help='各曲率分级的阈值')
    parser.add_argument('--max_iter', type=int, default=20, help='优化的最大轮次')
    parser.add_argument('--k_point', type=float, default=0.3, help='优化目标中末端误差的权重')## 一般不超过0.5
    # parser.add_argument('--k_end', type=float, default=2.0, help='优化目标中末端误差的权重')
    parser.add_argument('--k_end', type=float, default=1.0, help='优化目标中末端误差的权重')
    parser.add_argument('--k_pitch', type=float, default=1.0, help='优化目标中螺距误差的权重')
    parser.add_argument('--k_radius', type=float, default=1.0, help='优化目标中半径误差的权重')
    parser.add_argument('--method', type=str, default="Powell", help='优化算法, 用于输入scipy.optimize.minimimze')
    parser.add_argument('--hyper_params', type=dict, default=[10000, 1e-6, 1e-6], help='优化算法使用的超参数')
    parser.add_argument('--min_loss_diff', type=float, default=1e-5, help='收敛判定')
    parser.add_argument('--ss', type=float, default=2.6e-3, help='LUNA传感点间隔, 单位为m')
    # 动态展示参数
    parser.add_argument('--IP', type=str, default='192.168.1.75', choices=['192.168.1.75', '10.0.0.122'], help='FiberTecc使用192.168.1.75, Hippo使用10.0.0.122')
    parser.add_argument('--PORT', type=int, default=26546, choices=[26546, 4010], help='FiberTecc使用26546, Hippo使用4010')
    parser.add_argument('--maxsize', type=int, default=10, choices=[10, 2], help='FiberTecc使用10, Hippo使用2')
    parser.add_argument('--data_freq', type=int, default=100, help='解调仪频率')
    parser.add_argument('--total_scale', type=float, default=1.0, help='动态显示大小')
    parser.add_argument('--imu', type=bool, default=False, help='是否启用IMU')
    parser.add_argument('--imu_com', type=str, default='COM6', help='IMU接口')
    parser.add_argument('--imu_maxlen', type=int, default=10)
    parser.add_argument('--demo_recorder', type=bool, default=False, help='是否在动态展示时记录数据')
    parser.add_argument('--unwrap_threshold', type=float, default=0.65, help='若两帧同一点角度变化小于该阈值，则统一unwrap方向')
    parser.add_argument('--align_threshold', type=float, default=0.20, help='若某帧第一点角度变化小于该阈值，则将第一点角度与上一帧对齐')
    parser.add_argument('--direction_blend_enabled', action='store_true', help='动态展示中启用0/120/240度参数半余弦软过渡；应在rot_ang确定后再打开')
    parser.add_argument('--direction_reference_direct', type=int, default=240, choices=[0, 120, 240], help='动态第一遍方向估计及关闭软过渡时使用的最高精度参数方向')
    parser.add_argument('--direction_min_curvature', type=float, default=0.5, help='动态方向估计的有效弯曲点最小曲率，低于该值时冻结上一帧方向质量')
    parser.add_argument('--direction_min_consecutive', type=int, default=3, help='动态方向估计中近端稳定弯曲区要求的最少连续点数')
    parser.add_argument('--direction_consistency_threshold', type=float, default=0.6, help='曲率加权圆周平均的最小方向一致性，低于该值时冻结上一帧方向质量')
    parser.add_argument('--direction_smooth_alpha', type=float, default=0.15, help='动态方向质量跨帧指数平滑系数，范围(0,1]')
    parser.add_argument('--demo_kalman_enabled', type=_str2bool, default=True, help='动态展示中对重构曲线启用跨帧卡尔曼滤波（True开启，开启后替代原有的curve_history滑动平均；False关闭）')
    parser.add_argument('--demo_kalman_Rk', type=float, default=1e-4, help='跨帧卡尔曼滤波的观测噪声参数，越大越平滑、响应越慢，量纲为m^2')
    parser.add_argument('--demo_kalman_Bk', type=float, default=1e-5, help='跨帧卡尔曼滤波的状态转移误差参数，越大对新观测响应越快，量纲为m^2')
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
    parser.add_argument('--kalman_params', type=dict, default={'angle': {'Rk': 0.001, 'Bk': 0.001}, 'magnitude': {'Rk': 0.0001, 'Bk': 0.01}}, help='卡尔曼滤波参数')
    parser.add_argument('--smoothing_params', type=dict, default={'window_length': 21,'polyorder': 3}, help='LUNA数据平滑参数')
    parser.add_argument('--interp_num', type=int, default=256, help='插值目标点数')
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
    parser.add_argument('--end_weights', type=bool, default=True, help='是否对末端另算权重') #考虑末端15cm
    parser.add_argument('--end_start', type=int, default=-4, help='末端起点')
    parser.add_argument('--TNB_threshold', type=float, default=0.0, help='TNB重构直线判定阈值')
    # 初始化时必须手动调整的超参数
    parser.add_argument('--straight_trim', type=float, default=0.0, help='默认不读取的部分，若只知道剩余长度，则调整为负数。')
    parser.add_argument('--segmentation', type=list, default=[10, 10, 10, 10], help='对扭转角度-传感点位置曲线的点数')#优先调分段
    parser.add_argument('--connect', type=bool, default=False, help='拟合初始分段时是否令各分段首尾相连')
    parser.add_argument('--turn_threshold', type=float, default=2.0, help='判断形状弯曲方向是否改变的阈值')
    parser.add_argument('--sensing_ranges', type=dict, default={1: (583, 1048), 3: (678, 1146), 4: (749, 1215)}, help='LUNA各通道使用的传感点范围')
    # 角度优化初始值
    parser.add_argument('--rot_ang_by_direct', type=dict, default={0: -1.077499349132087, 120: 74.57340262388045, 240: -55.22501149481747}, help='各标定方向的独立旋转修正，单位度；rot_ang为额外公共修正')
    parser.add_argument('--rot_ang', type=float, default=0.0, help='绕x轴旋转角度, 初始为0.0')
    # 曲率权重与扭转系数相关初始值
    parser.add_argument('--weights', default={0: np.array([0.7681269991014278, 0.8958490993372497, 0.9717751489906998, 0.8321388107691313, 0.868050674058409, 0.8325988748589692, 2.9999626316192662, 0.21820889971696456, 0.2000373683807333, 2.9999626515116398, 2.9999626731478797, 2.59174363495306]), 120: np.array([0.7242529211939532, 1.5974086499737923, 0.7258574083773086, 0.8619035512785476, 0.7326200643405204, 0.8832992185547598, 2.9999626316192662, 2.9999626316192667, 2.9999626316192667, 2.9999626316192667, 2.9999626316192667, 2.9999626316192662]), 240: np.array([1.2064341632715074, 1.0454247831557058, 1.0525395153737613, 0.8393788974965916, 1.2081786289983187, 1.0828198486747733, 2.9999626316192662, 2.9999626316192662, 2.9999626316192662, 2.9999626316192662, 2.9999626316192662, 2.9999626316192662])}, help='曲率权重')
    parser.add_argument('--slopes', default={0: np.array([[1.2976970834409056, -14.625454809777953, -4.069075052992371, -14.826769991441392], [0.5965430687870685, 8.48121405093909, -45.01795255643384, 49.99758166269136], [-0.39405119257554494, -3.0752353686787557, -15.768499284539464, 4.810463653792263], [0.049234428487001054, -3.102022517233669, -15.759927282236285, 4.816573302986483], [-0.5846678578949583, -3.0841490558548257, -15.730438983193281, 4.827100432993619], [0.3355703905079888, -2.9289618608707157, -15.597575276563497, 4.8343082766442045]]), 120: np.array([[-5.147267245926437, 30.113341447038383, -23.803793915760338, -9.094267297736472], [-6.425596085615511, 35.8245707127698, -43.306440500146905, -1.6920018713986664], [-3.176497899295115, 8.831361423718098, -18.934812367255663, -9.004857755843966], [-2.298185452871928, 20.22985935105206, -22.55149732334409, 0.30637658485319247], [-0.509346121963006, -0.5825293608189449, -14.431819073136747, -45.70143606418788], [2.120312005929197, -24.74151081043309, -36.53916581475063, 28.5480167993861]]), 240: np.array([[6.128792099948288, 12.964642800774806, 42.199354645489784, -49.99758103179057, 18.706749148040206, -49.997581031790546], [8.930560133000071, -34.14441283529342, -3.8628021460210897, -23.834863412839272, -14.921928348257769, -49.99758103198665], [8.621159493600627, -7.871896027582313, 13.972492762435435, -32.361788339789676, -38.01837402033964, 41.95917529514145], [-3.059614697380865, 5.454284618728189, 3.304380839915548, -11.354946839539522, -12.75833006671491, 41.708430888643946], [-6.059535675917536, 9.498710908339216, 8.21828779939979, -6.606169144601874, -10.43436834962857, 35.79881160537345], [-2.9925304742855228, 17.518309872475758, 5.875444873791617, -15.650634190397552, -12.644406304943992, 36.630494436442554]])}, help='扭转系数')
    # 不传入Optimiser的参数
    parser.add_argument('--task', type=str, required=True, choices=['init', 'ang', 'optim', 'recon', 'demo'], help='选择运行目的为初始化、旋转角度优化、曲率权重与扭转系数优化、重构还是动态展示')
    parser.add_argument('--ang_step', type=float, default=0.1, help='旋转角度搜索步长, 初始为0.1')
    parser.add_argument('--ang_range', type=float, default=1.0, help='旋转角度搜索距离, 初始为180.0')
    args = parser.parse_args()


    # Legacy A/B aliases consumed by the shared Sensor pipeline.
    if all(value is not None for value in (args.samp_dist_preset_a, args.samp_dist_preset_b, args.samp_dist_preset_c)):
        args.samp_dist_preset = args.samp_dist_preset_a
        args.samp_dist_preset_sub = args.samp_dist_preset_b

    # 存储零状态只作用于动态展示；其他任务保持原有静态数据流程。
    if args.task != 'demo':
        args.use_stored_zero = False

    # 避免Terminal指令读取错误
    if args.weights == "None":
        args.weights = None
    if args.slopes == "None":
        args.slopes = None
    
    # 只传给 Demonstrator 的参数，不传给 Optimiser
    # demo_param_keys = ['total_scale', 'imu', 'imu_com', 'imu_maxlen', 'demo_recorder', 'unwrap_threshold', 'align_threshold',
    #                    'body_model_path', 'entry_length_cm', 'max_curvature', 'back_num', 'entry_exclude', 'enable_t_align', 't2_smooth_window', 'clip_pct', 'clip_k', 'still_rms_th', 'still_hold_frames'] # 用于完整样机展示
    demo_param_keys = [
        'total_scale', 'imu', 'imu_com', 'imu_maxlen', 'demo_recorder', 'unwrap_threshold', 'align_threshold',
        'direction_blend_enabled', 'direction_reference_direct', 'direction_min_curvature', 'direction_min_consecutive',
        'direction_consistency_threshold', 'direction_smooth_alpha',
        'demo_kalman_enabled', 'demo_kalman_Rk', 'demo_kalman_Bk',
    ]

    optim_exclude_keys = ['task', 'ang_step', 'ang_range'] + demo_param_keys
    params = {k: getattr(args, k) for k in vars(args) if k not in optim_exclude_keys}

    demo_params = {k: getattr(args, k) for k in demo_param_keys}

    if args.sensor_id == "11B8" and args.slopes is not None:
        selected_direction = args.direction_reference_direct if args.task == "demo" else args.direct
        params["segmentation"] = CALIBRATION_SEGMENTATION_11B8[selected_direction]

    # 初始化优化器与可视化工具
    optim = Optimiser(**params)
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
