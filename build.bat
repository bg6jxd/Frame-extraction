@echo off
chcp 65001 >nul
REM VideoFrame Windows打包脚本

echo ========================================
echo VideoFrame 跨平台打包工具 (Windows)
echo ========================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    exit /b 1
)

REM 安装依赖
echo.
echo [1/4] 安装依赖...
pip install -r requirements.txt

REM 安装PyInstaller
echo.
echo [2/4] 安装 PyInstaller...
pip install pyinstaller

REM 清理旧的构建文件
echo.
echo [3/4] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

REM 打包
echo.
echo [4/4] 正在为 Windows 打包...
pyinstaller --noconfirm --onefile --windowed ^
    --name VideoFrame ^
    --hidden-import PyQt5 ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import PyQt5.sip ^
    --hidden-import sqlite3 ^
    --exclude-module tkinter ^
    --exclude-module matplotlib ^
    --exclude-module numpy ^
    run_gui.py

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo.
echo 输出文件: dist\VideoFrame.exe
echo.
echo ========================================
echo 重要提示
echo ========================================
echo.
echo 此程序需要 FFmpeg 支持，请从以下地址下载：
echo https://ffmpeg.org/download.html
echo.
echo 将 ffmpeg.exe 放置在与 VideoFrame.exe 相同的目录，
echo 或添加到系统 PATH 环境变量中。
echo.
pause
