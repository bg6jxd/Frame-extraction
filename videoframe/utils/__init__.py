"""
工具函数和辅助类
"""
import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from functools import lru_cache


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """设置日志"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers: list = [logging.StreamHandler()]
    
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers
    )


def generate_task_id() -> str:
    """生成任务ID"""
    import uuid
    return str(uuid.uuid4())[:8]


def calculate_file_hash(file_path: str) -> str:
    """计算文件哈希值"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def format_duration(seconds: float) -> str:
    """格式化时长"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def ensure_dir(path: str):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)


def load_json(file_path: str) -> Dict[str, Any]:
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Dict[str, Any], file_path: str):
    """保存JSON文件"""
    ensure_dir(str(Path(file_path).parent))
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@lru_cache(maxsize=100)
def get_video_extensions() -> tuple:
    """获取支持的视频扩展名"""
    return ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg')


def is_video_file(file_path: str) -> bool:
    """判断是否为视频文件"""
    path = Path(file_path)
    name = path.name
    
    # 跳过macOS隐藏文件（以 ._ 开头）
    if name.startswith('._'):
        return False
    
    # 跳过其他隐藏文件
    if name.startswith('.'):
        return False
    
    return path.suffix.lower() in get_video_extensions()


def get_file_info(file_path: str) -> Dict[str, Any]:
    """获取文件信息"""
    stat = os.stat(file_path)
    return {
        'path': file_path,
        'name': Path(file_path).name,
        'size': stat.st_size,
        'created': datetime.fromtimestamp(stat.st_ctime),
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'accessed': datetime.fromtimestamp(stat.st_atime),
    }
