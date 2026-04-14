"""
视频索引管理器
"""
import logging
from typing import List, Optional, Callable
from datetime import datetime
from pathlib import Path

from videoframe.models import VideoFile, IndexStatus
from videoframe.utils import ensure_dir
from .database import Database
from .scanner import VideoScanner, ScanResult


logger = logging.getLogger(__name__)


class IndexResult:
    """索引结果"""
    
    def __init__(self):
        self.total_videos = 0
        self.indexed = 0
        self.updated = 0
        self.failed = 0
        self.errors = []
    
    def to_dict(self):
        return {
            'total_videos': self.total_videos,
            'indexed': self.indexed,
            'updated': self.updated,
            'failed': self.failed,
            'errors': self.errors[:10],
        }


class CoverageReport:
    """视频覆盖报告"""
    
    def __init__(self, start_time: datetime, end_time: datetime):
        self.start_time = start_time
        self.end_time = end_time
        self.total_duration = (end_time - start_time).total_seconds()
        self.covered_duration = 0.0
        self.gaps = []
        self.videos = []
    
    @property
    def coverage_ratio(self) -> float:
        """覆盖率"""
        return self.covered_duration / self.total_duration if self.total_duration > 0 else 0.0
    
    def to_dict(self):
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_duration': self.total_duration,
            'covered_duration': self.covered_duration,
            'coverage_ratio': self.coverage_ratio,
            'gaps': len(self.gaps),
        }


class VideoIndexManager:
    """视频索引管理器"""
    
    # 批量插入的批次大小
    BATCH_SIZE = 100
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / '.videoframe' / 'index.db')
        
        self.db = Database(db_path)
        self.scanner = VideoScanner()
    
    def scan_and_index(
        self,
        directory: str,
        recursive: bool = True,
        pattern: Optional[str] = None,
        force_rebuild: bool = False,
        progress_callback: Optional[Callable] = None,
        quick_mode: bool = True
    ) -> IndexResult:
        """扫描并索引视频目录
        
        Args:
            directory: 视频目录路径
            recursive: 是否递归扫描子目录
            pattern: 文件名匹配模式
            force_rebuild: 是否强制重建索引
            progress_callback: 进度回调函数
            quick_mode: 快速模式，仅解析文件名，不读取文件内容
        """
        
        result = IndexResult()
        
        if force_rebuild:
            logger.info("Force rebuild index, clearing existing data...")
            self.db.clear_all()
        
        # 使用扫描器的批量扫描方法
        scan_result = self.scanner.scan_directory_batch(
            directory,
            recursive=recursive,
            pattern=pattern,
            progress_callback=progress_callback,
            quick_mode=quick_mode
        )
        
        result.total_videos = scan_result.video_files
        result.failed = scan_result.failed
        result.errors = scan_result.errors
        
        # 收集所有扫描到的视频并批量插入
        videos = list(self.scanner.scan_directory(
            directory,
            recursive=recursive,
            pattern=pattern,
            quick_mode=quick_mode
        ))
        
        # 批量插入
        for i in range(0, len(videos), self.BATCH_SIZE):
            batch = videos[i:i + self.BATCH_SIZE]
            success, failed = self.db.insert_videos_batch(batch)
            result.indexed += success
            result.failed += failed
        
        logger.info(f"Index completed: {result.indexed}/{result.total_videos} videos indexed")
        
        return result
    
    def build_index(self, videos: List[VideoFile]) -> IndexResult:
        """构建索引"""
        
        result = IndexResult()
        result.total_videos = len(videos)
        
        # 批量插入
        for i in range(0, len(videos), self.BATCH_SIZE):
            batch = videos[i:i + self.BATCH_SIZE]
            success, failed = self.db.insert_videos_batch(batch)
            result.indexed += success
            result.failed += failed
        
        return result
    
    def query_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        camera_id: Optional[str] = None
    ) -> List[VideoFile]:
        """按时间范围查询视频"""
        return self.db.query_by_time_range(start_time, end_time, camera_id)
    
    def get_video_coverage(
        self,
        start_time: datetime,
        end_time: datetime,
        camera_id: Optional[str] = None
    ) -> CoverageReport:
        """获取视频覆盖情况"""
        
        videos = self.query_by_time_range(start_time, end_time, camera_id)
        
        report = CoverageReport(start_time, end_time)
        report.videos = videos
        
        if not videos:
            report.gaps = [(start_time, end_time)]
            return report
        
        valid_videos = [v for v in videos if v.start_time and v.end_time]
        if not valid_videos:
            report.gaps = [(start_time, end_time)]
            return report
        
        valid_videos.sort(key=lambda v: v.start_time if v.start_time else start_time)
        
        current_time = start_time
        
        for video in valid_videos:
            vid_start = video.start_time if video.start_time else start_time
            vid_end = video.end_time if video.end_time else end_time
            
            if vid_start > current_time:
                report.gaps.append((current_time, vid_start))
            
            if vid_end > current_time:
                covered = (min(vid_end, end_time) - max(vid_start, current_time)).total_seconds()
                report.covered_duration += covered
                current_time = vid_end
        
        if current_time < end_time:
            report.gaps.append((current_time, end_time))
        
        return report
    
    def get_all_videos(self) -> List[VideoFile]:
        """获取所有视频"""
        return self.db.get_all_videos()
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return self.db.get_statistics()
    
    def remove_video(self, file_path: str):
        """移除视频"""
        self.db.delete_video(file_path)
    
    def get_video_by_path(self, file_path: str) -> Optional[VideoFile]:
        """根据路径获取视频"""
        return self.db.get_video_by_path(file_path)
    
    def close(self):
        """关闭数据库连接"""
        self.db.close()
