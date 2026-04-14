#!/bin/bash
# VideoFrame 跨平台打包脚本
# 支持 macOS, Windows, Linux

set -e

echo "========================================"
echo "VideoFrame 跨平台打包工具"
echo "========================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

# 检测操作系统
OS=$(uname -s)
echo ""
echo "[1/3] 检测到操作系统: $OS"

# 安装依赖（使用 --break-system-packages 适配 Homebrew Python）
echo ""
echo "[2/3] 安装依赖..."
pip3 install --break-system-packages -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null || pip install -r requirements.txt

# 安装PyInstaller
echo ""
echo "[3/3] 安装 PyInstaller..."
pip3 install --break-system-packages pyinstaller 2>/dev/null || pip3 install pyinstaller 2>/dev/null || pip install pyinstaller

# 清理旧的构建文件
echo ""
echo "清理旧的构建文件..."
rm -rf build dist *.spec

# 打包
echo ""
echo "正在打包..."

pyinstaller --noconfirm --onefile --windowed \
    --name VideoFrame \
    --hidden-import PyQt5 \
    --hidden-import PyQt5.QtCore \
    --hidden-import PyQt5.QtGui \
    --hidden-import PyQt5.QtWidgets \
    --hidden-import PyQt5.sip \
    --hidden-import sqlite3 \
    --exclude-module tkinter \
    --exclude-module matplotlib \
    --exclude-module numpy \
    run_gui.py

echo ""
echo "========================================"
echo "打包完成！"
echo "========================================"
echo ""
echo "输出文件: dist/VideoFrame"
echo ""
echo "创建 macOS 应用包..."

# 创建 .app 包结构
mkdir -p "dist/VideoFrame.app/Contents/MacOS"
mkdir -p "dist/VideoFrame.app/Contents/Resources"
mv dist/VideoFrame dist/VideoFrame.app/Contents/MacOS/VideoFrame

# 创建 Info.plist
cat > "dist/VideoFrame.app/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>VideoFrame</string>
    <key>CFBundleIdentifier</key>
    <string>com.videoframe.app</string>
    <key>CFBundleName</key>
    <string>VideoFrame</string>
    <key>CFBundleDisplayName</key>
    <string>VideoFrame</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

echo ""
echo "========================================"
echo "打包成功！"
echo "========================================"
echo ""
echo "输出文件: dist/VideoFrame.app"
echo ""
echo "重要提示: 此程序需要 FFmpeg 支持"
echo "安装命令: brew install ffmpeg"
echo ""
