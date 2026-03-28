#!/usr/bin/env python3
"""
VideoFrame GUI 启动脚本
启动图形化界面
"""
import sys
from pathlib import Path

# 添加项目路径到系统路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from videoframe.gui_pyqt import main

if __name__ == "__main__":
    main()
