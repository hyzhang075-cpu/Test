import os
import vtk
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib import animation
from scipy import stats

from tools.utils import dict_recur_paths, dict_recur_value, update_view

class Visualisor:
    """
    可视化方法以及必要参数
    """
    def __init__(self, recon):
        self.sensor_id = recon.sensor_id
        self.active_channels = recon.active_channels
        self.samp_dist = recon.samp_dist
        self.ad_samp_dist = recon.ad_samp_dist
        self.ideal_len = recon.ideal_len
        self.rot_ang = recon.rot_ang
        self.calib_shapes = recon.calib_shapes
        self.plot_Data = recon.plot_Data
        self.radii = recon.radii
        self.init_weight = recon.init_weight
        self.segmentation = recon.segmentation
        self.active_channels = recon.active_channels
        self.angle_results_unwrap = recon.angle_results_unwrap
        self.angle_results_raw = recon.angle_results_raw
        self.global_fit_direct = recon.global_fit_direct
        self.individual_fits_direct = recon.individual_fits_direct

        self.zero_init = recon.zero_init
        self.straight_trim = recon.straight_trim
        self._segment_data = recon._segment_data

        self._calculate_segments = recon._calculate_segments
        self._construct_ideals = recon._construct_ideals

    # def init_visualise(self, direct):
    #     """
    #     生成初始化阶段相关的可视化结果并保存到目录。

    #     步骤：
    #     1. 创建当前方向与 segmentation 对应的初始化图像目录。
    #     2. 对当前对象中记录的各 calib_shape 绘制应变曲线图。
    #     3. 若存在 S 形标定数据，则绘制其原始角度与 unwrap 后角度的对比图。
    #     4. 基于 circ 标定数据的 unwrap 后角度结果，进一步绘制：
    #         - 多半径角度曲线图；
    #         - 整体线性拟合图；
    #         - 分段全局拟合与单半径拟合对比图。

    #     输入：
    #     - direct: 当前实验方向

    #     输出：
    #     - 无显式返回
    #     - 副作用：
    #         - 在 self.sensor_id/.../init_plots/ 目录下保存多张初始化阶段图像

    #     说明：
    #     - 当前实现会对所有存在的 calib_shape 绘制应变曲线；
    #     - 若存在 S 形标定数据，则额外使用
    #     self.angle_results_raw['S'][direct] 与 self.angle_results_unwrap['S'][direct] 绘制角度对比图；
    #     - circ 相关拟合图使用的是 self.angle_results_unwrap['circ'][direct]，
    #     以及 self.global_fit_direct[direct]、self.individual_fits_direct[direct]。
    #     """
    #     init_dir = os.path.join(self.sensor_id, str(self.active_channels.keys()), str(self.segmentation), str(direct), "init_plots")
    #     os.makedirs(init_dir, exist_ok=True)
    #     for calib_shape in self.calib_shapes:
    #         if calib_shape == 'S':
    #             self._ang_curve(angle=self.angle_results_raw['S'][direct], angle_unwrap=self.angle_results_unwrap['S'][direct], save_dir=init_dir)
    #         self._strain_curve(direct=direct, calib_shape=calib_shape, save_dir=init_dir)
    #     fit_slope, fit_intercept, combined_x, _ = self._linear_fit_processor(angle_data=self.angle_results_unwrap['circ'][direct]) # 不考虑分段做线性拟合
    #     self._dict_curves(direct=direct, dict_data=self.angle_results_unwrap['circ'][direct], save_dir=init_dir) # 画角度点
    #     self._visualisation_engine(angle_data=self.angle_results_unwrap['circ'][direct], slope=fit_slope, intercept=fit_intercept, merged_x=combined_x, save_dir=init_dir) # 画角度曲线
    #     self._visualise_ensemble_fit(angle_data=self.angle_results_unwrap['circ'][direct], global_fit=self.global_fit_direct[direct], individual_fits=self.individual_fits_direct[direct], save_dir=init_dir) # 画曲线+拟合线

    def init_visualise(self, direct):
        init_dir = os.path.join(self.sensor_id, str(self.active_channels.keys()), str(self.segmentation), str(direct), "init_plots")
        os.makedirs(init_dir, exist_ok=True)

        for calib_shape in self.calib_shapes:
            if calib_shape == 'S' and 'S' in self.angle_results_raw and direct in self.angle_results_raw['S']:
                self._ang_curve(angle=self.angle_results_raw['S'][direct], angle_unwrap=self.angle_results_unwrap['S'][direct], save_dir=init_dir)
            self._strain_curve(direct=direct, calib_shape=calib_shape, save_dir=init_dir)

        # 新的统一图
        self._visualise_all_shapes_unwrap_and_fit(direct=direct, save_dir=init_dir)
        
    def _visualise_all_shapes_unwrap_and_fit(self, direct, save_dir):
        """
        在一张图中画出：
        1) 所有 shape 的 unwrap 曲线
        2) 所有可参与拟合的 shape 的 global fit
        3) 所有可参与拟合的 shape 的 individual fits
        """

        # ---------- 收集当前 direct 下所有 unwrap 数据 ----------
        angle_data_by_shape = {}
        for shape, direct_dict in self.angle_results_unwrap.items():
            if direct in direct_dict:
                angle_data_by_shape[shape] = direct_dict[direct]

        # ---------- 收集当前 direct 下所有 individual fits ----------
        fit_data_by_shape = self.individual_fits_direct.get(direct, {})

        # 当前 joint global fit（这是联合 circ/S/rot0 算出来的）
        global_fit = self.global_fit_direct.get(direct, None)

        # ---------- 拉平所有曲线 ----------
        curve_items = []   # [(shape, path, angles), ...]
        curve_map = {}     # {(shape, *path): angles}

        for shape, tree in angle_data_by_shape.items():
            for path, angles in self._flatten_tree_leaves(tree):
                angles = np.asarray(angles, dtype=float).reshape(-1)
                key = (shape,) + path
                curve_items.append((shape, path, angles))
                curve_map[key] = angles

        # ---------- 为 global fit 重新构造 combined_x 与 merged_segments ----------
        # 注意：这里要尽量模仿 Initialiser._compute_global_fit 的拼接逻辑
        pooled_x = [[] for _ in range(len(self.segmentation))]

        for shape in fit_data_by_shape.keys():   # 只对有 fit 的 shape 做 global fit 可视化
            if shape not in angle_data_by_shape:
                continue

            for path, angles in self._flatten_tree_leaves(angle_data_by_shape[shape]):
                x_data, y_data, segments = self._segment_data(np.asarray(angles, dtype=float))

                for idx, (start, end) in enumerate(segments):
                    if idx >= len(pooled_x):
                        break
                    pooled_x[idx].extend(np.asarray(x_data[start:end], dtype=float).tolist())

        combined_x = []
        merged_segments = []
        current = 0
        for xs in pooled_x:
            if len(xs) == 0:
                continue
            combined_x.extend(xs)
            merged_segments.append((current, current + len(xs)))
            current += len(xs)

        combined_x = np.asarray(combined_x, dtype=float)

        # ---------- 开始画图 ----------
        fig, axes = plt.subplots(3, 1, figsize=(16, 20), squeeze=False)
        ax_raw, ax_global, ax_ind = axes.flatten()

        # ====== 1) 所有 unwrap 曲线 ======
        for shape, path, angles in curve_items:
            x, y = self._prepare_curve_xy(angles)
            if len(x) == 0:
                continue
            label = self._leaf_label(shape, path)
            ax_raw.plot(x, y, 'o-', markersize=3, alpha=0.8, label=label)

        ax_raw.set_title(f"All Unwrapped Angle Curves (direct={direct})")
        ax_raw.set_xlabel("Sample Distance (m)")
        ax_raw.set_ylabel("Angle (rad)")
        ax_raw.grid(alpha=0.3)
        ax_raw.legend(fontsize=8, ncol=2)

        # ====== 2) 所有曲线 + global fit ======
        for shape, path, angles in curve_items:
            x, y = self._prepare_curve_xy(angles)
            if len(x) == 0:
                continue
            label = self._leaf_label(shape, path)
            ax_global.plot(x, y, 'o', markersize=3, alpha=0.35, label=label)

        if global_fit is not None and len(combined_x) > 0:
            for idx, ((slope, intercept), (start, end)) in enumerate(zip(global_fit, merged_segments)):
                if np.isnan(slope) or np.isnan(intercept):
                    continue
                x_seg = combined_x[start:end]
                y_fit = slope * x_seg + intercept
                ax_global.plot(
                    x_seg, y_fit,
                    'k--', lw=3,
                    label='Global Fit' if idx == 0 else None
                )

        ax_global.set_title(f"All Curves + Joint Global Fit (direct={direct})")
        ax_global.set_xlabel("Sample Distance (m)")
        ax_global.set_ylabel("Angle (rad)")
        ax_global.grid(alpha=0.3)
        ax_global.legend(fontsize=8, ncol=2)

        # ====== 3) 所有曲线 + individual fits ======
        for shape, path, angles in curve_items:
            x, y = self._prepare_curve_xy(angles)
            if len(x) == 0:
                continue
            label = self._leaf_label(shape, path)
            ax_ind.plot(x, y, 'o', markersize=3, alpha=0.25, label=label)

        for shape, fit_tree in fit_data_by_shape.items():
            for path, fit_list in self._flatten_tree_leaves(fit_tree):
                key = (shape,) + path
                if key not in curve_map:
                    continue

                angles = curve_map[key]
                x_data, y_data, segments = self._segment_data(angles)

                first_seg = True
                for (slope, intercept), (start, end) in zip(fit_list, segments):
                    if np.isnan(slope) or np.isnan(intercept):
                        continue

                    x_seg = np.asarray(x_data[start:end], dtype=float)
                    y_fit = slope * x_seg + intercept

                    ax_ind.plot(
                        x_seg, y_fit, lw=2,
                        label=f"{self._leaf_label(shape, path)} Fit" if first_seg else None
                    )
                    first_seg = False

        ax_ind.set_title(f"All Curves + Individual Fits (direct={direct})")
        ax_ind.set_xlabel("Sample Distance (m)")
        ax_ind.set_ylabel("Angle (rad)")
        ax_ind.grid(alpha=0.3)
        ax_ind.legend(fontsize=8, ncol=2)

        plt.tight_layout()

        save_path = os.path.join(save_dir, "All_Shapes_Unwrap_and_Fits.png")
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

    def _flatten_tree_leaves(self, obj, prefix=()):
        """
        将嵌套字典拉平成 [(path_tuple, leaf_value), ...]
        """
        items = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                items.extend(self._flatten_tree_leaves(v, prefix + (k,)))
        else:
            items.append((prefix, obj))
        return items


    def _prepare_curve_xy(self, angles):
        """
        将单条角度曲线整理成与拟合时一致的 x / y。
        """
        angles = np.asarray(angles, dtype=float).reshape(-1)
        valid_length = min(len(angles), len(self.samp_dist))

        if self.zero_init or self.straight_trim != 0:
            x = np.asarray(self.samp_dist[:valid_length], dtype=float)
            y = angles[:valid_length]
        else:
            x = np.asarray(self.samp_dist[1:valid_length], dtype=float)
            y = angles[1:valid_length]

        return x, y


    def _leaf_label(self, shape, path):
        """
        给每条曲线生成图例标签。
        """
        if len(path) == 0:
            return str(shape)
        return f"{shape}|" + "-".join(str(p) for p in path)

    def _strain_curve(self, direct, calib_shape, save_dir):
        """
        绘制指定标定形状与方向下的各通道应变曲线并保存。

        输入：
        - direct: 当前方向
        - calib_shape: 标定形状类型，如 'circ'、'S'、'end'、'rot0'、'up' 或 'down'
        - save_dir: 图像保存目录

        输出：
        - 无显式返回
        - 副作用：
            - 在 save_dir 下保存名为 "Strain_Data_{calib_shape}.png" 的图像文件

        说明：
        - 每个激活通道对应一个子图；
        - 对 circ / S，按单层半径键绘制曲线；
        - 对 end / rot0 / up / down，按两层键组合绘制曲线；
        - 图例标签对嵌套形状使用 "一级键-二级键" 的形式。
        """
        title = f"Strain Data {calib_shape}"
        # 创建图形
        fig, axes = plt.subplots(len(self.active_channels), 1, figsize=(8, 12))  
        
        # 遍历每个通道
        for phy_ch, idx in self.active_channels.items():
            ax = axes[idx]  # 当前子图
            for radius, data in self.plot_Data[calib_shape][direct].items():
                if calib_shape in ['circ', 'S']:
                    x = list(range(len(data[:, idx])))
                    y = data[:, idx] / 1e-6
                    ax.plot(x, y, label=radius)
                else:
                    for radius_end, data_end in data.items():
                        x = x = list(range(len(data_end[:, idx])))
                        y = data_end[:, idx]
                        ax.plot(x, y, label=f"{radius}-{radius_end}")

            ax.set_ylabel(f'Ch {phy_ch}') #限制y轴范围，便于观察细节
            ax.set_ylim(-500, 500)  # 根据实际数据调整范围
        # 显示图形
        safe_title = title.replace(" ", "_").replace("/", "_")
        save_path = os.path.join(save_dir, f"{safe_title}.png")
        axes[0].legend(loc='upper right', fontsize='small', title='Radius')
        plt.tight_layout()  # 自动调整子图的间距
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

    def _ang_curve(self, angle, angle_unwrap, save_dir):
        """
        绘制原始角度与 unwrap 后角度的逐半径对比图并保存。

        输入：
        - angle: 原始角度字典，键为半径，值为角度数组
        - angle_unwrap: unwrap 后角度字典，键为半径，值为角度数组
        - save_dir: 图像保存目录

        输出：
        - 无显式返回
        - 副作用：
        - 在 save_dir 下保存名为 "Angle_Data.png" 的图像文件

        异常：
        - 当 angle 与 angle_unwrap 没有共同半径键时抛出 ValueError
        - 当某个半径对应的数据长度与 self.samp_dist 不一致时抛出 ValueError

        说明：
        - 每个半径使用一个单独子图
        - 子图中会同时绘制 angle 与 angle_unwrap，并在点旁标出数值
        """
        title = "Angle Data"

        # 取两个字典共同拥有的 radius
        radii = [r for r in angle.keys() if r in angle_unwrap]
        if not radii:
            raise ValueError("angle 和 angle_unwrap 没有共同的 radius key。")

        # 如果你想按半径从大到小显示，就用这一句
        radii = sorted(radii, reverse=True)

        n = len(radii)
        fig, axes = plt.subplots(n, 1, figsize=(12, 4 * n), squeeze=False)
        axes = axes.flatten()

        x = np.asarray(self.samp_dist)

        for ax, radius in zip(axes, radii):
            y1 = np.asarray(angle[radius], dtype=float)
            y2 = np.asarray(angle_unwrap[radius], dtype=float)

            if len(x) != len(y1) or len(x) != len(y2):
                raise ValueError(
                    f"radius={radius} 时长度不一致: "
                    f"len(self.samp_dist)={len(x)}, len(angle)={len(y1)}, len(angle_unwrap)={len(y2)}"
                )

            ax.plot(x, y1, 'r-o', label='angle')
            ax.plot(x, y2, 'g-o', label='angle_unwrap')
            ax.set_title(f"Radius = {radius}")
            ax.set_ylabel("Angle")
            ax.grid(True)
            ax.legend()

            # 显示 angle 数据点数值
            for xi, yi in zip(x, y1):
                ax.text(xi, yi, f'{yi:.2f}', color='red', fontsize=8, ha='right', va='bottom')

            # 显示 angle_unwrap 数据点数值
            for xi, yi in zip(x, y2):
                ax.text(xi, yi, f'{yi:.2f}', color='green', fontsize=8, ha='left', va='bottom')

        axes[-1].set_xlabel("Sample Distance")

        safe_title = title.replace(" ", "_").replace("/", "_")
        save_path = os.path.join(save_dir, f"{safe_title}.png")
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close(fig)


    def _dict_curves(self, direct, dict_data, save_dir):
        """
        将字典中的多条角度曲线画到同一张图中并保存。

        输入：
        - dict_data: 字典，键为半径，值为对应的一维角度数组
        - save_dir: 图像保存目录

        输出：
        - 无显式返回
        - 副作用：
        - 在 save_dir 下保存名为
            "Changing_of_angles_under_different_curvature_(raw).png" 的图像文件

        说明：
        - 横坐标使用 self.samp_dist
        - 遍历顺序使用 self.radii[direct]['circ']
        - 该方法假定 dict_data 中包含 self.radii[direct]['circ'] 对应的全部键
        """
        # ---------- 创建保存路径 ----------
        title = "Changing of angles under different curvature (raw)"

        plt.figure(figsize=(12, 8))

        for radius in self.radii[direct]['circ']:
            data = dict_data[radius]
            plt.plot(self.samp_dist, data, label=f'Radius {radius}')

        # 统一设置坐标轴标签和标题
        plt.xlabel('Sample Distance')  # 正确函数名
        plt.ylabel('Value')
        plt.legend(loc='upper right', fontsize='small')
        plt.tight_layout()

        # ----------- 保存并关闭 -----------
        safe_title = title.replace(" ", "_").replace("/", "_")
        save_path = os.path.join(save_dir, f"{safe_title}.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()


    def _visualisation_engine(self, angle_data, slope, intercept, merged_x, save_dir):
        '''
        可视化多半径角度数据及其整体线性拟合结果。

        输入：
        - angle_data: 各半径对应的角度数据字典，键为半径，值为角度数组
        - slope: 整体线性拟合斜率
        - intercept: 整体线性拟合截距
        - merged_x: 参与整体拟合的合并横坐标序列
        - save_dir: 图像保存目录

        输出：
        - 无显式返回
        - 副作用：
        - 在 save_dir 下保存名为
            "Changing_of_angles_under_different_curvature_(processed).png" 的图像文件

        说明：
        - 半径为 0 的曲线不会参与绘制
        - 每条曲线的有效长度取 min(len(angles), len(self.samp_dist))
        - 拟合线按 y = slope * merged_x + intercept 绘制
        '''
        # ---------- 创建保存路径 ----------
        title = "Changing of angles under different curvature (processed)"

        plt.figure(figsize=(12, 8))

        # ---------- 原始数据 -----------
        for radius, angles in angle_data.items():
            if radius == 0:
                continue

            valid_length = min(len(angles), len(self.samp_dist))
            plt.plot(self.samp_dist[:valid_length],
                    angles[:valid_length],
                    'o-', markersize=4,
                    label=f'R={radius}')

        # ----------- 拟合直线 -----------
        fit_curve = slope * np.array(merged_x) + intercept
        plt.plot(merged_x, fit_curve,
                'r--', lw=2,
                label=f'fitting results: y={slope:.2f}x + {intercept:.2f}')

        # ----------- 图形参数 -----------
        plt.xlabel('sampling distance(m)', fontsize=12)
        plt.ylabel('Angle(rad)', fontsize=12)
        plt.title(title, fontsize=14)
        plt.legend(loc='upper right', fontsize=10)
        plt.grid(alpha=0.3)
        plt.tight_layout()

        # ----------- 保存并关闭 -----------
        safe_title = title.replace(" ", "_").replace("/", "_")
        save_path = os.path.join(save_dir, f"{safe_title}.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

    def _visualise_ensemble_fit(self, angle_data, global_fit, individual_fits, save_dir):
        """
        可视化多半径分段全局拟合与单半径分段拟合结果对比。

        输入：
        - angle_data: 各半径对应的角度数据字典，键为半径，值为角度数组
        - global_fit: 全局分段拟合结果，格式为 [(斜率, 截距), ...]
        - individual_fits: 单半径分段拟合结果字典，键为半径，值为该半径的分段拟合结果列表
        - save_dir: 图像保存目录

        输出：
        - 无显式返回
        - 副作用：
            - 在 save_dir 下保存名为
            "Multi-Radius_Segmented_Linear_Fitting.png" 的图像文件

        说明：
        - 原始数据散点会跳过半径为 0 的情况；
        - 对每条非零半径曲线，当前实现绘制散点时会跳过第一个采样点；
        - 全局拟合线基于所有非零半径曲线拼接后的 combined_x 绘制；
        - 单半径拟合线只取 individual_fits 中的第一个半径作为示例进行绘制。
        """
        # ----------- 创建保存路径 -----------
        title = "Multi-Radius Segmented Linear Fitting"

        plt.figure(figsize=(15, 8))

        # ----------- 所有原始数据 -----------
        for radius, angles in angle_data.items():
            if radius == 0:
                continue

            valid_length = min(len(angles), len(self.samp_dist))
            x = self.samp_dist[1:valid_length]
            y = angles[1:valid_length]

            plt.plot(x, y,
                    'o', markersize=4,
                    alpha=0.5,
                    label=f'Radius {radius} Data')

        # ----------- 全局拟合线 -----------
        combined_x = np.concatenate([self.samp_dist[:min(len(self.samp_dist), len(angles))] for radius, angles in angle_data.items() if radius != 0])

        for (slope, intercept), (start, end) in zip(global_fit, self._calculate_segments(total_points=len(combined_x))):

            if not np.isnan(slope):
                x_seg = combined_x[start:end]
                y_fit = slope * x_seg + intercept
                plt.plot(x_seg, y_fit, 'k--', lw=3, label='Global Fit' if start == 0 else None)

        # ----------- 单半径拟合线 -----------
        sample_radius = next(iter(individual_fits))
        for (slope, intercept), (start, end) in zip(individual_fits[sample_radius], self._calculate_segments(total_points=len(self.samp_dist))):

            if not np.isnan(slope):
                x_seg = self.samp_dist[start:end]
                y_fit = slope * x_seg + intercept
                plt.plot(x_seg, y_fit, 'r-', lw=2, label='Individual Fit' if start == 0 else None)

        # ----------- 图形参数 -----------
        plt.xlabel('Sample Distance (m)')
        plt.ylabel('Unwrapped Angle (rad)')
        plt.title(title)
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()

        # ----------- 保存并关闭 -----------
        safe_title = title.replace(" ", "_").replace("/", "_")
        save_path = os.path.join(save_dir, f"{safe_title}.png")

        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()

    def show_reconstruction(self, direct, rs, interp_dist, showanime=False):
        """
        将各标定形状的三维重构结果与理论曲线进行可视化，并保存旋转动画。

        步骤：
        1. 创建当前方向与旋转角度对应的重构结果保存目录。
        2. 对 rs 中的每个标定形状构造对应的理想曲线 ideals。
        3. 调用 _plot_reconstruction() 在三维坐标系中绘制重构曲线与理想曲线。
        4. 使用 matplotlib.animation.FuncAnimation 生成旋转视角动画并保存为 mp4 文件。
        5. 若 showanime=True，则额外弹出静态三维图进行显示。

        输入：
        - direct: 当前实验方向
        - rs: 按标定形状组织的重构结果字典
        - interp_dist: 当前重构使用的插值采样距离数组
        - showanime: 是否在保存动画之外额外显示静态图

        输出：
        - 无显式返回
        - 副作用：
            - 在 self.sensor_id/.../recon_plots/... 目录下保存各形状的 mp4 动画文件
        """
        base_save_dir = os.path.join(self.sensor_id, str(self.active_channels.keys()), str(self.segmentation), str(direct), "recon_plots", str(self.rot_ang))
        os.makedirs(base_save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for shape in rs:
            ideals = self._construct_ideals(calib_shape=shape, interp_dist=interp_dist, val_len=self.ideal_len)
            results = rs[shape]

            fig_anim = plt.figure(figsize=(10, 8))
            ax_anim = fig_anim.add_subplot(111, projection='3d')
            self._plot_reconstruction(ax_anim, results, ideals)
            ax_anim.set_title(f'3D reconstruction: shape={shape}, direct={direct}')

            shape_save_dir = os.path.join(base_save_dir, str(shape))
            os.makedirs(shape_save_dir, exist_ok=True)

            ani = animation.FuncAnimation(fig_anim, lambda num: update_view(num, ax=ax_anim), frames=np.arange(0, 180), interval=200)

            filename = os.path.join(shape_save_dir, f"reconstruction_{shape}_direct_{direct}_{timestamp}.mp4")
            ani.save(filename, writer="ffmpeg", fps=10)
            plt.close(fig_anim)

            if showanime:
                fig_show = plt.figure(figsize=(10, 8))
                ax_show = fig_show.add_subplot(111, projection='3d')
                self._plot_reconstruction(ax_show, results, ideals)
                ax_show.set_title(f'3D reconstruction: shape={shape}, direct={direct}')
                plt.show()
                plt.close(fig_show)

    def _plot_reconstruction(self, ax, results, ideals):
        """
        在给定三维坐标轴上绘制重构曲线与对应的理论曲线。

        步骤：
        1. 递归获取 results 中所有叶子路径。
        2. 遍历每条路径，分别提取对应的重构曲线与理想曲线。
        3. 使用不同颜色与标记绘制重构结果，并以同色虚线绘制理论曲线。
        4. 根据所有重构点的范围统一设置三维坐标轴比例与显示范围。

        输入：
        - ax: matplotlib 的 3D 坐标轴对象
        - results: 重构结果字典
        - ideals: 与 results 结构对应的理想曲线字典

        输出：
        - 无显式返回
        - 副作用：
            - 直接在 ax 上完成绘图与坐标轴设置
        """
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
        markers = ['o', '^', 's', 'D', 'x', '*', 'v']

        paths = dict_recur_paths(results)

        all_points = dict_recur_value(d=results)
        x_min, x_max = np.min(all_points[:, :, 0]), np.max(all_points[:, :, 0])
        y_min, y_max = np.min(all_points[:, :, 1]), np.max(all_points[:, :, 1])
        z_min, z_max = np.min(all_points[:, :, 2]), np.max(all_points[:, :, 2])

        for i, path in enumerate(paths):
            color = colors[i % len(colors)]
            marker = markers[i % len(markers)]

            r_result = results
            r_ideal = ideals
            for k in path:
                r_result = r_result[k]
                r_ideal = r_ideal[k]

            ax.plot(r_result[:, 0], r_result[:, 1], r_result[:, 2], color=color, marker=marker, markevery=10, markersize=5, label='result-' + '-'.join(map(str, path)))

            ax.plot(r_ideal[:, 0], r_ideal[:, 1], r_ideal[:, 2], color=color, linestyle='--', linewidth=2, markevery=10, markersize=5, label='ideal-' + '-'.join(map(str, path)))

        ranges = max(x_max - x_min, y_max - y_min, z_max - z_min)
        center_x = (x_max + x_min) / 2
        center_y = (y_max + y_min) / 2
        center_z = (z_max + z_min) / 2

        ax.set_xlim(center_x - ranges / 2, center_x + ranges / 2)
        ax.set_ylim(center_y - ranges / 2, center_y + ranges / 2)
        ax.set_zlim(center_z - ranges / 2, center_z + ranges / 2)

        ax.view_init(elev=0, azim=90)
        ax.set_xlabel('X-axis (m)')
        ax.set_ylabel('Y-axis (m)')
        ax.set_zlabel('Z-axis (m)')
        ax.legend()

    def _linear_fit_processor(self, angle_data):
        '''
        对多半径角度数据做整体线性拟合。

        输入：
        - angle_data: 各半径对应的角度数据字典，键为半径，值为角度数组

        输出：
        - slope: 拟合斜率
        - intercept: 拟合截距
        - merged_x: 参与拟合的合并横坐标列表
        - merged_y: 参与拟合的合并纵坐标列表

        说明：
        - 半径为 0 的数据不会参与拟合
        - 每条曲线的有效长度取 min(len(angles), len(self.samp_dist))
        - 最终使用所有非零半径数据拼接后的 merged_x / merged_y 做一次整体线性回归
        '''
        merged_x, merged_y = [], []
        
        # 数据预处理流程
        for radius, angles in angle_data.items():
            if radius == 0:
                continue
            
            # 数据对齐校准
            valid_length = min(len(angles), len(self.samp_dist))
            merged_x.extend(self.samp_dist[:valid_length])
            merged_y.extend(angles[:valid_length])
        
        # 执行线性回归
        slope, intercept = stats.linregress(merged_x, merged_y)[:2]
        return slope, intercept, merged_x, merged_y
    
    def plot_curve_with_tnb(self, dist, r, T=None, N=None, B=None, scale=1.0, arrow_length=0.1):
        """
        绘制曲线及每个点处的切向量、法向量、副法向量（如果提供）。
        
        参数:
        - r: ndarray (N x 3)，曲线上每个点的位置向量。
        - T: ndarray (N x 3) 或 None，每个点处的切向量。如果为 None，则不绘制。
        - N: ndarray (N x 3) 或 None，每个点处的法向量。如果为 None，则不绘制。
        - B: ndarray (N x 3) 或 None，每个点处的副法向量。如果为 None，则不绘制。
        - dist: 螺距信息
        - scale: float，法向量和副法向量的缩放因子。
        - arrow_length: float，箭头的长度。
        """
        # 确保输入是 NumPy 数组
        r = np.array(r)
        
        # 检查输入形状是否一致
        if T is not None:
            T = np.array(T)
            if r.shape != T.shape:
                raise ValueError("r 和 T 必须具有相同的形状")
        if N is not None:
            N = np.array(N)
            if r.shape != N.shape:
                raise ValueError("r 和 N 必须具有相同的形状")
        if B is not None:
            B = np.array(B)
            if r.shape != B.shape:
                raise ValueError("r 和 B 必须具有相同的形状")
        
        # 创建 3D 图形
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # 绘制曲线
        ax.plot(r[:, 0], r[:, 1], r[:, 2], label="Curve", color='blue')
        
        # 绘制每个点的 T、N 和 B 向量
        for i in range(len(r)):
            # 当前点
            p = r[i]
            
            # 绘制切向量 T（如果提供）
            if T is not None:
                ax.quiver(
                    p[0], p[1], p[2],  # 起点
                    T[i, 0], T[i, 1], T[i, 2],  # 切向量方向
                    color='red', length=arrow_length, normalize=True, label='T' if i == 0 else ""
                )
            
            # 绘制法向量 N（如果提供）
            if N is not None:
                ax.quiver(
                    p[0], p[1], p[2],
                    N[i, 0], N[i, 1], N[i, 2],
                    color='green', length=arrow_length * scale, normalize=True, label='N' if i == 0 else ""
                )
            
            # 绘制副法向量 B（如果提供）
            if B is not None:
                ax.quiver(
                    p[0], p[1], p[2],
                    B[i, 0], B[i, 1], B[i, 2],
                    color='purple', length=arrow_length * scale, normalize=True, label='B' if i == 0 else ""
                )
        
        # 固定坐标轴范围
        ax.set(xlim=(-0.1, 0.3), ylim=(-0.25, 0.15), zlim=(-0.2, 0.2))
        # ax.set(xlim=(0.0, 1.2), ylim=(-0.6, 0.2), zlim=(-0.4, 0.4))
        
        # 设置图例
        ax.legend(loc='upper left')
        
        # 设置轴标签
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        
        # 设置标题
        ax.set_title(f"Curve with T, N, B vectors in {dist}")
        
        # 设置视角
        ax.view_init(elev=30, azim=60)
        
        # 显示图形
        plt.show()
