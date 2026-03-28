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

# 安装依赖
echo ""
echo "[1/4] 安装依赖..."
pip3 install -r requirements.txt

# 安装PyInstaller
echo ""
echo "[2/4] 安装 PyInstaller..."
pip3 install pyinstaller

# 检测操作系统
OS=$(uname -s)
echo ""
echo "[3/4] 检测到操作系统: $OS"

# 清理旧的构建文件
echo ""
echo "[4/4] 清理旧的构建文件..."
rm -rf build dist *.spec

# 打包
echo ""
echo "正在打包..."

case "$OS" in
    Darwin)
        echo "为 macOS 打包..."
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
        
        echo "输出文件: dist/VideoFrame.app"
        ;;
    Linux)
        echo "为 Linux 打包..."
        pyinstaller --noconfirm --onefile \
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
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "为 Windows 打包..."
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
            --icon=icon.ico \
            run_gui.py
        
        echo ""
        echo "========================================"
        echo "打包完成！"
        echo "========================================"
        echo ""
        echo "输出文件: dist\VideoFrame.exe"
        ;;
    *)
        echo "未知操作系统: $OS"
        echo "尝试通用打包..."
        pyinstaller --noconfirm --onefile --windowed \
            --name VideoFrame \
            --hidden-import PyQt5 \
            --hidden-import PyQt5.QtCore \
            --hidden-import PyQt5.QtGui \
            --hidden-import PyQt5.QtWidgets \
            --hidden-import sqlite3 \
            run_gui.py
        ;;
esac

echo ""
echo "========================================"
echo "重要提示"
echo "========================================"
echo ""
echo "此程序需要 FFmpeg 支持，请确保目标系统已安装 FFmpeg："
echo ""
echo "  macOS:   brew install ffmpeg"
echo "  Ubuntu:  sudo apt install ffmpeg"
echo "  Windows: 从 https://ffmpeg.org 下载"
echo ""
