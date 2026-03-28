"""
数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from pathlib import Path


class IndexStatus(str, Enum):
    """索引状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SamplingMethod(str, Enum):
    """采样方法"""
    INTERVAL = "interval"
    SPECIFIC_TIMES = "specific_times"
    MOTION_BASED = "motion_based"


class FrameOrdering(str, Enum):
    """帧排序方式"""
    CHRONOLOGICAL = "chronological"
    REVERSE = "reverse"
    RANDOM = "random"


@dataclass
class VideoFile:
    """视频文件信息"""
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    fps: float = 0.0
    resolution_width: int = 0
    resolution_height: int = 0
    codec: str = ""
    bitrate: int = 0
    camera_id: str = ""
    index_status: IndexStatus = IndexStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if self.file_name == "" and self.file_path:
            self.file_name = Path(self.file_path).name
    
    @property
    def resolution(self) -> Tuple[int, int]:
        """获取分辨率"""
        return (self.resolution_width, self.resolution_height)
    
    @property
    def duration(self) -> timedelta:
        """获取时长"""
        return timedelta(seconds=self.duration_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'fps': self.fps,
            'resolution_width': self.resolution_width,
            'resolution_height': self.resolution_height,
            'codec': self.codec,
            'bitrate': self.bitrate,
            'camera_id': self.camera_id,
            'index_status': self.index_status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class TimeSelection:
    """时间选择配置"""
    type: str = "daily_range"  # daily_range, full_day
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    timezone: str = "Asia/Shanghai"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'start_time': self.start_time.strftime("%H:%M:%S") if self.start_time else None,
            'end_time': self.end_time.strftime("%H:%M:%S") if self.end_time else None,
            'timezone': self.timezone,
        }


@dataclass
class DateRange:
    """日期范围"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    exclude_dates: List[date] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'exclude_dates': [d.isoformat() for d in self.exclude_dates],
        }


@dataclass
class Sampling:
    """采样配置"""
    method: SamplingMethod = SamplingMethod.INTERVAL
    interval: timedelta = timedelta(minutes=1)
    specific_times: List[time] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'method': self.method.value,
            'interval_seconds': self.interval.total_seconds(),
            'specific_times': [t.strftime("%H:%M:%S") for t in self.specific_times],
        }


@dataclass
class OutputConfig:
    """输出配置"""
    format: str = "jpg"
    quality: int = 95
    resolution: str = "original"
    naming: str = "{date}_{time}_{camera_id}_{frame_number}"
    output_dir: str = "./output"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'format': self.format,
            'quality': self.quality,
            'resolution': self.resolution,
            'naming': self.naming,
            'output_dir': self.output_dir,
        }


@dataclass
class ExtractionRule:
    """抽帧规则"""
    name: str = ""
    description: str = ""
    time_selection: Optional[TimeSelection] = None
    date_range: Optional[DateRange] = None
    sampling: Optional[Sampling] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    output: Optional[OutputConfig] = None
    
    def __post_init__(self):
        if self.time_selection is None:
            self.time_selection = TimeSelection()
        if self.date_range is None:
            self.date_range = DateRange()
        if self.sampling is None:
            self.sampling = Sampling()
        if self.output is None:
            self.output = OutputConfig()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'time_selection': self.time_selection.to_dict() if self.time_selection else None,
            'date_range': self.date_range.to_dict() if self.date_range else None,
            'sampling': self.sampling.to_dict() if self.sampling else None,
            'filters': self.filters,
            'output': self.output.to_dict() if self.output else None,
        }


@dataclass
class ExtractionPoint:
    """提取点"""
    timestamp: datetime
    method: str = "interval"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'method': self.method,
        }


@dataclass
class FrameLocation:
    """帧位置信息"""
    video_file: VideoFile
    frame_number: int
    timestamp: datetime
    time_offset: float  # 在视频中的偏移秒数
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'video_file': self.video_file.file_path,
            'frame_number': self.frame_number,
            'timestamp': self.timestamp.isoformat(),
            'time_offset': self.time_offset,
        }


@dataclass
class ExtractedFrame:
    """已提取的帧"""
    file_path: str
    timestamp: datetime
    frame_number: int
    camera_id: str = ""
    resolution: Tuple[int, int] = (0, 0)
    size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': self.file_path,
            'timestamp': self.timestamp.isoformat(),
            'frame_number': self.frame_number,
            'camera_id': self.camera_id,
            'resolution': self.resolution,
            'size': self.size,
        }


@dataclass
class ExtractionPlan:
    """抽帧计划"""
    video_mappings: List[Tuple[ExtractionPoint, List[VideoFile]]]
    rule: ExtractionRule
    frame_locations: List[FrameLocation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_points': len(self.video_mappings),
            'total_frames': len(self.frame_locations),
            'rule': self.rule.to_dict(),
        }


@dataclass
class ExtractionTask:
    """抽帧任务"""
    id: str
    plan: ExtractionPlan
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ExtractionResult:
    """抽帧结果"""
    task_id: str
    frames: List[ExtractedFrame]
    total_extracted: int = 0
    errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.total_extracted == 0:
            self.total_extracted = len(self.frames)


@dataclass
class ProgressInfo:
    """进度信息"""
    task_id: str
    status: TaskStatus
    progress: float
    extracted_frames: int
    total_frames: int
    errors: List[str]
    start_time: Optional[datetime] = None
    elapsed_time: Optional[timedelta] = None
    
    def __post_init__(self):
        if self.start_time and not self.elapsed_time:
            self.elapsed_time = datetime.now() - self.start_time


@dataclass
class CompositionConfig:
    """视频合成配置"""
    fps: int = 30
    resolution: Tuple[int, int] = (1920, 1080)
    codec: str = "h264"
    preset: str = "medium"
    crf: int = 23
    output_path: str = "output.mp4"
    add_timestamp: bool = False
    watermark: Optional[str] = None
    transition: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'fps': self.fps,
            'resolution': self.resolution,
            'codec': self.codec,
            'preset': self.preset,
            'crf': self.crf,
            'output_path': self.output_path,
            'add_timestamp': self.add_timestamp,
            'watermark': self.watermark,
            'transition': self.transition,
        }


@dataclass
class CompositionResult:
    """合成结果"""
    output_path: str
    total_frames: int
    duration: float
    file_size: int
    fps: int
    resolution: Tuple[int, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'output_path': self.output_path,
            'total_frames': self.total_frames,
            'duration': self.duration,
            'file_size': self.file_size,
            'fps': self.fps,
            'resolution': self.resolution,
        }


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str):
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
