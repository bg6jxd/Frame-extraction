#!/usr/bin/env python3
"""
VideoFrame - 监控视频抽帧管理工具
用于从海量监控视频中按规则提取帧并合成延时摄影视频
"""

__version__ = "1.0.0"
__author__ = "VideoFrame Team"

try:
    from videoframe.cli.main import cli
    __all__ = ["cli"]
except ImportError:
    __all__ = []
