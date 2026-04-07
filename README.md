# TikTok 无水印视频下载器（Windows / macOS）

这是一个跨平台桌面工具（Python + Tkinter），用于下载 TikTok 视频并尽量获取无水印版本。

## 功能
- 输入 TikTok 视频链接（支持短链自动跳转）。
- 自动解析视频信息并尝试生成无水印下载地址。
- 选择保存目录并下载为 `.mp4`。
- 图形化界面，适配 Windows / macOS。

## 免责声明
请仅下载你有权使用的内容，并遵守 TikTok 平台条款与当地法律法规。

## 快速开始

### 1) 安装依赖
```bash
python3 -m pip install -r requirements.txt
```

### 2) 运行
```bash
python3 app.py
```

## 打包

### Windows
在 PowerShell 中运行：
```powershell
./build_windows.ps1
```
产物：`dist/TikTokDownloader.exe`

### macOS
在终端中运行：
```bash
chmod +x build_macos.sh
./build_macos.sh
```
产物：`dist/TikTokDownloader.app`

## 项目结构
- `app.py`：GUI 入口
- `tiktok_downloader.py`：TikTok 链接解析与下载核心逻辑
- `requirements.txt`：Python 依赖
- `build_windows.ps1`：Windows 打包脚本
- `build_macos.sh`：macOS 打包脚本


## 扩展方案
- `STABILIZER_DESIGN.md`：PR 跟踪稳定软件（AI自动识别、GPU加速、实时预览、多任务）设计文档。
