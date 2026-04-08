# PR 跟踪稳定软件设计方案（AI 自动识别 + GPU 加速）

> 目标：设计一款可用于视频中目标（人物/物体/区域）跟踪与画面稳定的桌面应用，支持自动识别与手动选区，兼顾实时预览、批处理和工程化可扩展性。

## 1. 产品定位

- **核心场景**：短视频后期、运动镜头防抖、人物主体稳定、商品展示稳定。
- **用户类型**：视频剪辑师、自媒体创作者、视觉算法工程师。
- **关键价值**：
  1. 一键 AI 跟踪稳定；
  2. 可手动修正跟踪对象；
  3. GPU 加速提升速度；
  4. 实时预览保证可控性；
  5. 多任务并行提升生产效率。

## 2. 功能需求拆解

> 术语说明：本文中的 **PR 跟踪稳定** 指“以目标部位为参考路径进行画面稳定（Path-Referenced Stabilization）”。

### 2.1 AI 全自动识别 + 跟踪

- 支持目标检测（人脸、人体、车辆、物体）并自动初始化跟踪框。
- 跟踪器支持：
  - 轻量实时：KCF / CSRT / MOSSE（CPU 兼容）；
  - 深度学习：Siamese 系列（更稳，依赖 GPU）。
- 失跟后自动重检测（re-detect）并平滑衔接轨迹。

### 2.2 稳定处理（Stabilization）

- 以目标中心作为参考路径，计算每帧平移/旋转/缩放变换。
- 轨迹平滑算法：
  - 一阶低通滤波（快速）；
  - 卡尔曼滤波（动态场景更稳）；
  - 滑动窗口 Savitzky-Golay（保细节）。
- 输出两种模式：
  - **强稳定**（画面更稳，可能裁切更多）；
  - **保视野**（稳定适中，保留更多边缘）。

### 2.3 防黑边处理

- 提供三种策略：
  1. **自适应缩放**：根据最大位移自动放大，避免黑边；
  2. **智能补边**：边缘镜像/模糊填充；
  3. **内容感知补全（高级）**：基于修补模型做背景扩展。
- UI 中提供“黑边风险预估（%）”。

### 2.4 UI 进度条 + 任务状态

- 全局任务列表：队列中 / 处理中 / 已完成 / 失败。
- 单任务进度：
  - 百分比（0~100%）；
  - 当前阶段（解码、跟踪、稳定、编码）；
  - 预估剩余时间 ETA。
- 可暂停、继续、取消任务。

### 2.5 视频实时预览

- 预览窗口支持：
  - 原视频 / 稳定后分屏对比；
  - 轨迹叠加显示；
  - 实时拖动参数（平滑强度、缩放系数）并即时反馈。
- 预览低延迟目标：1080p 下 < 120ms（GPU 模式）。

### 2.6 多任务处理

- 支持批量导入视频。
- 支持并发策略：
  - 单 GPU 多流（限制并发数，避免爆显存）；
  - CPU + GPU 混合调度。
- 任务失败自动重试并输出错误报告。

### 2.7 手动选择要跟踪稳定的部位

- 手动 ROI：框选/多边形/关键点。
- 部位级模板（示例）：头部、上半身、全身、车牌、产品主体。
- 支持关键帧修正：用户在任意帧重设目标，系统自动插值过渡。

### 2.8 PR 跟踪稳定核心功能定义

- 输入：`视频帧序列 + 目标轨迹(自动/手动)`。
- 输出：`稳定后视频 + 轨迹日志 + 黑边风险报告`。
- 核心流程：
  1. 轨迹去噪（卡尔曼/SG）；
  2. 计算“目标应停留位置”（一般为画面中心或自定义锚点）；
  3. 生成逐帧仿射变换矩阵（平移/旋转/缩放）；
  4. 应用防黑边策略；
  5. 编码输出并上报质量指标（抖动残差、裁切率、清晰度变化）。

## 3. 推荐技术架构

```text
[UI层]
  ├─ 项目管理 / 参数面板 / 预览播放器 / 任务队列
  └─ 进度状态总线（事件订阅）

[业务编排层]
  ├─ Task Scheduler（多任务调度）
  ├─ Pipeline Orchestrator（解码→检测→跟踪→稳定→编码）
  └─ Profile Manager（CPU/GPU策略）

[算法层]
  ├─ Detector（YOLO/RT-DETR）
  ├─ Tracker（CSRT/Siamese）
  ├─ Stabilizer（轨迹滤波 + 仿射变换）
  └─ Border Handler（缩放/补边/修补）

[媒体层]
  ├─ FFmpeg/NVDEC（解码）
  ├─ OpenCV/CUDA（图像处理）
  └─ NVENC/x264（编码）
```

## 4. GPU 加速设计

