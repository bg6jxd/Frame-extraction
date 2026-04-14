"""
帧提取器模块
"""
import os
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import multiprocessing

from videoframe.models import FrameLocation, ExtractedFrame, ExtractionPlan
from videoframe.utils import ensure_dir


logger = logging.getLogger(__name__)


class FrameExtractor:
    """帧提取器"""
    
    def __init__(self, output_dir: str = "./frames", max_workers: int = None):
        self.output_dir = output_dir
        ensure_dir(output_dir)
        # 默认使用CPU核心数的2倍作为最大线程数
        self.max_workers = max_workers or min(multiprocessing.cpu_count() * 2, 16)
    
    def extract_frame(
        self,
        location: FrameLocation,
        output_format: str = "jpg",
        quality: int = 95
    ) -> Optional[ExtractedFrame]:
        """提取单帧"""
        
        output_filename = self._generate_filename(location, output_format)
        output_path = os.path.join(self.output_dir, output_filename)
        
        try:
            # FFmpeg q:v 范围是 2-31（JPEG），2 最高质量，31 最低
            # 将 1-100 质量映射到 2-31
            q_value = max(2, min(31, 31 - int(quality * 29 / 100)))
            
            cmd = [
                'ffmpeg',
                '-ss', str(location.time_offset),  # 在输入前seek，速度更快
                '-i', location.video_file.file_path,
                '-vframes', '1',
                '-q:v', str(q_value),
                '-threads', '1',  # 单帧提取使用单线程
                '-preset', 'ultrafast',  # 最快预设
                '-y',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr.decode()}")
                return None
            
            if not os.path.exists(output_path):
                return None
            
            stat = os.stat(output_path)
            
            return ExtractedFrame(
                file_path=output_path,
                timestamp=location.timestamp,
                frame_number=location.frame_number,
                camera_id=location.video_file.camera_id,
                resolution=location.video_file.resolution,
                size=stat.st_size
            )
        
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout extracting frame from {location.video_file.file_path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting frame: {e}")
            return None
    
    def extract_batch(
        self,
        locations: List[FrameLocation],
        output_format: str = "jpg",
        quality: int = 95,
        max_workers: int = None,
        progress_callback: Optional[Callable] = None
    ) -> List[ExtractedFrame]:
        """批量提取帧（并行处理）"""
        
        workers = max_workers or self.max_workers
        results = []
        total = len(locations)
        
        logger.info(f"Starting batch extraction: {total} frames with {workers} workers")
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self.extract_frame,
                    loc,
                    output_format,
                    quality
                ): loc
                for loc in locations
            }
            
            for future in as_completed(futures):
                try:
                    frame = future.result()
                    if frame:
                        results.append(frame)
                    
                    if progress_callback:
                        progress_callback(len(results), total)
                
                except Exception as e:
                    logger.error(f"Error in batch extraction: {e}")
        
        logger.info(f"Batch extraction completed: {len(results)}/{total} frames extracted")
        return results
    
    def extract_from_plan(
        self,
        plan: ExtractionPlan,
        max_workers: int = None,
        progress_callback: Optional[Callable] = None
    ) -> List[ExtractedFrame]:
        """根据计划提取帧"""
        
        output_config = plan.rule.output
        
        return self.extract_batch(
            plan.frame_locations,
            output_format=output_config.format if output_config else "jpg",
            quality=output_config.quality if output_config else 95,
            max_workers=max_workers or self.max_workers,
            progress_callback=progress_callback
        )
    
    def _generate_filename(self, location: FrameLocation, format: str) -> str:
        """生成输出文件名"""
        
        timestamp_str = location.timestamp.strftime("%Y%m%d_%H%M%S")
        return f"{timestamp_str}_{location.video_file.camera_id}_{location.frame_number:08d}.{format}"


class ExtractionTaskManager:
    """抽帧任务管理器"""
    
    def __init__(self):
        self.tasks = {}
    
    def create_task(self, plan: ExtractionPlan) -> str:
        """创建任务"""
        from videoframe.utils import generate_task_id
        
        task_id = generate_task_id()
        self.tasks[task_id] = {
            'plan': plan,
            'status': 'pending',
            'progress': 0,
            'extracted_frames': [],
            'errors': [],
        }
        
        return task_id
    
    def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        return self.tasks.get(task_id, {})
    
    def update_task_progress(self, task_id: str, progress: int, total: int):
        """更新任务进度"""
        if task_id in self.tasks:
            self.tasks[task_id]['progress'] = progress / total if total > 0 else 0
