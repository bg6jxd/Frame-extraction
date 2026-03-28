# VideoFrame - Surveillance Video Frame Extraction Tool

[中文文档](#中文文档) | [English Documentation](#english-documentation)

---

# English Documentation

🎬 **VideoFrame** is a professional surveillance video frame extraction management tool designed to extract frames from massive surveillance video archives based on time rules and compose them into timelapse videos.

## Features

- 📁 **Video Index Management** - Scan and index video files, parse filenames to extract time information
- ⏱️ **Time-based Frame Extraction** - Extract frames by date range, daily time period, and interval
- 🚀 **Multi-threaded Parallel Processing** - Support for multi-threaded parallel extraction, significantly improving processing speed
- 🎬 **Video Composition** - Compose extracted frames into timelapse videos
- 🖥️ **Graphical Interface** - Modern GUI based on PyQt5
- 💻 **CLI Support** - Complete command-line interface

## Supported Video File Formats

Automatically parses the following camera filename formats:

| Brand | Filename Format Example |
|-------|-------------------------|
| Xiaomi | `00_20260327121712_20260327122218.mp4` |
| Hikvision | `ch01_20260327121712.mp4` |
| Dahua | `DH20260327121712.mp4` |

## System Requirements

- Python 3.10+
- FFmpeg (for video processing)

### Installing FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org and add to PATH
```

## Installation

### Install from Source

```bash
# Clone repository
git clone https://github.com/bg6jxd/Frame-extraction.git
cd "Frame extraction"

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Graphical Interface (Recommended)

```bash
python run_gui.py
```

### Command Line Interface

```bash
# Initialize index
videoframe init

# Scan video files
videoframe scan /path/to/videos

# Extract frames
videoframe extract --start-date 2026-03-19 --end-date 2026-03-27 --interval 120

# Compose video
videoframe compose /path/to/frames -o output.mp4
```

## GUI Interface Guide

### Video Index
- Select video directory
- Scan and index video files
- Quick scan mode (parse filenames only, no video content reading)

### Frame Extraction Settings
- Set date range (automatically constrained by video time range)
- Set daily time period
- Set extraction interval
- Set output format and quality

### Video Composition
- Select frame directory
- Set frame rate, resolution
- Select video encoder (H.264/H.265/VP9/AV1)

### Operation Log
- View operation logs

## Project Structure

```
videoframe/
├── cli/                 # Command line interface
│   └── main.py
├── core/                # Core modules
│   ├── composition/     # Video composition
│   ├── extraction/      # Frame extraction
│   ├── index/           # Index management
│   └── metadata/        # Metadata extraction
├── models/              # Data models
├── utils/               # Utility functions
└── gui_pyqt.py          # PyQt5 GUI
```

## Build Standalone Application

### macOS / Linux

```bash
chmod +x build.sh
./build.sh
```

Output:
- macOS: `dist/VideoFrame.app`
- Linux: `dist/VideoFrame`

### Windows

```cmd
build.bat
```

Output: `dist\VideoFrame.exe`

## Configuration

Configuration file located at `videoframe/config/default.yaml`, customize default parameters.

## License

MIT License

---

# 中文文档

🎬 **VideoFrame** 是一个专业的监控视频抽帧管理工具，用于从海量监控视频中按照时间规则提取帧图像，并合成为延时视频。

## 功能特性

- 📁 **视频索引管理** - 扫描并索引视频文件，解析文件名获取时间信息
- ⏱️ **时间规则抽帧** - 按日期范围、每日时间段、抽帧间隔提取帧图像
- 🚀 **多线程并行处理** - 支持多线程并行抽帧，大幅提升处理速度
- 🎬 **视频合成** - 将提取的帧图像合成为延时视频
- 🖥️ **图形化界面** - 基于 PyQt5 的现代化 GUI 界面
- 💻 **命令行支持** - 完整的 CLI 命令行工具

## 支持的视频文件格式

自动解析以下摄像机文件名格式：

| 品牌 | 文件名格式示例 |
|------|----------------|
| 小米 | `00_20260327121712_20260327122218.mp4` |
| 海康威视 | `ch01_20260327121712.mp4` |
| 大华 | `DH20260327121712.mp4` |

## 系统要求

- Python 3.10+
- FFmpeg（用于视频处理）

### 安装 FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 从 https://ffmpeg.org 下载并添加到 PATH
```

## 安装

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/bg6jxd/Frame-extraction.git
cd "Frame extraction"

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 图形化界面（推荐）

```bash
python run_gui.py
```

### 命令行界面

```bash
# 初始化索引
videoframe init

# 扫描视频文件
videoframe scan /path/to/videos

# 提取帧图像
videoframe extract --start-date 2026-03-19 --end-date 2026-03-27 --interval 120

# 合成视频
videoframe compose /path/to/frames -o output.mp4
```

## GUI 界面说明

### 视频索引
- 选择视频文件目录
- 扫描并索引视频文件
- 快速扫描模式（仅解析文件名，不读取视频内容）

### 抽帧设置
- 设置日期范围（自动根据视频时间范围约束）
- 设置每日时间段
- 设置抽帧间隔
- 设置输出格式和质量

### 视频合成
- 选择帧图像目录
- 设置帧率、分辨率
- 选择视频编码器（H.264/H.265/VP9/AV1）

### 运行日志
- 查看操作日志

## 项目结构

```
videoframe/
├── cli/                 # 命令行界面
│   └── main.py
├── core/                # 核心功能模块
│   ├── composition/     # 视频合成
│   ├── extraction/      # 帧提取
│   ├── index/           # 索引管理
│   └── metadata/        # 元数据提取
├── models/              # 数据模型
├── utils/               # 工具函数
└── gui_pyqt.py          # PyQt5 GUI
```

## 打包为独立程序

### macOS / Linux

```bash
chmod +x build.sh
./build.sh
```

输出文件：
- macOS: `dist/VideoFrame.app`
- Linux: `dist/VideoFrame`

### Windows

```cmd
build.bat
```

输出文件：`dist\VideoFrame.exe`

## 配置文件

配置文件位于 `videoframe/config/default.yaml`，可自定义默认参数。

## 许可证

MIT License
