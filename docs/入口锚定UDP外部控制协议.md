# 入口锚定 UDP 外部控制协议

## 1. 网络与编码

- Demonstrator 监听：`0.0.0.0:8888/UDP`。
- 报文编码：UTF-8 JSON，每个 UDP datagram 对应一条完整命令。
- 距离单位：`entrance_offset_m` 为 m；`insert_dis` 为 mm。
- UDP 中的 `entrance_offset_m` 表示从导管物理末端沿重构曲线向回量到入口的距离。重构曲线的虚拟末端已包含 `end_value`，与导管物理末端对齐，因此算法直接使用该距离，不再减去 `end_value` 或额外的末端后缩量。
- 控制命令是单向输入。Demonstrator 不向命令来源回发任何 ACK/NACK UDP 报文，避免控制消息混入外部软件接收的 `sendObj` 数据流。
- 命令执行成功、失败及 `anchor_status` 状态只打印在 Demonstrator 本机命令行。

`request_id` 可由调用方生成，仅用于 Demonstrator 本机日志追踪，不会通过 UDP 回传。

## 2. 启动 Demonstrator

默认入口距离为 0.06 m（从重构曲线虚拟末端向回量 60 mm）。可在启动时分别启用平移和旋转锚定：

```powershell
python main.py --task demo --anchor_translation_enabled --anchor_rotation_enabled --anchor_offset_m 0.06
```

只固定入口位置时仅传 `--anchor_translation_enabled`；只稳定入口切向时仅传
`--anchor_rotation_enabled`。旋转单独开启时围绕当前入口点作无滚转的最小旋转，
只对齐切向 `T`，不使用 `Y/Z`，因此不会引入入口平移或绕 `T` 的滚转。
旧参数 `--anchor_constraint_enabled` 继续兼容，等价于同时开启两项。

也可以不在启动时启用，待程序运行后使用 `anchor_configure` 开启。

## 3. 配置并重新锚定

发送：

```json
{
  "cmd": "anchor_configure",
  "request_id": "cfg-0001",
  "data": {
    "enabled": true,
    "entrance_offset_m": 0.07,
    "reset": true
  }
}
```

等价进程内调用：

```python
demo.configure_anchor_constraint(
    enabled=True,
    entrance_offset_m=0.07,
    reset=True,
)
```

上例中外部发送 0.07 m，锚定算法与进程内接口均直接使用 0.07 m，从已对齐物理导管末端的重构曲线虚拟点向回量取。

约束：

- `enabled` 必须是 JSON boolean，不能传字符串 `"true"`/`"false"`。
- `entrance_offset_m` 必须是有限的非负数，单位 m；负数会被拒绝，原锚定状态保持不变。
- `reset` 必须是 JSON boolean；省略时默认为 `true`。
- 修改 `entrance_offset_m` 时推荐始终使用 `reset=true`。

`reset=true` 会同时清除固定入口坐标、入口参考切向、推进量零点和上次相对推进量。下一帧重构曲线从末端沿三维光纤中心线反向累计有效入口距离，并在线段内插值得到入口位置；固定 `anchor_m` 直接取该曲线入口点，不再沿全局 X 负方向计算。位置和经过 `rot_matrix` 的切向 `T` 使用同一个反向弧长位置。当前最新的有限非零机械臂读数会在下一帧成为新推进量零点。UDP 的旧 `enabled` 字段仍同时开关平移与旋转，状态查询额外返回 `translation_enabled` 和 `rotation_enabled`。

后续帧先把当前入口点平移到固定入口坐标，再绕该坐标以最小旋转转动整条曲线，使当前入口切向 `T` 对齐参考切向。该旋转不使用 `Y/Z`，也不附加绕 `T` 的滚转。末端 `End_pose` 继续保留 `Y_end/Z_end` 反向绕 `T_end` 旋转 `rot_ang` 的既有协议补偿，随后再乘同一个入口锚定旋转矩阵。

## 4. 仅 reset 当前锚定会话

发送：

```json
{
  "cmd": "anchor_reset",
  "request_id": "reset-0001"
}
```

该命令保留当前 `enabled` 和 `entrance_offset_m`，只清空：

- `anchor_m`；
- `anchor_frame`；
- `insertion_baseline_mm`；
- `last_relative_insert_mm`。

## 5. 在 Demonstrator 命令行查询实际状态

发送：

```json
{
  "cmd": "anchor_status",
  "request_id": "status-0001"
}
```

该命令不会产生 UDP 回包。Demonstrator 本机命令行会打印类似状态：

```json
{
    "enabled": true,
    "entrance_offset_m": 0.06,
    "anchor_initialized": true,
    "anchor_frame_initialized": true,
    "anchor_m": [0.13, 0.0, 0.0],
    "anchor_frame": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    "insertion_baseline_mm": 156.8,
    "last_relative_insert_mm": 10.0,
    "insert_value_mm": 166.8
}
```

配置/reset 执行后，命令行短暂显示 `anchor_initialized=false`、`anchor_frame_initialized=false` 是正常状态：新固定入口和参考切向都要等下一帧曲线才能同时建立。为兼容既有协议，状态字段仍保留 `anchor_frame` 名称，但其中 Y/Z 只作诊断，不参与锚定旋转。

## 6. 推进量输入

保留原协议：

```json
{
  "cmd": "insert_dis",
  "request_id": "insert-0001",
  "data": 166.8
}
```

`data` 必须是一个有限数，单位 mm。前导零或后续零由锚定状态机视为占位/掉线值，不会改变推进零点或最后有效相对推进量。

## 7. 错误处理

非法 JSON、未知命令、错误类型、NaN、无穷值或负入口距离不会终止 UDP 接收线程，也不会产生 UDP 回包。错误只打印在 Demonstrator 本机命令行，例如：

```text
UDP命令执行失败: cmd=anchor_configure, error=enabled must be a JSON boolean
```

失败配置不会部分修改原有锚定状态。

## 8. Python 调用示例

```python
import json
import socket

DEMO_ADDRESS = ("192.168.1.100", 8888)  # 替换为运行 demo 的电脑 IP

command = {
    "cmd": "anchor_configure",
    "request_id": "cfg-0001",
    "data": {
        "enabled": True,
        "entrance_offset_m": 0.07,  # 从重构曲线虚拟末端向回量 70 mm
        "reset": True,
    },
}

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.sendto(json.dumps(command).encode("utf-8"), DEMO_ADDRESS)
```

生产接入建议：外部调用方发送后不要等待 UDP 响应。UDP 可能丢包、乱序或重复，且当前没有服务端去重，因此 reset/configure 命令不得并发或自动重复发送。如需可靠的执行确认，应另行约定独立的控制反馈端口，不能复用 `sendObj` 数据端口。
