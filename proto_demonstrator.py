import pickle
import queue
import os
#import datetime
from datetime import datetime
import time
import vtk
import threading
import numpy as np

from collections import deque
from scipy.spatial.transform import Rotation as R
from numpy.linalg import pinv
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QSpinBox, QPushButton
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5.QtCore import Qt, QTimer

import IMU

# ==============================================================================
# 数据记录器类：用于后台异步保存数据，避免阻塞 VTK 渲染主线程
# ==============================================================================
class DataRecorder:
    def __init__(self, filename_prefix="ShapeData"):
        start_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"{filename_prefix}_{start_str}.pkl"
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        print(f"--- 数据记录已启动，保存至: {self.filename} ---")

    def save(self, timestamp, r_results, end_pose, cur_interp, row_bad, calib_data):
        """
        将当前帧的重构结果打包后放入后台写入队列。

        步骤：
        1. 若记录器已停止运行，则直接返回。
        2. 将输入的时间戳、重构结果、末端姿态和曲率插值结果打包为字典。
        3. 对支持 copy() 的对象做浅拷贝，避免后续主线程修改影响已排队的数据。
        4. 以非阻塞方式将数据包放入 self.queue。
        5. 若队列已满，则直接丢弃当前帧，保证渲染实时性。

        输入：
        - timestamp: 当前帧时间戳
        - r_results: 当前帧的重构三维轨迹结果
        - end_pose: 当前帧末端姿态
        - cur_interp: 当前帧插值后的曲率序列

        输出：
        - 无显式返回
        - 副作用：
            - 向后台写入队列 self.queue 中加入一个数据包

        说明：
        - 当前 self.queue 未设置 maxsize，因此 put(block=False) 通常不会因队列满而失败。
        - 若未来将 self.queue 改为有界队列，则 queue.Full 分支会丢弃当前帧，以避免阻塞渲染线程。
        """
        if not self.running:
            return
        try:
            data_packet = {
                'timestamp': timestamp,
                'r_results': r_results.copy() if hasattr(r_results, 'copy') else r_results,
                'end_pose': end_pose.copy() if hasattr(end_pose, 'copy') else end_pose,
                'cur_interp': list(cur_interp) if cur_interp is not None else [],
                'row_bad': row_bad if cur_interp is not None else [],
                'calib_data': calib_data if calib_data is not None else []
            }
            # 非阻塞放入，保证渲染实时性
            self.queue.put(data_packet, block=False)
        except queue.Full:
            pass 

    def _worker(self):
        """
        后台循环消费写入队列，并将数据逐包序列化保存到 pkl 文件。

        步骤：
        1. 以写入模式打开当前记录文件。
        2. 在 self.running 为 True 或队列仍非空时持续循环。
        3. 尝试从 self.queue 中取出一个数据包。
        4. 使用 pickle.dump 将数据包顺序写入文件。
        5. 写入成功后调用 task_done 标记当前任务完成。
        6. 当队列暂时为空时继续等待；若写入过程异常，则打印错误信息。

        输入：
        - 无（使用实例中的 self.filename、self.queue 与 self.running）

        输出：
        - 无显式返回
        - 副作用：
            - 持续向 self.filename 对应的 pkl 文件中追加序列化数据包

        说明：
        - 该方法设计为后台守护线程入口函数
        - 文件会在 with 代码块结束后自动关闭
        """
        with open(self.filename, 'wb') as f:
            while self.running or not self.queue.empty():
                try:
                    data = self.queue.get(timeout=0.1)
                    pickle.dump(data, f)
                    self.queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"写入错误: {e}")

    def stop(self):
        self.running = False
        self.thread.join()
        print(f"--- 数据记录结束，文件已关闭 ---")

class Demonstrator(QMainWindow):
    def __init__(self, recon, total_scale, unwrap_threshold, align_threshold, imu=False, imu_com='COM6', imu_maxlen=10, demo_recorder=False, title="Viewer", body_model_path="./model.stl", entry_length_cm=0, max_curvature=2.3, back_num=8, entry_exclude=20, t2_smooth_window=3, enable_t_align=True, clip_pct=0.38, clip_k=3.0, still_rms_th=0.05, still_hold_frames=10):
        super().__init__()

        self.setWindowTitle(title)
        self.recon = recon

        self.demo_recorder = demo_recorder
        if self.demo_recorder:
            self.recorder = DataRecorder(filename_prefix="VTK_ShapeData")
        else:
            self.recorder = None

        # imu相关参数
        self.imu = imu
        self.imu_com = imu_com
        self.imu_lock = threading.Lock() if imu else None
        self.imu_data_queue = deque(maxlen=imu_maxlen) if imu else None

        # 展示效果控制参数
        self.curve_history = deque(maxlen=self.recon.move_filter)
        self.prev_reordered_data = None
        self.total_scale = total_scale

        self.unwrap_threshold = unwrap_threshold
        self.align_threshold = align_threshold
        self.angle_prev = None
        self.angle_unwrap_prev = None

        # 人体模型/入口点显示参数
        self.body_model_path = body_model_path
        self.show_body = False
        self.stl_actor = None
        self.entry_length_cm = float(entry_length_cm)
        self.entry_anchor_world = None
        self.lastPoint = None
        self.last_entry_point = None
        self.body_model_scale = 16000
        self.body_model_offset = np.array([-9000.0, 0.0, 0.0], dtype=float)

        # 曲率入口识别参数。默认关闭，点击“曲率计算”后切换为曲率入口模式。
        self.curvature_action = False
        self.max_curvature = float(max_curvature)
        self.back_num = int(back_num)
        self.entry_exclude = int(entry_exclude)

        # 入口 T 向量对齐与滤波参数。沿用旧版逻辑：仅在不显示人体模型时启用。
        self.enable_t_align = bool(enable_t_align)
        self.T2_history = deque(maxlen=max(1, int(t2_smooth_window)))

        # 显示人体时的坐标截断 clipping 与静止冻结 freeze 参数。
        self.prev_r = None
        self.clip_pct = float(clip_pct)
        self.clip_k = float(clip_k)
        self.prev_out = None
        self.still_rms_th = float(still_rms_th)
        self.still_hold_frames = int(still_hold_frames)
        self._still_counter = 0
        self.force_unfreeze = False

        if hasattr(self.recon, 'ad_samp_dist') and len(self.recon.ad_samp_dist) > 0:
            self.fibre_length_cm = float(np.max(self.recon.ad_samp_dist) * 100.0)
        else:
            self.fibre_length_cm = 135.0

        self.firstFocal = None
        self.firstPosition = None
        self.setWindowTitle("3D Shape Visualization")
        self.setGeometry(100, 100, 1000, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # 顶部控制栏：手动设置入体长度，并控制人体 STL 模型显示
        self.controls_layout = QHBoxLayout()
        self.entry_label = QLabel("入体长度(cm):")
        self.entry_input = QSpinBox()
        self.entry_input.setRange(0, max(1, int(np.ceil(self.fibre_length_cm))))
        self.entry_input.setValue(max(0, min(int(round(self.entry_length_cm)), int(np.ceil(self.fibre_length_cm)))))
        self.entry_input.valueChanged.connect(self.on_entry_length_changed)
        self.controls_layout.addWidget(self.entry_label)
        self.controls_layout.addWidget(self.entry_input)

        self.curvature_button = QPushButton("曲率计算")
        self.curvature_button.clicked.connect(self.on_curvature_clicked)
        self.controls_layout.addWidget(self.curvature_button)

        self.show_model_button = QPushButton("显示模型")
        self.show_model_button.clicked.connect(self.on_show_model_clicked)
        self.controls_layout.addWidget(self.show_model_button)

        self.unfreeze_button = QPushButton("自动校准")
        self.unfreeze_button.clicked.connect(self.on_unfreeze_clicked)
        self.controls_layout.addWidget(self.unfreeze_button)

        self.layout.addLayout(self.controls_layout)

        self.vtk_widget = QVTKRenderWindowInteractor(self.central_widget)
        self.layout.addWidget(self.vtk_widget, 1)

        self.renderer = vtk.vtkRenderer()
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.renderer.SetBackground(0.2, 0.2, 0.2)

        self.add_ball()
        self.add_axes()
        self.add_model()

        self.points = vtk.vtkPoints()
        self.lines = vtk.vtkCellArray()
        self.colors = vtk.vtkUnsignedCharArray()
        self.colors.SetNumberOfComponents(3)
        self.colors.SetName("Colors")

        self.line_polydata = vtk.vtkPolyData()
        self.line_polydata.SetPoints(self.points)
        self.line_polydata.SetLines(self.lines)

        self.line_mapper = vtk.vtkPolyDataMapper()
        self.line_mapper.SetInputData(self.line_polydata)
        self.line_actor = vtk.vtkActor()
        self.line_actor.SetMapper(self.line_mapper)
        self.line_actor.GetProperty().SetLineWidth(2)
        self.line_mapper.SetScalarModeToUsePointData()
        self.line_mapper.SetScalarVisibility(True)

        self.renderer.AddActor(self.line_actor)
        self.renderer.ResetCamera()

        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)
        self.interactor.Initialize()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_vtk)
        self.timer.start(int(1000 / self.recon.data_freq))  

    def add_model(self):
        """
        读取人体 STL 模型并加入 VTK 场景。

        说明：
        - 默认读取 self.body_model_path，通常为 "./model.stl"。
        - 初始状态隐藏，点击“显示模型”按钮后显示。
        - 具体位置会在 _update_body_model_transform() 中根据入口点实时更新。
        """
        model_path = self.body_model_path
        if not model_path:
            return

        if not os.path.isabs(model_path):
            local_path = os.path.join(os.path.dirname(__file__), model_path)
            if os.path.exists(local_path):
                model_path = local_path

        if not os.path.exists(model_path):
            print(f"[Warning] 未找到人体模型 STL 文件: {self.body_model_path}")
            return

        stl_reader = vtk.vtkSTLReader()
        stl_reader.SetFileName(model_path)
        stl_reader.Update()

        stl_mapper = vtk.vtkPolyDataMapper()
        stl_mapper.SetInputConnection(stl_reader.GetOutputPort())

        self.stl_actor = vtk.vtkActor()
        self.stl_actor.SetMapper(stl_mapper)
        self.stl_actor.GetProperty().SetOpacity(0.1)

        transform = vtk.vtkTransform()
        transform.Scale(self.body_model_scale, self.body_model_scale, self.body_model_scale)
        transform.RotateY(90)
        transform.RotateZ(270)
        self.stl_actor.SetUserTransform(transform)

        self.stl_actor.SetVisibility(False)
        self.renderer.AddActor(self.stl_actor)

    def _get_manual_entry_idx(self, num_points):
        """
        根据当前手动入体长度换算入口点索引。

        约定：
        - entry_length_cm = 0 时，入口点在末端附近；
        - entry_length_cm = fibre_length_cm 时，入口点在起点附近。
        """
        if num_points <= 0:
            return 0

        fibre_length_cm = max(float(self.fibre_length_cm), 1e-12)
        entry_length_cm = max(0.0, min(float(self.entry_length_cm), fibre_length_cm))
        first_idx = int((1.0 - entry_length_cm / fibre_length_cm) * num_points)
        return max(0, min(num_points - 1, first_idx))

    def _get_entry_idx(self, num_points, curvature=None):
        """
        获取入口点索引。

        - 默认使用手动入体长度；
        - 若已点击“曲率计算”并提供 curvature，则使用曲率阈值入口识别；
        - 若曲率数据不可用或识别失败，则回退到手动入口点。
        """
        if num_points <= 0:
            return 0

        if self.curvature_action and curvature is not None:
            return self.calc_min_curvature(curvature, num_points=num_points)

        return self._get_manual_entry_idx(num_points)

    def calc_min_curvature(self, curvature, num_points=None):
        """
        曲率入口识别：从 entry_exclude 后开始寻找第一个超过 max_curvature 的位置，
        找到后向后退 back_num 个点作为入口点。

        如果没有找到超过阈值的位置，则回退到手动入口点，避免入口点突然跳到错误位置。
        """
        if curvature is None:
            return self._get_manual_entry_idx(num_points or 0)

        cur = np.asarray(curvature, dtype=float).reshape(-1)
        if cur.size == 0:
            return self._get_manual_entry_idx(num_points or 0)

        n = int(num_points) if num_points is not None else cur.size
        n = max(1, min(n, cur.size))
        start = max(0, min(int(self.entry_exclude), n - 1))

        valid_idx = np.where(cur[start:n] > self.max_curvature)[0]
        if valid_idx.size == 0:
            return self._get_manual_entry_idx(n)

        first_idx = int(valid_idx[0] + start - self.back_num)
        first_idx = max(0, min(n - 1, first_idx))
        return first_idx

    def _as_curve_array(self, data, name="data"):
        """
        将输入曲线整理成 (N, 3) 数组，并做有限值保护。
        """
        arr = np.asarray(data, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 3:
            if arr.ndim == 2 and arr.shape[0] == 3:
                arr = arr.T
            else:
                raise ValueError(f"Unexpected {name} shape: {arr.shape}")

        if not np.isfinite(arr).all():
            if name == "r_results_postrot" and self.prev_r is not None and self.prev_r.shape == arr.shape:
                arr = self.prev_r.copy()
            else:
                arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        return arr

    def _apply_body_clipping(self, data, first_idx):
        """
        显示人体模型时，对当前帧相对上一帧的点位移做百分比截断。
        """
        cur = self._as_curve_array(data, name="r_results_postrot")

        if not self.show_body:
            self.prev_r = cur.copy()
            return cur

        if self.prev_r is not None:
            prev = self.prev_r
            if prev.shape != cur.shape:
                n = min(prev.shape[0], cur.shape[0])
                prev = prev[:n]
                cur = cur[:n]
                first_idx = min(first_idx, n - 1)

            prev_in = prev[first_idx:]
            seg = np.diff(prev_in, axis=0)
            seg_len = np.linalg.norm(seg, axis=1)
            d_med = np.median(seg_len) if seg_len.size else 0.0
            max_step = max(1e-6, self.clip_pct * self.clip_k * d_med)

            diff = cur - prev
            step = np.linalg.norm(diff, axis=1, keepdims=True)
            scale = np.minimum(1.0, max_step / (step + 1e-12))
            clipped = prev + diff * scale

            alpha = np.ones((cur.shape[0], 1), dtype=float)
            if first_idx > 0:
                t = np.arange(first_idx, dtype=float) / float(first_idx)
                alpha[:first_idx, 0] = t * t * (3.0 - 2.0 * t)

            cur = (1.0 - alpha) * cur + alpha * clipped

        self.prev_r = cur.copy()
        return cur

    def _apply_body_freeze(self, data):
        """
        显示人体模型时，如果连续若干帧整体 RMS 位移足够小，则冻结输出曲线。
        """
        cur = self._as_curve_array(data, name="r_out")

        if not self.show_body:
            self.prev_out = None
            self._still_counter = 0
            return cur

        if self.prev_out is None:
            self.prev_out = cur.copy()
            return cur

        prev = self.prev_out
        if prev.shape != cur.shape:
            n = min(prev.shape[0], cur.shape[0])
            prev = prev[:n]
            cur = cur[:n]

        diff = cur - prev
        rms = float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))

        if rms < self.still_rms_th:
            self._still_counter += 1
        else:
            self._still_counter = 0

        if self._still_counter >= self.still_hold_frames:
            if self.force_unfreeze:
                self.force_unfreeze = False
                self._still_counter = 0
                self.prev_out = cur.copy()
                self.curve_history.clear()
                self.curve_history.append(cur.copy())
                return cur

            cur = self.prev_out.copy()
            self.curve_history.clear()
            self.curve_history.append(cur.copy())
            return cur

        self.prev_out = cur.copy()
        return cur

    def _align_entry_t(self, data, T_rot, first_idx):
        """
        入口 T 向量对齐与滤波：用入口点处的 T 向量对齐到 x 轴。

        复刻旧版行为：只在不显示人体模型时启用；显示人体模型时清空历史，
        避免下次切回非人体模式时带入旧方向。
        """
        if not self.enable_t_align or T_rot is None:
            return data

        if self.show_body:
            self.T2_history.clear()
            return data

        try:
            T_arr = np.asarray(T_rot, dtype=float)
            if T_arr.ndim != 2 or T_arr.shape[1] != 3:
                if T_arr.ndim == 2 and T_arr.shape[0] == 3:
                    T_arr = T_arr.T
                else:
                    return data

            first_idx = max(0, min(len(data) - 1, int(first_idx)))
            T2 = np.asarray(T_arr[first_idx], dtype=float)
            n = float(np.linalg.norm(T2))

            if n < 1e-12:
                if len(self.T2_history) > 0:
                    T2_use = np.mean(np.array(self.T2_history), axis=0)
                    T2_use /= (np.linalg.norm(T2_use) + 1e-12)
                else:
                    T2_use = np.array([1.0, 0.0, 0.0], dtype=float)
            else:
                T2_unit = T2 / n
                self.T2_history.append(T2_unit)

                if len(self.T2_history) == self.T2_history.maxlen:
                    T2_use = np.mean(np.array(self.T2_history), axis=0)
                    T2_use /= (np.linalg.norm(T2_use) + 1e-12)
                else:
                    T2_use = T2_unit

            target_direction = np.array([1.0, 0.0, 0.0], dtype=float)
            rot_matrix = self.align_vector_to_target(T2_use, target_direction)

            center = np.asarray(data[first_idx], dtype=float)
            data_np = np.asarray(data, dtype=float).copy()
            data_np = (rot_matrix @ (data_np - center).T).T + center
            return data_np

        except Exception as e:
            print(f"[Warning] 入口T向量对齐失败: {e}")
            return data

    def align_vector_to_target(self, v, target):
        """
        将向量 v 旋转到与 target 对齐。
        """
        v = np.asarray(v, dtype=float)
        target = np.asarray(target, dtype=float)

        vn = np.linalg.norm(v)
        tn = np.linalg.norm(target)
        if vn < 1e-12 or tn < 1e-12:
            return np.eye(3)

        v = v / vn
        target = target / tn

        if np.allclose(v, target):
            return np.eye(3)

        if np.allclose(v, -target):
            # 180 度旋转时选一个与 v 不平行的轴，避免直接返回 -I 造成反射。
            ref = np.array([1.0, 0.0, 0.0])
            if abs(np.dot(v, ref)) > 0.9:
                ref = np.array([0.0, 1.0, 0.0])
            axis = np.cross(v, ref)
            axis /= (np.linalg.norm(axis) + 1e-12)
            angle = np.pi
        else:
            axis = np.cross(v, target)
            axis /= (np.linalg.norm(axis) + 1e-12)
            angle = float(np.arccos(np.clip(np.dot(v, target), -1.0, 1.0)))

        K = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
        return np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * (K @ K)

    def _update_body_model_transform(self, data, first_idx, scale_factor):
        """
        将人体 STL 模型绑定到入口点位置。
        """
        if not self.show_body or self.stl_actor is None or len(data) == 0:
            return

        entry_point = np.asarray(data[first_idx], dtype=float) * scale_factor
        transform = vtk.vtkTransform()
        transform.Translate(entry_point[0] + self.body_model_offset[0], entry_point[1] + self.body_model_offset[1], entry_point[2] + self.body_model_offset[2])
        transform.Scale(self.body_model_scale, self.body_model_scale, self.body_model_scale)
        transform.RotateY(90)
        transform.RotateZ(270)
        self.stl_actor.SetUserTransform(transform)

        camera = self.renderer.GetActiveCamera()
        if self.firstFocal is None:
            self.firstFocal = camera.GetFocalPoint()
            self.firstPosition = camera.GetPosition()

        camera.SetFocalPoint(entry_point[0], entry_point[1], entry_point[2])

    def on_entry_length_changed(self, value):
        """
        更新手动入体长度。入口点变化后重置锚点，避免沿用旧入口点的固定位置。
        """
        self.entry_length_cm = float(value)
        self.entry_anchor_world = None
        print(f"[Input] 入体长度: {value} cm")

    def on_curvature_clicked(self):
        """
        切换曲率入口识别模式。
        """
        self.curvature_action = not self.curvature_action
        self.entry_anchor_world = None
        mode = "曲率入口识别" if self.curvature_action else "手动入体长度"
        print(f"[Action] 入口模式: {mode}")

    def on_unfreeze_clicked(self):
        """
        手动解除静止冻结，并清空显示平滑缓存。
        """
        print("[Action] 手动解冻/自动校准")
        self.force_unfreeze = True
        self._still_counter = 0
        self.prev_out = None
        self.curve_history.clear()

    def on_show_model_clicked(self):
        """
        切换人体 STL 模型显示状态。
        """
        self.show_body = not self.show_body

        if self.stl_actor is not None:
            self.stl_actor.SetVisibility(self.show_body)
            if self.show_body and self.last_entry_point is not None:
                scale_factor = 5000 * self.total_scale
                entry_point = np.asarray(self.last_entry_point, dtype=float) * scale_factor
                camera = self.renderer.GetActiveCamera()
                camera.SetFocalPoint(entry_point[0], entry_point[1], entry_point[2])
                camera.SetPosition(entry_point[0], entry_point[1], entry_point[2] + 60000)
                self.renderer.ResetCamera()
            elif not self.show_body:
                self.prev_out = None
                self._still_counter = 0
        else:
            print("[Warning] 人体模型未加载，无法显示。")

        self.vtk_widget.GetRenderWindow().Render()
        print(f"[Action] 显示模型: {self.show_body}")

    def add_ball(self):
        """
        根据采样点位置创建用于显示各采样点的球体标记，并加入渲染器。

        步骤：
        1. 根据 self.recon.ad_samp_dist 生成反向排列的采样位置索引数组 self.indexArr。
        2. 为每个采样位置创建一个 vtkSphereSource。
        3. 为每个球体建立 mapper 与 actor。
        4. 将所有球体 actor 保存到实例成员中，并加入当前 renderer。

        输入：
        - 无（使用 self.recon.ad_samp_dist）

        输出：
        - 无显式返回
        - 更新以下成员：
            - self.indexArr
            - self.sphereArr
            - self.sphereActorArr

        说明：
        - 当前实现中球体初始半径固定为 30.0，初始中心均为原点
        - 球体的实际位置会在后续 _update_frame() 中动态更新
        """
        self.indexArr = self.recon.ad_samp_dist[::-1] * 1000
        self.sphereArr = []
        self.sphereActorArr = []
        for _ in enumerate(self.indexArr):
            sphere = vtk.vtkSphereSource()
            sphere.SetRadius(30.0)
            sphere.SetCenter(0.0, 0.0, 0.0)
            sphere.SetThetaResolution(50)
            sphere.SetPhiResolution(50)
            self.sphereArr.append(sphere)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(1, 0, 0)
            self.sphereActorArr.append(actor)
            self.renderer.AddActor(actor)

    def add_axes(self):
        """
        向 VTK 场景中添加主坐标轴和右下角方向标记部件。

        步骤：
        1. 创建主坐标轴 vtkAxesActor，并设置长度、轴杆类型与标签显示。
        2. 调整主坐标轴标签字体大小。
        3. 将主坐标轴加入当前 renderer。
        4. 创建右下角方向标记坐标轴，并设置标签文字与字体大小。
        5. 使用 vtkOrientationMarkerWidget 将方向标记绑定到当前交互器并启用。

        输入：
        - 无

        输出：
        - 无显式返回
        - 副作用：
            - 向当前渲染窗口中加入主坐标轴与方向标记组件

        说明：
        - 主坐标轴用于场景内参考
        - 右下角方向标记用于交互时显示当前观察方向
        """
        # 添加坐标轴
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(1500, 1500, 1500)  # 设置坐标轴长度
        axes.SetShaftType(0)  # 设置轴杆类型为线条
        axes.SetAxisLabels(1)  # 显示轴标签

        # 调整坐标轴标签的字体大小
        axes.GetXAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(1)
        axes.GetYAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(1)
        axes.GetZAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(1)

        self.renderer.AddActor(axes)

        # 添加方向标记部件（右下角的小坐标系）
        orient_axes = vtk.vtkAxesActor()
        orient_axes.SetShaftTypeToCylinder()
        orient_axes.SetXAxisLabelText("X")  # 设置X轴标签
        orient_axes.SetYAxisLabelText("Y")  # 设置Y轴标签
        orient_axes.SetZAxisLabelText("Z")  # 设置Z轴标签

        # 调整方向标记部件的标签字体大小
        orient_axes.GetXAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(8)
        orient_axes.GetYAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(8)
        orient_axes.GetZAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(8)

        orientation_widget = vtk.vtkOrientationMarkerWidget()
        orientation_widget.SetOrientationMarker(orient_axes)
        orientation_widget.SetInteractor(self.interactor)
        orientation_widget.SetViewport(0.8, 0.0, 1.0, 0.2)  # 设置方向标记的位置（右下角）
        orientation_widget.SetEnabled(1)
        orientation_widget.InteractiveOn()

    def receive_IMU(self):
        """
        持续从 IMU 串口读取姿态数据，并将相对初始姿态的旋转矩阵写入缓存队列。

        步骤：
        1. 初始化 IMU 串口连接，并准备姿态解码所需的输出字典。
        2. 持续读取串口数据并调用 IMU.decode_data 进行解析。
        3. 将 roll、pitch、yaw 从角度转换为弧度。
        4. 在前 100 帧中累计姿态数据，用于估计初始参考姿态 R_init。
        5. 在参考姿态建立后，对每一帧新姿态计算当前旋转矩阵 R_0IMU。
        6. 通过 pinv(R_init) @ R_0IMU 计算相对初始姿态的旋转矩阵 R_initIMU。
        7. 在加锁条件下将 R_initIMU 追加到 self.imu_data_queue。

        输入：
        - 无（使用 self.imu_com、self.imu_lock 与 self.imu_data_queue）

        输出：
        - 无显式返回
        - 副作用：
            - 持续向 self.imu_data_queue 写入相对初始姿态的旋转矩阵

        说明：
        - 当前实现假定该方法通常运行在独立线程中
        - 若 IMU 初始化失败，则直接打印错误并返回
        - 当前实现只捕获了部分读取/解析异常
        """
        yis_out = {'tid':1, 'roll':0.0, 'pitch':0.0, 'yaw':0.0, 'q0':1.0, 'q1':1.0, 'q2':0.0, 'q3':0.0, 'sensor_temp':25.0, 'acc_x':0.0, 'acc_y':0.0, 'acc_z':1.0, 'gyro_x':0.0, 'gyro_y':0.0, 'gyro_z':0.0, 'norm_mag_x':0.0, 'norm_mag_y':0.0, 'norm_mag_z':0.0, 'raw_mag_x':0.0, 'raw_mag_y':0.0, 'raw_mag_z':0.0, 'lat':0.0, 'longt':0.0, 'alt':0.0, 'vel_e':0.0, 'vel_n':0.0, 'vel_u':0.0, 'ms':0, 'year': 2022, 'month':8, 'day': 31, 'hour':12, 'minute':0, 'second':0, 'samp_timestamp':0, 'dataready_timestamp':0 ,'status':0}
        roll_list = []
        pitch_list = []
        yaw_list = []
        loop_cnt = 0
        
        try:
            conn=IMU.open_serial(self.imu_com, 460800)
            print("IMU connection established.")
        except Exception as e:
            print(f"IMU initialization error: {e}")
            return

        while True:
            try:
                data = conn.read_all()
                num = len(data)
                if(num > 0):
                    ret = IMU.decode_data(data, num, yis_out, False)
                    if ret is True:
                        roll = np.deg2rad(yis_out['roll'])
                        pitch = np.deg2rad(yis_out['pitch'])
                        yaw = np.deg2rad(yis_out['yaw'])
                        if loop_cnt < 100:
                            roll_list.append(roll); pitch_list.append(pitch); yaw_list.append(yaw)
                            loop_cnt += 1
                        elif loop_cnt == 100:
                            roll_mean = np.mean(roll_list); pitch_mean = np.mean(pitch_list); yaw_mean = np.mean(yaw_list)
                            r_init = R.from_euler('xyz', (roll_mean, pitch_mean, yaw_mean))
                            R_init = r_init.as_matrix()
                            # print("R_init initialized")
                            loop_cnt += 1
                        else:
                            try:
                                r = R.from_euler('xyz', (roll, pitch, yaw))
                                R_0IMU = r.as_matrix()
                                if 'R_init' in locals():
                                    R_initIMU = pinv(R_init) @ R_0IMU
                                    with self.imu_lock:
                                        self.imu_data_queue.append(R_initIMU)
                            except Exception: pass
            except IndexError: 
                pass

    def closeEvent(self, event):
        if hasattr(self, 'recorder') and self.recorder:
            self.recorder.stop()
        super().closeEvent(event)

    def update_vtk(self):
        """
        从实时数据队列中读取一帧数据，完成预处理、重构、可选 IMU 姿态融合、平滑与 VTK 显示更新。

        步骤：
        1. 记录当前处理帧的时间戳。
        2. 以非阻塞方式从 self.recon.data_queue 中读取一帧数据；若队列为空则直接返回。
        3. 将读入数据按当前单位约定转换为 calib_Data。
        4. 若启用了中心光纤补偿，则调用 self.recon._process_centreData() 去除中心通道影响。
        5. 检查当前帧是否存在非有限值；若存在，则优先使用上一帧同位置数据进行替换，否则直接跳过本帧。
        6. 当前动态展示中 direct 固定为 0，自动方向判定逻辑仍处于注释状态。
        7. 若启用 IMU，则从 IMU 队列读取最新姿态矩阵，并据此构造初始切向量 init_T；否则使用默认 init_T。
        8. 调用 self.recon._reconstruct_frame() 完成曲率计算、unwrap、滤波、插值和三维重构；具体使用 TNB 还是 TNN 由 self.recon.frame_rule 决定。
        9. 调用 self.recon._get_rot_x(direct=0) 做方向旋转补偿。
        10. 将最近若干帧重构结果存入 self.curve_history，并在达到窗口长度后做均值平滑。
        11. 若启用 recorder，则将当前帧结果写入后台记录器。
        12. 调用 _update_frame() 将最终曲线写入 VTK 显示。

        输入：
        - 无（使用实例中的实时队列、IMU 队列与重构器参数）

        输出：
        - 无显式返回
        - 副作用：
            - 更新 self.prev_reordered_data
            - 更新 self.curve_history
            - 可能向 recorder 写入一帧记录
            - 触发一次 VTK 场景刷新

        说明：
        - 当前实现中 direct 被固定为 0，方向自动判定逻辑仍处于注释状态
        - 当前实现对含 NaN / inf 的坏行会优先尝试用上一帧对应行替换
        - 当前实现中 IMU 姿态只用于更新初始切向量 init_T
        """
        # 记录当前处理帧的时间戳
        frame_timestamp = time.time()

        # 定义初始状态
        last_valid_R_0IMU = np.eye(3)
        R_imu_rot = np.array([[0, -1, 0], [-1, 0, 0], [0, 0, -1]])

        # 修改点 1：消除竞态条件，使用非阻塞 get() 并捕获异常
        try:
            Data = self.recon.data_queue.get_nowait()
        except queue.Empty:
            return  # 队列为空，直接返回等待下一次定时器触发
        
        # ---------- 处理数据 ----------
        calib_Data = Data[0] * 1e-6
        # calib_Data = Data[0]

        # 处理中心光纤的数据
        if self.recon.centre_fibre:
            _, _, calib_Data, _ = self.recon._process_centreData(calib_Data)

        # 确保缺数、inf、异常大值、突变值不会造成展示中断
        abs_threshold = 1000 * 1e-6       # 绝对值阈值
        jump_threshold = 500 * 1e-6     # 相邻帧突变阈值

        # 1. NaN / inf / -inf
        finite_bad = ~np.isfinite(calib_Data).all(axis=1)

        # 2. 有限但绝对值异常大
        safe_abs = np.where(np.isfinite(calib_Data), np.abs(calib_Data), np.inf)
        abs_bad = safe_abs.max(axis=1) > abs_threshold

        # 3. 相比上一帧突变过大
        if self.prev_reordered_data is not None and self.prev_reordered_data.shape == calib_Data.shape:
            jump_bad = np.abs(calib_Data - self.prev_reordered_data).max(axis=1) > jump_threshold
        else:
            jump_bad = np.zeros(calib_Data.shape[0], dtype=bool)

        row_bad = finite_bad | abs_bad | jump_bad

        if np.any(row_bad):
            print(f"坏点/超量程行: {np.where(row_bad)[0].tolist()}")

            if self.prev_reordered_data is not None and self.prev_reordered_data.shape == calib_Data.shape:
                # 用上一帧同一行替换
                calib_Data = calib_Data.copy()
                calib_Data[row_bad, :] = self.prev_reordered_data[row_bad, :]
            else:
                # 第一帧就坏了：没法用上一帧补，只能跳过这一帧
                return

        self.prev_reordered_data = calib_Data.copy()

        # ---------- 判定当前方向 ----------
        # _, _, angle = self.recon._get_base(radius=None, calib_Data=calib_Data, base_slopes=self.recon.slopes[0][0], verbose=False) # 这个地方要再看，初始方向判定固定使用得是0方向的base_slope
        # init_ang = (angle[0] + np.deg2rad(self.recon.rot_ang)) % (2 * np.pi)
        # if -np.pi / 3 <= init_ang < np.pi / 3:
        #     direct = 0
        # elif np.pi / 3 <= init_ang < np.pi:
        #     direct = 120
        # else:
        #     direct = 240
        direct = 120

        # ---------- 预处理 ----------
        if self.imu:
            if self.imu_data_queue:
                with self.imu_lock:
                    R_0IMU = self.imu_data_queue[-1]  # 非阻塞获取
                    last_valid_R_0IMU = R_0IMU  # 更新最新的有效数据
            else:
                if last_valid_R_0IMU is not None:
                    # print("update_vtk is using the cached R_0IMU.")
                    R_0IMU = last_valid_R_0IMU  # 使用缓存数据
                else:
                    print("update_vtk: No valid R_0IMU available, skipping update.")
            init_T = -R_0IMU[:3, 1] @ R_imu_rot
        else:
            init_T = [1.0, 0.0, 0.0]

        # ---------- 重构 ----------
        self.angle_prev, self.angle_unwrap_prev, cur_interp, _, r, T, N, B, _ = self.recon._reconstruct_frame(keys=None, calib_shape='circ', calib_Data=calib_Data, weight=self.recon.weights[direct], slope=self.recon.slopes[direct], magnitude_ratio=1.0, init_T=init_T, verbose=False,
                                                                                            unwrap_threshold=self.unwrap_threshold, align_threshold=self.align_threshold, angle_prev=self.angle_prev, angle_unwrap_prev=self.angle_unwrap_prev)
        rot_matrix = self.recon._get_rot_x(direct=0)
        r_results_postrot = r @ rot_matrix.T
        T_rot = T @ rot_matrix.T if T is not None else None

        # 提取末端姿态 (End_pose)
        # 根据参考代码逻辑，End_pose 通常是末端节点的切向向量，即 T 的最后一行
        End_pose = self.recon._build_end_pose(
            T,
            N,
            B,
            rot_matrix=rot_matrix,
            rot_ang_deg=self.recon.rot_ang,
        )

        # ---------- 显示人体时的坐标截断 clipping ----------
        first_idx = self._get_entry_idx(len(r_results_postrot), curvature=cur_interp)
        r_results_postrot = self._apply_body_clipping(r_results_postrot, first_idx)

        # --------------  平滑滤波 --------------
        self.curve_history.append(r_results_postrot.copy())
        if len(self.curve_history) == self.recon.move_filter:
            r_results_postrot = np.mean(np.array(self.curve_history), axis=0)

        # ---------- 显示人体时的静止冻结 freeze ----------
        r_results_postrot = self._apply_body_freeze(r_results_postrot)

        if hasattr(self, 'recorder') and self.recorder:
            self.recorder.save(timestamp=frame_timestamp, r_results=r_results_postrot, end_pose=End_pose, cur_interp=cur_interp, row_bad=row_bad, calib_data=calib_Data)

        self._update_frame(r_results_postrot, T_rot=T_rot, curvature=cur_interp)

    def _update_frame(self, data, T_rot=None, curvature=None):
        """
        将当前三维重构曲线写入 VTK 点集与连线结构，并刷新显示。

        本版本额外加入：
        - 手动入体长度对应的入口点索引 first_idx；
        - 入口点世界坐标锚定；
        - 体内/体外分段染色；
        - 人体 STL 模型随入口点移动。
        """
        scale_factor = 5000 * self.total_scale
        data_np = np.asarray(data, dtype=float)

        if data_np.ndim != 2 or data_np.shape[1] != 3:
            if data_np.shape == (3, len(data_np)):
                data_np = data_np.T
            else:
                raise ValueError(f"Unexpected data shape for VTK display: {data_np.shape}")

        num_points = len(data_np)
        if num_points == 0:
            return

        first_idx = self._get_entry_idx(num_points, curvature=curvature)

        # 入口点坐标锚定：第一次进入时保存入口点位置，后续帧都把当前入口点平移回该位置。
        if self.entry_anchor_world is None:
            self.entry_anchor_world = data_np[first_idx].copy()

        delta = self.entry_anchor_world - data_np[first_idx]
        data_np = data_np + delta

        self.lastPoint = data_np[-1].copy()
        self.last_entry_point = data_np[first_idx].copy()

        # 入口 T 向量对齐与滤波：仅在不显示人体模型时启用。
        data_np = self._align_entry_t(data_np, T_rot, first_idx)
        self.lastPoint = data_np[-1].copy()
        self.last_entry_point = data_np[first_idx].copy()

        # 避免每帧 Reset()。仅在首次运行或点数变化时初始化拓扑结构。
        if self.points.GetNumberOfPoints() != num_points:
            self.points.Reset()
            self.lines.Reset()
            self.colors.Reset()

            self.points.SetNumberOfPoints(num_points)
            self.colors.SetNumberOfComponents(3)
            self.colors.SetName("Colors")
            self.colors.SetNumberOfTuples(num_points)

            self.lines.Allocate(max(num_points - 1, 0))
            for i in range(num_points - 1):
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, i)
                line.GetPointIds().SetId(1, i + 1)
                self.lines.InsertNextCell(line)

            self.line_polydata.SetPoints(self.points)
            self.line_polydata.SetLines(self.lines)
            self.line_polydata.GetPointData().SetScalars(self.colors)
        elif self.colors.GetNumberOfTuples() != num_points:
            self.colors.Reset()
            self.colors.SetNumberOfComponents(3)
            self.colors.SetName("Colors")
            self.colors.SetNumberOfTuples(num_points)
            self.line_polydata.GetPointData().SetScalars(self.colors)

        # 就地更新点坐标与体内/体外颜色。
        # 约定：first_idx 及其后的部分为体内段，显示为红色；first_idx 前为体外段，显示为白色。
        for i, point in enumerate(data_np):
            self.points.SetPoint(i, point[0] * scale_factor, point[1] * scale_factor, point[2] * scale_factor)
            if i >= first_idx:
                self.colors.SetTuple3(i, 255, 0, 0)
            else:
                self.colors.SetTuple3(i, 255, 255, 255)

        self.line_polydata.GetPointData().SetScalars(self.colors)
        self.line_mapper.SetScalarModeToUsePointData()
        self.line_mapper.SetScalarVisibility(True)

        # 更新标记球体位置，并保持与体内/体外颜色一致。
        max_len = float(self.indexArr[0]) if len(self.indexArr) > 0 and abs(float(self.indexArr[0])) > 1e-12 else 1.0
        for i, len_num in enumerate(self.indexArr):
            idx = round((float(len_num) / max_len) * num_points)
            idx = max(0, min(num_points - 1, idx))
            self.sphereArr[i].SetCenter(
                data_np[idx][0] * scale_factor,
                data_np[idx][1] * scale_factor,
                data_np[idx][2] * scale_factor
            )

            if idx >= first_idx:
                self.sphereActorArr[i].GetProperty().SetColor(1, 0, 0)
            else:
                self.sphereActorArr[i].GetProperty().SetColor(1, 1, 1)

        self._update_body_model_transform(data_np, first_idx, scale_factor)

        # 标记数据已修改，触发 VTK 渲染管线更新
        self.points.Modified()
        self.colors.Modified()
        self.line_polydata.Modified()
        self.vtk_widget.GetRenderWindow().Render()
