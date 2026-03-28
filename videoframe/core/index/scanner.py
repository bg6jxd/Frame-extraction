"""
视频文件扫描器
"""
import os
import logging
from pathlib import Path
from typing import List, Generator, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from videoframe.models import VideoFile
from videoframe.utils import is_video_file
from videoframe.core.metadata import MetadataExtractor


logger = logging.getLogger(__name__)


class ScanResult:
    """扫描结果"""
    
    def __init__(self):
        self.total_files = 0
        self.video_files = 0
        self.successful = 0
        self.failed = 0
        self.errors = []
    
    def add_success(self):
        self.successful += 1
    
    def add_failure(self, error: str):
        self.failed += 1
        self.errors.append(error)
    
    def to_dict(self):
        return {
            'total_files': self.total_files,
            'video_files': self.video_files,
            'successful': self.successful,
            'failed': self.failed,
            'errors': self.errors[:10],
        }


class VideoScanner:
    """视频文件扫描器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.metadata_extractor = MetadataExtractor()
    
    def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
        pattern: Optional[str] = None,
        quick_mode: bool = True
    ) -> Generator[VideoFile, None, None]:
        """扫描目录中的视频文件
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描
            pattern: 文件名匹配模式
            quick_mode: 快速模式，仅解析文件名，不读取文件内容
        """
        
        dir_path = Path(directory).resolve()
        
        if recursive:
            file_paths = dir_path.rglob('*')
        else:
            file_paths = dir_path.glob('*')
        
        for file_path in file_paths:
            if file_path.is_file() and is_video_file(str(file_path)):
                if pattern and pattern not in file_path.name:
                    continue
                
                try:
                    # 使用绝对路径
                    abs_path = str(file_path.resolve())
                    if quick_mode:
                        video = self.metadata_extractor.quick_extract(abs_path)
                    else:
                        video = self.metadata_extractor.extract(abs_path)
                    yield video
                except Exception as e:
                    logger.error(f"Failed to extract metadata from {file_path}: {e}")
    
    def scan_directory_batch(
        self,
        directory: str,
        recursive: bool = True,
        pattern: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        quick_mode: bool = True
    ) -> ScanResult:
        """批量扫描目录
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描
            pattern: 文件名匹配模式
            progress_callback: 进度回调函数
            quick_mode: 快速模式，仅解析文件名，不读取视频内容
        """
        
        result = ScanResult()
        dir_path = Path(directory).resolve()
        
        all_files = []
        
        if recursive:
            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    result.total_files += 1
                    if is_video_file(str(file_path)):
                        if pattern and pattern not in file_path.name:
                            continue
                        all_files.append(file_path.resolve())
                        result.video_files += 1
        else:
            for file_path in dir_path.glob('*'):
                if file_path.is_file():
                    result.total_files += 1
                    if is_video_file(str(file_path)):
                        if pattern and pattern not in file_path.name:
                            continue
                        all_files.append(file_path.resolve())
                        result.video_files += 1
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self.metadata_extractor.quick_extract if quick_mode else self.metadata_extractor.extract,
                    str(fp)
                ): fp
                for fp in all_files
            }
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    video = future.result()
                    result.add_success()
                    
                    if progress_callback:
                        progress_callback(video, result)
                except Exception as e:
                    result.add_failure(f"{file_path}: {str(e)}")
        
        return result
