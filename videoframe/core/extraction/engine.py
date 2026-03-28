"""
抽帧引擎模块
"""
import logging
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, date, time

from videoframe.models import (
    ExtractionRule, ExtractionPoint, ExtractionPlan,
    FrameLocation, VideoFile, DateRange, TimeSelection, Sampling, SamplingMethod
)
from videoframe.core.index import VideoIndexManager


logger = logging.getLogger(__name__)


class TimeCalculator:
    """时间计算引擎"""
    
    def calculate_extraction_points(
        self,
        date_range: DateRange,
        time_selection: TimeSelection,
        sampling: Sampling
    ) -> List[ExtractionPoint]:
        """计算所有需要提取的时间点"""
        
        if not date_range.start_date or not date_range.end_date:
            return []
        
        points = []
        current_date = date_range.start_date
        
        while current_date <= date_range.end_date:
            if self._should_process_date(current_date, date_range):
                daily_points = self._calculate_daily_points(
                    current_date,
                    time_selection,
                    sampling
                )
                points.extend(daily_points)
            
            current_date += timedelta(days=1)
        
        return points
    
    def _should_process_date(self, check_date: date, date_range: DateRange) -> bool:
        """判断是否应该处理该日期"""
        return check_date not in date_range.exclude_dates
    
    def _calculate_daily_points(
        self,
        target_date: date,
        time_selection: TimeSelection,
        sampling: Sampling
    ) -> List[ExtractionPoint]:
        """计算单日的提取时间点"""
        
        if sampling.method == SamplingMethod.INTERVAL:
            return self._interval_sampling(target_date, time_selection, sampling.interval)
        elif sampling.method == SamplingMethod.SPECIFIC_TIMES:
            return self._specific_time_sampling(target_date, sampling.specific_times)
        else:
            return self._interval_sampling(target_date, time_selection, sampling.interval)
    
    def _interval_sampling(
        self,
        target_date: date,
        time_selection: TimeSelection,
        interval: timedelta
    ) -> List[ExtractionPoint]:
        """间隔采样"""
        
        points = []
        
        if time_selection.type == "full_day":
            start_dt = datetime.combine(target_date, time.min)
            end_dt = datetime.combine(target_date, time.max)
        else:
            start_time = time_selection.start_time or time.min
            end_time = time_selection.end_time or time.max
            start_dt = datetime.combine(target_date, start_time)
            end_dt = datetime.combine(target_date, end_time)
        
        current_dt = start_dt
        while current_dt <= end_dt:
            points.append(ExtractionPoint(
                timestamp=current_dt,
                method="interval"
            ))
            current_dt += interval
        
        return points
    
    def _specific_time_sampling(
        self,
        target_date: date,
        specific_times: List[time]
    ) -> List[ExtractionPoint]:
        """指定时间点采样"""
        
        points = []
        for t in specific_times:
            dt = datetime.combine(target_date, t)
            points.append(ExtractionPoint(
                timestamp=dt,
                method="specific_time"
            ))
        
        return points


class FrameLocator:
    """帧定位器"""
    
    def locate_frame(
        self,
        video_file: VideoFile,
        target_time: datetime
    ) -> Optional[FrameLocation]:
        """定位视频中的特定帧"""
        
        if not video_file.start_time or not video_file.end_time:
            return None
        
        time_offset = (target_time - video_file.start_time).total_seconds()
        
        if time_offset < 0 or time_offset > video_file.duration_seconds:
            return None
        
        frame_number = int(time_offset * video_file.fps) if video_file.fps > 0 else 0
        
        return FrameLocation(
            video_file=video_file,
            frame_number=frame_number,
            timestamp=target_time,
            time_offset=time_offset
        )
    
    def batch_locate(
        self,
        extraction_points: List[ExtractionPoint],
        video_index: VideoIndexManager
    ) -> List[FrameLocation]:
        """批量定位帧"""
        
        locations = []
        
        for point in extraction_points:
            videos = video_index.query_by_time_range(
                point.timestamp,
                point.timestamp + timedelta(seconds=1)
            )
            
            for video in videos:
                location = self.locate_frame(video, point.timestamp)
                if location:
                    locations.append(location)
                    break
        
        return locations


class ExtractionEngine:
    """抽帧引擎"""
    
    def __init__(self, video_index: VideoIndexManager):
        self.video_index = video_index
        self.time_calculator = TimeCalculator()
        self.frame_locator = FrameLocator()
    
    def create_extraction_plan(self, rule: ExtractionRule) -> ExtractionPlan:
        """创建抽帧计划"""
        
        if not rule.date_range or not rule.time_selection or not rule.sampling:
            return ExtractionPlan(video_mappings=[], rule=rule, frame_locations=[])
        
        extraction_points = self.time_calculator.calculate_extraction_points(
            rule.date_range,
            rule.time_selection,
            rule.sampling
        )
        
        video_mappings = []
        for point in extraction_points:
            videos = self.video_index.query_by_time_range(
                point.timestamp,
                point.timestamp + timedelta(seconds=1)
            )
            video_mappings.append((point, videos))
        
        frame_locations = self.frame_locator.batch_locate(
            extraction_points,
            self.video_index
        )
        
        return ExtractionPlan(
            video_mappings=video_mappings,
            rule=rule,
            frame_locations=frame_locations
        )
    
    def preview_extraction(self, rule: ExtractionRule) -> dict:
        """预览抽帧计划"""
        
        plan = self.create_extraction_plan(rule)
        
        date_range_info = {}
        if rule.date_range:
            date_range_info = {
                'start': rule.date_range.start_date.isoformat() if rule.date_range.start_date else None,
                'end': rule.date_range.end_date.isoformat() if rule.date_range.end_date else None,
            }
        
        time_selection_info = {}
        if rule.time_selection:
            time_selection_info = {
                'start': rule.time_selection.start_time.strftime("%H:%M:%S") if rule.time_selection.start_time else None,
                'end': rule.time_selection.end_time.strftime("%H:%M:%S") if rule.time_selection.end_time else None,
            }
        
        sampling_info = {}
        if rule.sampling:
            sampling_info = {
                'method': rule.sampling.method.value,
                'interval': str(rule.sampling.interval),
            }
        
        return {
            'total_points': len(plan.video_mappings),
            'total_frames': len(plan.frame_locations),
            'date_range': date_range_info,
            'time_selection': time_selection_info,
            'sampling': sampling_info,
        }