- **加速环节**：检测、光流、图像变换、编码。
- **推荐实现**：
  - NVIDIA：CUDA + TensorRT + NVENC/NVDEC；
  - 通用方案：ONNX Runtime + DirectML（Windows）作为 fallback。
- **显存保护机制**：
  - 动态 batch / 分辨率降级；
  - 并发任务上限（按显存自动计算）；
  - OOM 自动回退 CPU 模式。

## 5. 数据流与状态机

### 5.1 单任务数据流

1. 视频导入 -> 元信息解析（分辨率/FPS/时长）
2. AI 检测初始化目标
3. 帧级跟踪，生成原始轨迹
4. 轨迹平滑并计算稳定变换
5. 防黑边策略应用
6. 编码输出 + 质量检查

### 5.2 任务状态

- `QUEUED` → `PREPARING` → `TRACKING` → `STABILIZING` → `ENCODING` → `DONE`
- 异常分支：任意状态 → `FAILED`（附错误码、日志路径、建议修复动作）

## 6. UI 原型建议（核心页面）

- **首页**：新建任务、最近项目、设备状态（CPU/GPU 占用）。
- **编辑页**：
  - 左侧参数（目标模式、稳定强度、防黑边策略）；
  - 中央预览（原始/结果分屏）；
  - 底部时间轴（关键帧修正）。
- **队列页**：多任务列表 + 百分比 + 状态 + 操作按钮。

## 6.1 UI 状态与反馈细节（你要求的进度条与任务状态）

- 任务卡片建议字段：
  - `任务名`、`输入文件`、`输出路径`、`当前阶段`、`百分比`、`ETA`、`FPS`、`GPU显存占用`。
- 阶段颜色建议：
  - QUEUED（灰）/ TRACKING（蓝）/ STABILIZING（紫）/ ENCODING（青）/ DONE（绿）/ FAILED（红）。
- 交互建议：
  - 支持“暂停/继续/取消/重试”；
  - 失败时提供“查看日志”和“一键重跑（降级参数）”。
- 预览区域建议：
  - 左右分屏：左原始、右稳定；
  - 叠加目标框、轨迹曲线、黑边风险热区；
  - 参数滑条实时生效，确保“所见即所得”。

## 6.2 手动部位选择设计（你要求的可手选稳定部位）

- 选择模式：
  - 矩形框（最快）；
  - 多边形（复杂目标）；
  - 关键点（头部、肩部、车牌角点等）。
- 关键帧机制：
  - 用户在时间轴打关键帧修正目标；
  - 非关键帧采用插值+局部重跟踪；
  - 明显漂移时自动弹出“需要修正”的提示标记。

## 7. 性能目标（建议）

- 1080p / 30fps / 3分钟视频：
  - GPU 中档显卡：处理时间 ≤ 1.2x 实时；
  - CPU 模式：处理时间 ≤ 4x 实时。
- 跟踪稳定成功率（主体无遮挡场景）≥ 95%。

## 8. MVP 里程碑（建议 3 期）

### 里程碑 1（MVP）
- 单目标自动跟踪 + 基础稳定 + 进度条 + 导出。

### 里程碑 2
- 手动 ROI、实时预览、黑边自适应缩放、多任务队列。

### 里程碑 3
- 多目标跟踪、内容感知补边、GPU 调度优化、质量评估报告。

## 9. 风险与规避

- **复杂运动失跟**：引入重检测 + 关键帧人工修正。
- **黑边严重**：增加智能补边与最小可接受裁切阈值。
- **显存不足**：自动降级推理分辨率并限制并发。
- **跨平台兼容**：抽象硬件加速接口，保留 CPU 后备通道。

## 10. 可直接落地的开发清单

1. 建立 `pipeline` 模块（阶段化状态上报）。
2. 建立 `task_queue`（并发、暂停、取消、重试）。
3. 接入 OpenCV + FFmpeg（先 CPU 跑通）。
4. 引入 GPU 推理（ONNX/TensorRT 二选一）。
5. 实现实时预览与参数热更新。
6. 增加可视化日志与导出报告。

## 11. 模块接口草案（便于工程开工）

```python
class TrackingRequest:
    input_path: str
    output_path: str
    target_mode: str          # auto | manual
    roi_points: list          # optional
    stabilize_strength: float # 0~1
    border_strategy: str      # scale | mirror | inpaint
    use_gpu: bool

class TaskProgress:
    task_id: str
    stage: str                # QUEUED/PREPARING/TRACKING/...
    percent: float            # 0~100
    eta_sec: int
    fps: float
    status_text: str

class StabilizerEngine:
    def submit(req: TrackingRequest) -> str: ...
    def pause(task_id: str) -> None: ...
    def resume(task_id: str) -> None: ...
    def cancel(task_id: str) -> None: ...
    def preview_frame(task_id: str, frame_idx: int): ...
```

> 以上接口可先用 Python 实现 MVP，后续将计算密集模块迁移到 C++/CUDA。

