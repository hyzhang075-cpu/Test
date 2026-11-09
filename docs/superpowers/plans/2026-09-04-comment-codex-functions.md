# Codex 新增函数注释 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Git 历史中明确由 Codex 新增的运行时函数补齐中文函数说明和关键作用行注释，不改变程序行为。

**Architecture:** 以作者为 `Codex <codex@openai.com>` 的提交 `296c0c6`、`0c71c71` 为审计边界。对这些提交创建的入口锚定、IMU 串口和离线渲染函数补充 docstring，并在单位换算、状态冻结、弧长反查、刚体变换、原子替换等关键语句前添加作用注释。

**Tech Stack:** Python、NumPy、SciPy、Matplotlib、Plotly、Git

**Spec:** `docs/superpowers/specs/2026-08-23-entrance-anchor-constraint-design.md`；`docs/superpowers/specs/2026-08-23-dynamic-anchor-control-and-rendering-design.md`

## Global Constraints

- 仅修改注释和 docstring，不修改任何可执行语句、函数签名或数据格式。
- 注释使用中文，说明函数用途以及关键作用行的原因、单位和状态影响。
- 覆盖 Codex 创建且仍存在的运行时函数；测试函数不纳入运行时文档范围。

---

### Task 1: 入口锚定几何函数

**Files:**
- Modify: `entrance_anchor.py`
- Test: `tests/test_entrance_anchor.py`

**Interfaces:**
- Consumes: `curve_m: ndarray[N, 3]`、可选推进量和局部 `T/Y/Z` 标架。
- Produces: `AnchorConstraintResult` 和保持兼容的 `apply_entrance_anchor(...)` 曲线输出。

- [x] **Step 1: 为所有类方法和包装函数补充中文 docstring**

  说明输入单位、状态捕获、平移/旋转开关、返回内容与异常条件。

- [x] **Step 2: 为关键几何和状态语句添加作用注释**

  覆盖首个非零推进量基线、从末端反查弧长点、SVD 投影到旋转矩阵、Slerp 标架插值、平移和绕入口旋转。

- [x] **Step 3: 运行入口锚定测试**

  Run: `python -m pytest tests/test_entrance_anchor.py -q`
  Expected: PASS；注释修改不改变行为。

### Task 2: 串口与离线渲染函数

**Files:**
- Modify: `IMU.py`
- Modify: `tools/render_anchored_pickles.py`
- Test: `tests/test_render_anchored_pickles.py`

**Interfaces:**
- Consumes: IMU 串口配置、Demonstrator Pickle 帧和渲染参数。
- Produces: 串口对象、锚定数据结构、PNG/HTML/MP4 输出与批处理结果。

- [x] **Step 1: 补充 IMU 串口函数说明**

  解释串口打开、缓冲区清理和返回对象。

- [x] **Step 2: 为离线数据、路径、绘图、筛选、原子写入和 CLI 函数补充中文 docstring**

  每个函数至少说明用途；复杂函数补充单位、抽帧策略、文件覆盖策略和失败处理。

- [x] **Step 3: 为关键作用行添加注释**

  覆盖逐帧锚定、米到毫米换算、等比例坐标轴、抽帧、临时文件替换和批处理容错。

- [x] **Step 4: 运行渲染工具测试**

  Run: `python -m pytest tests/test_render_anchored_pickles.py -q`
  Expected: PASS；注释修改不改变行为。

### Task 3: 静态与差异验证

**Files:**
- Verify: `entrance_anchor.py`
- Verify: `IMU.py`
- Verify: `tools/render_anchored_pickles.py`

**Interfaces:**
- Consumes: 修改后的 Python 源文件和 Git 工作树。
- Produces: 可编译且仅含注释/docstring 变化的差异证据。

- [x] **Step 1: 编译目标文件**

  Run: `python -m py_compile entrance_anchor.py IMU.py tools/render_anchored_pickles.py`
  Expected: exit code 0。

- [x] **Step 2: 运行目标测试合集**

  Run: `python -m pytest tests/test_entrance_anchor.py tests/test_render_anchored_pickles.py -q`
  Expected: PASS。

- [x] **Step 3: 检查 Git 差异**

  Run: `git diff --check`，随后人工确认 `git diff` 未改变可执行语句。
  Expected: 无空白错误；差异仅包含 docstring、注释和本计划文件。
