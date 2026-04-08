# PR 跟踪稳定软件（AI 自动识别 + GPU 加速）

这是一个基于 Python + Tkinter + OpenCV 的桌面版视频稳定工具，支持：
- AI 自动识别目标并跟踪稳定；
- 手动框选要跟踪的部位；
- 防黑边处理；
- 任务进度百分比 + 状态显示；
- 实时预览（原始 vs 稳定后）；
- 多任务并发处理；
- GPU 可用性检测与自动回退。

## 快速开始

### 1) 安装依赖
```bash
python3 -m pip install -r requirements.txt
```

### 2) 启动软件
```bash
python3 app.py
```

## 使用说明

1. 点击 **选择视频（可多选）** 导入任务。
2. 如需手动跟踪部位，点击 **手动选跟踪部位**，在弹窗中框选并确认。
3. 选择输出目录与参数（AI识别/GPU/防黑边/实时预览/平滑强度/并发数）。
4. 点击 **开始批处理**。
5. 在任务列表查看每个视频的进度百分比和状态。

## 文件结构

- `app.py`：主界面与多任务调度。
- `stabilizer.py`：跟踪稳定核心逻辑（自动识别、轨迹平滑、防黑边、实时预览）。
- `requirements.txt`：依赖。
- `build_windows.ps1`：Windows 打包脚本。
- `build_macos.sh`：macOS 打包脚本。

## 说明

- 当前默认编码器为 `mp4v`，如需更高压缩效率可替换为 ffmpeg 管线。
- GPU 加速会先检测环境可用性，不可用时自动回退 CPU。


## Windows 一键打包 .exe

在 Windows 上执行：

- 双击 `build_windows.bat`（推荐）
- 或 PowerShell 执行 `./build_windows.ps1`

产物：`dist/PRStabilizer.exe`
