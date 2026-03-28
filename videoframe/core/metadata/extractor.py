"""
元数据解析模块
"""
import re
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from videoframe.models import VideoFile, IndexStatus
from videoframe.utils import is_video_file, get_file_info


logger = logging.getLogger(__name__)


class FileNameParser:
    """视频文件名解析器"""
    
    PATTERNS = {
        'xiaomi': r'(\d{2})_(\d{14})_(\d{14})\.(mp4|avi|mov|mkv)',
        'hikvision': r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
        'dahua': r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})',
    }
    
    def parse(self, filename: str) -> Optional[Dict[str, Any]]:
        """解析文件名，返回视频元数据"""
        for pattern_name, pattern in self.PATTERNS.items():
            match = re.search(pattern, filename)
            if match:
                return self._extract_metadata(match, pattern_name)
        return None
    
    def _extract_metadata(self, match: re.Match, pattern_name: str) -> Dict[str, Any]:
        """提取元数据"""
        if pattern_name == 'xiaomi':
            camera_id = match.group(1)
            start_time = datetime.strptime(match.group(2), '%Y%m%d%H%M%S')
            end_time = datetime.strptime(match.group(3), '%Y%m%d%H%M%S')
            
            return {
                'camera_id': camera_id,
                'start_time': start_time,
                'end_time': end_time,
                'pattern': pattern_name,
            }
        
        elif pattern_name == 'hikvision':
            start_time = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                int(match.group(4)), int(match.group(5)), int(match.group(6))
            )
            end_time = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                int(match.group(7)), int(match.group(8)), int(match.group(9))
            )
            
            return {
                'camera_id': '00',
                'start_time': start_time,
                'end_time': end_time,
                'pattern': pattern_name,
            }
        
        elif pattern_name == 'dahua':
            start_time = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                int(match.group(4)), int(match.group(5)), int(match.group(6))
            )
            
            return {
                'camera_id': '00',
                'start_time': start_time,
                'end_time': None,
                'pattern': pattern_name,
            }
        
        return {}


class MetadataExtractor:
    """视频元数据提取器"""
    
    def __init__(self):
        self.filename_parser = FileNameParser()
    
    def extract(self, file_path: str, quick_mode: bool = False) -> VideoFile:
        """提取视频元数据
        
        Args:
            file_path: 视频文件路径
            quick_mode: 快速模式，仅解析文件名，不调用FFprobe
        """
        if not is_video_file(file_path):
            raise ValueError(f"Not a video file: {file_path}")
        
        file_info = get_file_info(file_path)
        video = VideoFile(
            file_path=file_path,
            file_name=file_info['name'],
            file_size=file_info['size'],
            created_at=file_info['created'],
            updated_at=file_info['modified'],
        )
        
        filename_metadata = self.filename_parser.parse(file_info['name'])
        
        if filename_metadata:
            video.camera_id = filename_metadata.get('camera_id', '')
            video.start_time = filename_metadata.get('start_time')
            video.end_time = filename_metadata.get('end_time')
            
            if video.start_time and video.end_time:
                duration = (video.end_time - video.start_time).total_seconds()
                video.duration_seconds = int(duration)
        
        # 快速模式跳过FFprobe
        if quick_mode:
            video.index_status = IndexStatus.COMPLETED
            return video
        
        try:
            video_metadata = self._extract_video_metadata(file_path)
            if video_metadata:
                if not video.fps:
                    video.fps = video_metadata.get('fps', 0.0)
                if not video.resolution_width:
                    video.resolution_width = video_metadata.get('width', 0)
                if not video.resolution_height:
                    video.resolution_height = video_metadata.get('height', 0)
                if not video.codec:
                    video.codec = video_metadata.get('codec', '')
                if not video.bitrate:
                    video.bitrate = video_metadata.get('bitrate', 0)
                if not video.duration_seconds:
                    video.duration_seconds = int(video_metadata.get('duration', 0))
        except Exception as e:
            logger.warning(f"Failed to extract video metadata: {e}")
        
        video.index_status = IndexStatus.COMPLETED
        return video
    
    def quick_extract(self, file_path: str) -> VideoFile:
        """快速提取视频元数据（仅解析文件名，不读取文件内容）"""
        return self.extract(file_path, quick_mode=True)
    
    def _extract_video_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """使用FFmpeg提取视频元数据"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            import json
            data = json.loads(result.stdout)
            
            metadata = {}
            
            if 'format' in data:
                format_info = data['format']
                metadata['duration'] = float(format_info.get('duration', 0))
                metadata['bitrate'] = int(format_info.get('bit_rate', 0))
            
            if 'streams' in data:
                for stream in data['streams']:
                    if stream.get('codec_type') == 'video':
                        metadata['width'] = stream.get('width', 0)
                        metadata['height'] = stream.get('height', 0)
                        metadata['codec'] = stream.get('codec_name', '')
                        
                        fps_str = stream.get('r_frame_rate', '0/1')
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            metadata['fps'] = float(num) / float(den) if float(den) > 0 else 0.0
                        else:
                            metadata['fps'] = float(fps_str)
                        
                        break
            
            return metadata
        
        except Exception as e:
            logger.error(f"FFprobe error: {e}")
            return None
