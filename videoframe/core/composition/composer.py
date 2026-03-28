"""
视频合成器模块
"""
import os
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from videoframe.models import ExtractedFrame, CompositionConfig, CompositionResult
from videoframe.utils import ensure_dir


logger = logging.getLogger(__name__)


class VideoComposer:
    """视频合成器"""
    
    def __init__(self, config: CompositionConfig):
        self.config = config
        self.encoder_process = None
        self.frame_count = 0
    
    def compose(
        self,
        frames: List[ExtractedFrame],
        output_path: Optional[str] = None,
        progress_callback=None
    ) -> CompositionResult:
        """合成视频"""
        
        if not frames:
            raise ValueError("No frames to compose")
        
        output_path = output_path or self.config.output_path
        ensure_dir(str(Path(output_path).parent))
        
        frames.sort(key=lambda f: f.timestamp)
        
        self._initialize_encoder(output_path)
        
        try:
            for i, frame in enumerate(frames):
                self._encode_frame(frame)
                
                if progress_callback:
                    progress_callback(i + 1, len(frames))
            
            self._finalize_encoder()
            
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            duration = self.frame_count / self.config.fps
            
            return CompositionResult(
                output_path=output_path,
                total_frames=self.frame_count,
                duration=duration,
                file_size=file_size,
                fps=self.config.fps,
                resolution=self.config.resolution
            )
        
        except Exception as e:
            logger.error(f"Composition error: {e}")
            raise
    
    def _initialize_encoder(self, output_path: str):
        """初始化编码器"""
        
        width, height = self.config.resolution
        
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'image2pipe',
            '-vcodec', 'mjpeg',
            '-r', str(self.config.fps),
            '-i', '-',
            '-c:v', self.config.codec,
            '-preset', self.config.preset,
            '-crf', str(self.config.crf),
            '-s', f'{width}x{height}',
            '-pix_fmt', 'yuv420p',
            output_path
        ]
        
        self.encoder_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.frame_count = 0
    
    def _encode_frame(self, frame: ExtractedFrame):
        """编码单帧"""
        
        if not os.path.exists(frame.file_path):
            logger.warning(f"Frame file not found: {frame.file_path}")
            return
        
        with open(frame.file_path, 'rb') as f:
            frame_data = f.read()
        
        try:
            if self.encoder_process and self.encoder_process.stdin:
                self.encoder_process.stdin.write(frame_data)
                self.frame_count += 1
        except BrokenPipeError:
            if self.encoder_process and self.encoder_process.stderr:
                stderr = self.encoder_process.stderr.read().decode()
                raise RuntimeError(f"FFmpeg encoding failed: {stderr}")
    
    def _finalize_encoder(self):
        """完成编码"""
        
        if self.encoder_process:
            if self.encoder_process.stdin:
                self.encoder_process.stdin.close()
            self.encoder_process.wait()
            
            if self.encoder_process.returncode != 0:
                if self.encoder_process.stderr:
                    stderr = self.encoder_process.stderr.read().decode()
                    raise RuntimeError(f"FFmpeg encoding failed: {stderr}")
    
    def compose_from_directory(
        self,
        directory: str,
        output_path: Optional[str] = None,
        pattern: str = "*.jpg",
        progress_callback=None
    ) -> CompositionResult:
        """从目录合成视频"""
        
        dir_path = Path(directory)
        frame_files = sorted(dir_path.glob(pattern))
        
        frames = []
        for i, file_path in enumerate(frame_files):
            stat = file_path.stat()
            frames.append(ExtractedFrame(
                file_path=str(file_path),
                timestamp=datetime.fromtimestamp(stat.st_mtime),
                frame_number=i,
                size=stat.st_size
            ))
        
        return self.compose(frames, output_path, progress_callback)