## 12. 直接可执行的技术选型（定版建议）

### 12.1 技术栈（建议你直接按此落地）

- **桌面端 UI**：PySide6（比 Tkinter 更适合复杂播放器 + 多任务队列 UI）。
- **算法引擎**：Python + OpenCV + PyTorch/ONNX Runtime。
- **视频编解码**：FFmpeg（命令行 + 管道）+ NVENC/NVDEC（NVIDIA）。
- **任务调度**：`asyncio + multiprocessing`（UI 与计算进程隔离）。
- **数据存储**：SQLite（项目配置、任务元数据、运行日志索引）。
- **日志与监控**：结构化日志（JSON），关键指标写入 `metrics.jsonl`。

### 12.2 运行模式（必须支持）

- `AUTO`：AI 自动识别 + 自动跟踪 + 自动稳定。
- `AUTO+MANUAL`：AI 初始化后，用户手动修正关键帧。
- `MANUAL`：完全手动选部位后稳定（用于 AI 识别失败场景）。

## 13. 目录结构（建议直接创建）

```text
stabilizer/
  app/
    main.py
    ui/
      pages/
      widgets/
  core/
    pipeline/
      orchestrator.py
      stages.py
    tracking/
      detector.py
      tracker.py
    stabilize/
      transform_solver.py
      trajectory_filter.py
      border_handler.py
    preview/
      preview_engine.py
  infra/
    ffmpeg/
      decoder.py
      encoder.py
    scheduler/
      task_queue.py
      worker.py
    storage/
      project_repo.py
      task_repo.py
  tests/
```

## 14. 关键 API 细化（前后端/模块联调用）

### 14.1 创建任务

```json
POST /tasks
{
  "input_path": "xxx.mp4",
  "output_path": "yyy.mp4",
  "mode": "AUTO+MANUAL",
  "roi": [{"x":100,"y":120}, {"x":260,"y":120}, {"x":260,"y":300}, {"x":100,"y":300}],
  "stabilize_strength": 0.72,
  "border_strategy": "scale",
  "use_gpu": true
}
```

### 14.2 任务状态（用于 UI 进度条和状态标签）

```json
GET /tasks/{task_id}
{
  "task_id": "t_001",
  "stage": "TRACKING",
  "percent": 46.3,
  "eta_sec": 51,
  "fps": 87.4,
  "retry_count": 0,
  "black_border_risk": 0.08
}
```

### 14.3 关键帧修正（手动选部位核心能力）

```json
POST /tasks/{task_id}/keyframes
{
  "frame_index": 245,
  "roi": [{"x":130,"y":110}, {"x":280,"y":110}, {"x":280,"y":320}, {"x":130,"y":320}]
}
```

## 15. 多任务与 GPU 调度策略（可直接开发）

- GPU Worker 池建议：
  - 6GB 显存：并发 1；
  - 8~12GB 显存：并发 2；
  - >12GB 显存：并发 3（1080p 默认）。
- 调度规则：
  1. `ENCODING` 阶段优先复用 NVENC；
  2. 显存不足触发“降级队列”（降分辨率推理或切 CPU）；
  3. 单任务连续失败 2 次后标记 `FAILED_NEEDS_MANUAL`。
- 任务重试：
  - 第一次失败：降低模型输入尺寸（如 1280->960）；
  - 第二次失败：切换追踪器（Siamese -> CSRT）；
  - 第三次失败：暂停并提示用户添加手动关键帧。

## 16. 验收标准（你可以直接给团队执行）

- **功能验收**：
  - 支持自动识别、手动部位选择、实时预览、任务进度百分比和状态机显示；
  - 支持黑边处理三策略；
  - 支持批量任务和暂停/继续/取消/重试。
- **性能验收**：
  - 1080p/30fps，3 分钟视频，GPU 模式总处理时长 ≤ 1.2x 实时；
  - 预览延迟 ≤ 120ms；
  - 常规场景跟踪稳定成功率 ≥ 95%。
- **稳定性验收**：
  - 连续跑 50 条视频任务，失败率 ≤ 5%；
  - OOM 时无崩溃，能够自动降级并记录日志。

## 17. 4 周排期（可直接执行）

- **第 1 周**：
  - 完成任务队列、状态机、FFmpeg 解码/编码打通；
  - UI 完成任务列表 + 进度条 + 状态标签。
- **第 2 周**：
  - 完成自动检测 + 跟踪 + 基础稳定（CPU 跑通）；
  - 加入手动 ROI 与关键帧修正。
- **第 3 周**：
  - 接入 GPU 推理与 NVENC；
  - 完成实时预览与参数热更新。
- **第 4 周**：
  - 完成防黑边策略、失败重试策略、质量报告；
  - 回归测试 + 性能压测 + 交付文档。

---

这版就是“可直接执行”的版本，你可以按第 13~17 节直接拆任务开工。
