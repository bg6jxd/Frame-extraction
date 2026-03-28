"""
核心模块
"""
from videoframe.core.index import VideoIndexManager
from videoframe.core.extraction import ExtractionEngine, FrameExtractor
from videoframe.core.composition import VideoComposer

__all__ = ['VideoIndexManager', 'ExtractionEngine', 'FrameExtractor', 'VideoComposer']
