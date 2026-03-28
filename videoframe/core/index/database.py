"""
视频索引管理模块
"""
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

from videoframe.models import VideoFile, IndexStatus
from videoframe.utils import ensure_dir


logger = logging.getLogger(__name__)


class Database:
    """数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        ensure_dir(str(Path(db_path).parent))
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化数据库"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size BIGINT,
                    start_time DATETIME,
                    end_time DATETIME,
                    duration_seconds INTEGER,
                    fps REAL,
                    resolution_width INTEGER,
                    resolution_height INTEGER,
                    codec TEXT,
                    bitrate BIGINT,
                    camera_id TEXT,
                    index_status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_range 
                ON video_files(start_time, end_time)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_camera 
                ON video_files(camera_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_name 
                ON video_files(file_name)
            ''')
            
            conn.commit()
    
    def insert_video(self, video: VideoFile) -> int:
        """插入视频记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO video_files 
                (file_path, file_name, file_size, start_time, end_time, 
                 duration_seconds, fps, resolution_width, resolution_height, 
                 codec, bitrate, camera_id, index_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                video.file_path,
                video.file_name,
                video.file_size,
                video.start_time.isoformat() if video.start_time else None,
                video.end_time.isoformat() if video.end_time else None,
                video.duration_seconds,
                video.fps,
                video.resolution_width,
                video.resolution_height,
                video.codec,
                video.bitrate,
                video.camera_id,
                video.index_status.value,
                video.created_at.isoformat() if video.created_at else None,
                video.updated_at.isoformat() if video.updated_at else None,
            ))
            
            conn.commit()
            return cursor.lastrowid or 0
    
    def query_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        camera_id: Optional[str] = None
    ) -> List[VideoFile]:
        """按时间范围查询视频"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if camera_id:
                cursor.execute('''
                    SELECT * FROM video_files 
                    WHERE start_time <= ? AND end_time >= ?
                    AND camera_id = ?
                    AND index_status = 'completed'
                    ORDER BY start_time
                ''', (end_time.isoformat(), start_time.isoformat(), camera_id))
            else:
                cursor.execute('''
                    SELECT * FROM video_files 
                    WHERE start_time <= ? AND end_time >= ?
                    AND index_status = 'completed'
                    ORDER BY start_time
                ''', (end_time.isoformat(), start_time.isoformat()))
            
            rows = cursor.fetchall()
            return [self._row_to_video(row) for row in rows]
    
    def get_all_videos(self) -> List[VideoFile]:
        """获取所有视频"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM video_files ORDER BY start_time')
            rows = cursor.fetchall()
            return [self._row_to_video(row) for row in rows]
    
    def get_video_by_path(self, file_path: str) -> Optional[VideoFile]:
        """根据路径获取视频"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM video_files WHERE file_path = ?', (file_path,))
            row = cursor.fetchone()
            return self._row_to_video(row) if row else None
    
    def delete_video(self, file_path: str):
        """删除视频记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM video_files WHERE file_path = ?', (file_path,))
            conn.commit()
    
    def clear_all(self):
        """清除所有视频记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM video_files')
            conn.commit()
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM video_files')
            total_videos = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM video_files WHERE index_status = "completed"')
            indexed_videos = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(file_size) FROM video_files')
            total_size = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT MIN(start_time) FROM video_files WHERE start_time IS NOT NULL')
            earliest = cursor.fetchone()[0]
            
            cursor.execute('SELECT MAX(end_time) FROM video_files WHERE end_time IS NOT NULL')
            latest = cursor.fetchone()[0]
            
            # 将字符串转换为datetime对象
            earliest_time = datetime.fromisoformat(earliest) if earliest else None
            latest_time = datetime.fromisoformat(latest) if latest else None
            
            return {
                'total_videos': total_videos,
                'indexed_videos': indexed_videos,
                'total_size': total_size,
                'earliest_time': earliest_time,
                'latest_time': latest_time,
            }
    
    def _row_to_video(self, row: sqlite3.Row) -> VideoFile:
        """将数据库行转换为VideoFile对象"""
        return VideoFile(
            id=row['id'],
            file_path=row['file_path'],
            file_name=row['file_name'],
            file_size=row['file_size'] or 0,
            start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else None,
            end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
            duration_seconds=row['duration_seconds'] or 0,
            fps=row['fps'] or 0.0,
            resolution_width=row['resolution_width'] or 0,
            resolution_height=row['resolution_height'] or 0,
            codec=row['codec'] or '',
            bitrate=row['bitrate'] or 0,
            camera_id=row['camera_id'] or '',
            index_status=IndexStatus(row['index_status']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )
