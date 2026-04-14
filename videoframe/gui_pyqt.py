"""
VideoFrame GUI - 基于PyQt5的图形化界面
提供视频抽帧和合成的现代化操作界面
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from threading import Thread

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QSpinBox,
        QCheckBox, QProgressBar, QTabWidget, QGroupBox, QFileDialog,
        QMessageBox, QSlider, QGridLayout, QDateEdit
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate
    from PyQt5.QtGui import QFont, QIcon, QPalette, QColor
except ImportError:
    print("错误: 未安装PyQt5")
    print("请运行: pip install PyQt5")
    sys.exit(1)

from videoframe.core import VideoIndexManager, ExtractionEngine, FrameExtractor, VideoComposer
from videoframe.models import ExtractionRule, DateRange, TimeSelection, Sampling, OutputConfig, CompositionConfig

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """扫描工作线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, index_manager, video_dir, recursive, force_rebuild, quick_mode=True, pattern=None):
        super().__init__()
        self.index_manager = index_manager
        self.video_dir = video_dir
        self.recursive = recursive
        self.force_rebuild = force_rebuild
        self.quick_mode = quick_mode
        self.pattern = pattern
    
    def run(self):
        try:
            self.progress.emit("正在扫描视频文件...")
            result = self.index_manager.scan_and_index(
                self.video_dir,
                recursive=self.recursive,
                pattern=self.pattern,
                force_rebuild=self.force_rebuild,
                quick_mode=self.quick_mode
            )
            self.finished.emit({
                'total': result.total_videos,
                'indexed': result.indexed,
                'failed': result.failed,
                'errors': result.errors
            })
        except Exception as e:
            self.error.emit(str(e))


class ExtractionWorker(QThread):
    """抽帧工作线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, index_manager, rule, output_dir, max_workers=8):
        super().__init__()
        self.index_manager = index_manager
        self.rule = rule
        self.output_dir = output_dir
        self.max_workers = max_workers
    
    def run(self):
        try:
            engine = ExtractionEngine(self.index_manager)
            plan = engine.create_extraction_plan(self.rule)
            
            if not plan.frame_locations:
                self.error.emit("没有找到符合条件的视频帧")
                return
            
            # 使用并行批量提取
            extractor = FrameExtractor(self.output_dir, max_workers=self.max_workers)
            total = len(plan.frame_locations)
            
            def progress_callback(current, total_count):
                self.progress.emit(current, total_count)
            
            frames = extractor.extract_from_plan(
                plan,
                max_workers=self.max_workers,
                progress_callback=progress_callback
            )
            
            self.finished.emit(len(frames))
        except Exception as e:
            self.error.emit(str(e))


class CompositionWorker(QThread):
    """合成工作线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, frames_dir, output_file, fps, resolution, codec):
        super().__init__()
        self.frames_dir = frames_dir
        self.output_file = output_file
        self.fps = fps
        self.resolution = resolution
        self.codec = codec
    
    def run(self):
        try:
            config = CompositionConfig(
                fps=self.fps,
                resolution=self.resolution,
                codec=self.codec,
                output_path=self.output_file
            )
            
            composer = VideoComposer(config)
            
            frames_path = Path(self.frames_dir)
            frame_files = list(frames_path.glob('*.jpg'))
            total = len(frame_files)
            
            def progress_callback(current, total_frames):
                self.progress.emit(current, total_frames)
            
            result = composer.compose_from_directory(
                self.frames_dir,
                self.output_file,
                progress_callback=progress_callback
            )
            
            self.finished.emit({
                'output_path': result.output_path,
                'total_frames': result.total_frames,
                'duration': result.duration,
                'file_size': result.file_size
            })
        except Exception as e:
            self.error.emit(str(e))


class VideoFrameGUI(QMainWindow):
    """VideoFrame主窗口"""
    
    def __init__(self):
        super().__init__()
        
        self.index_manager: Optional[VideoIndexManager] = None
        self.current_worker: Optional[QThread] = None
        
        # 启动时清空数据库，避免历史数据混杂
        self._clear_database()
        
        self.init_ui()
        self.setup_logging()
    
    def _clear_database(self):
        """清空数据库中的历史数据"""
        try:
            db_path = str(Path.home() / '.videoframe' / 'index.db')
            if Path(db_path).exists():
                from videoframe.core.index.database import Database
                db = Database(db_path)
                db.clear_all()
                db.close()
                logger.info("Database cleared on startup")
        except Exception as e:
            logger.warning(f"Failed to clear database: {e}")
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("VideoFrame - 监控视频抽帧管理工具 v1.0.0")
        self.setGeometry(100, 100, 1100, 750)
        self.setMinimumSize(1000, 650)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QLabel {
                color: #000000;
                font-size: 13px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
            QLineEdit, QTextEdit, QSpinBox, QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
                color: #000000;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #3498db;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #000000;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #000000;
            }
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                color: #000000;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #000000;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                text-align: center;
                background-color: white;
                color: #000000;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
            QCheckBox {
                 color: #000000;
                 font-size: 13px;
                 spacing: 8px;
             }
             QCheckBox::indicator {
                 width: 18px;
                 height: 18px;
                 border: 2px solid #3498db;
                 border-radius: 3px;
                 background-color: white;
             }
             QCheckBox::indicator:checked {
                 background-color: #3498db;
                 border-color: #3498db;
                 image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMjAgNiA5IDE3IDQgMTIiPjwvcG9seWxpbmU+PC9zdmc+);
             }
             QCheckBox::indicator:hover {
                 border-color: #2980b9;
             }
             QSlider::groove:horizontal {
                 height: 8px;
                 background: #bdc3c7;
                 border-radius: 4px;
             }
             QSlider::handle:horizontal {
                 background: #3498db;
                 width: 18px;
                 margin: -5px 0;
                 border-radius: 9px;
             }
             QDateEdit {
                 border: 1px solid #bdc3c7;
                 border-radius: 4px;
                 padding: 6px;
                 background-color: white;
                 color: #000000;
                 font-size: 13px;
             }
             QDateEdit::drop-down {
                 border: none;
                 width: 30px;
             }
             QDateEdit::down-arrow {
                 width: 12px;
                 height: 12px;
             }
         """)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("🎬 VideoFrame - 监控视频抽帧管理工具")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setStyleSheet("color: #000000; padding: 10px;")
        main_layout.addWidget(title_label)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 添加标签页
        self.create_index_tab()
        self.create_extraction_tab()
        self.create_composition_tab()
        self.create_log_tab()
        
        # 全局底部区域：任务进度和统计信息
        bottom_frame = QWidget()
        bottom_frame.setStyleSheet("background-color: #ecf0f1; border-radius: 6px; padding: 5px;")
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 5, 10, 5)
        
        # 当前任务状态
        task_status_layout = QVBoxLayout()
        task_status_label = QLabel("当前任务")
        task_status_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        task_status_layout.addWidget(task_status_label)
        self.task_label = QLabel("暂无运行中的任务")
        self.task_label.setStyleSheet("color: #000000;")
        task_status_layout.addWidget(self.task_label)
        bottom_layout.addLayout(task_status_layout)
        
        # 分隔线
        separator1 = QLabel("|")
        separator1.setStyleSheet("color: #bdc3c7; font-size: 24px;")
        bottom_layout.addWidget(separator1)
        
        # 进度条区域
        progress_layout = QVBoxLayout()
        progress_title = QLabel("任务进度")
        progress_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        progress_layout.addWidget(progress_title)
        progress_h_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(200)
        progress_h_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet("color: #000000; min-width: 40px;")
        progress_h_layout.addWidget(self.progress_label)
        progress_layout.addLayout(progress_h_layout)
        bottom_layout.addLayout(progress_layout)
        
        # 分隔线
        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #bdc3c7; font-size: 24px;")
        bottom_layout.addWidget(separator2)
        
        # 统计信息
        stats_layout = QVBoxLayout()
        stats_title = QLabel("统计信息")
        stats_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        stats_layout.addWidget(stats_title)
        stats_h_layout = QHBoxLayout()
        stats_h_layout.setSpacing(20)
        
        stats_h_layout.addWidget(QLabel("已扫描:"))
        self.scanned_label = QLabel("0")
        self.scanned_label.setStyleSheet("font-weight: bold; color: #3498db;")
        stats_h_layout.addWidget(self.scanned_label)
        
        stats_h_layout.addWidget(QLabel("已抽帧:"))
        self.extracted_label = QLabel("0")
        self.extracted_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        stats_h_layout.addWidget(self.extracted_label)
        
        stats_h_layout.addWidget(QLabel("已合成:"))
        self.composed_label = QLabel("0")
        self.composed_label.setStyleSheet("font-weight: bold; color: #9b59b6;")
        stats_h_layout.addWidget(self.composed_label)
        
        stats_layout.addLayout(stats_h_layout)
        bottom_layout.addLayout(stats_layout)
        
        bottom_layout.addStretch()
        bottom_frame.setLayout(bottom_layout)
        main_layout.addWidget(bottom_frame)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        self.statusBar().setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        
        central_widget.setLayout(main_layout)
    
    def create_index_tab(self):
        """创建视频索引标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 视频目录设置
        dir_group = QGroupBox("视频目录设置")
        dir_layout = QHBoxLayout()
        
        dir_label = QLabel("视频文件目录：")
        self.video_dir_edit = QLineEdit()
        self.video_dir_edit.setPlaceholderText("请选择包含视频文件的目录")
        
        browse_btn = QPushButton("浏览...")
        browse_btn.setStyleSheet("background-color: #95a5a6;")
        browse_btn.clicked.connect(self.browse_video_dir)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.video_dir_edit)
        dir_layout.addWidget(browse_btn)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # 扫描选项
        options_group = QGroupBox("扫描选项")
        options_layout = QVBoxLayout()
        
        self.recursive_check = QCheckBox("递归扫描子目录")
        self.recursive_check.setChecked(True)
        
        self.force_rebuild_check = QCheckBox("强制重建索引")
        
        self.quick_mode_check = QCheckBox("快速扫描模式（仅解析文件名，不读取视频内容）")
        self.quick_mode_check.setChecked(True)
        self.quick_mode_check.setToolTip("快速模式仅解析文件名获取时间信息，不调用FFprobe读取视频元数据，大幅减少IO开销")
        
        options_layout.addWidget(self.recursive_check)
        options_layout.addWidget(self.force_rebuild_check)
        options_layout.addWidget(self.quick_mode_check)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        scan_btn = QPushButton("🔍 扫描视频文件")
        scan_btn.clicked.connect(self.scan_videos)
        
        stats_btn = QPushButton("📊 查看统计信息")
        stats_btn.setStyleSheet("background-color: #95a5a6;")
        stats_btn.clicked.connect(self.show_statistics)
        
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(stats_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 索引信息显示
        info_group = QGroupBox("索引信息")
        info_layout = QVBoxLayout()
        
        self.index_text = QTextEdit()
        self.index_text.setReadOnly(True)
        self.index_text.setMaximumHeight(250)
        self.index_text.setPlaceholderText("索引信息将在此显示...")
        
        info_layout.addWidget(self.index_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 初始提示
        self.index_text.append("欢迎使用 VideoFrame！\n")
        self.index_text.append("使用步骤：")
        self.index_text.append("1. 选择包含视频文件的目录")
        self.index_text.append("2. 点击\"扫描视频文件\"按钮进行索引")
        self.index_text.append("3. 切换到\"抽帧设置\"标签页配置抽帧规则")
        self.index_text.append("4. 执行抽帧任务")
        self.index_text.append("5. 切换到\"视频合成\"标签页合成延时视频\n")
        self.index_text.append("支持的文件名格式：")
        self.index_text.append("• 小米摄像机: 00_20260327121712_20260327122218.mp4")
        self.index_text.append("• 海康威视: 20250327_121712_122218.mp4")
        self.index_text.append("• 大华: 2025-03-27-12-17-12.mp4")
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "📹 视频索引")
    
    def create_extraction_tab(self):
        """创建抽帧设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 时间范围设置
        time_group = QGroupBox("时间范围设置")
        time_layout = QGridLayout()
        
        time_layout.addWidget(QLabel("开始日期："), 0, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setEnabled(False)
        time_layout.addWidget(self.start_date_edit, 0, 1)
        self.start_date_hint = QLabel("(请先扫描视频文件)")
        time_layout.addWidget(self.start_date_hint, 0, 2)
        
        time_layout.addWidget(QLabel("结束日期："), 1, 0)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setEnabled(False)
        time_layout.addWidget(self.end_date_edit, 1, 1)
        self.end_date_hint = QLabel("(请先扫描视频文件)")
        time_layout.addWidget(self.end_date_hint, 1, 2)
        
        time_layout.addWidget(QLabel("开始时间："), 2, 0)
        self.start_time_edit = QLineEdit("07:00:00")
        time_layout.addWidget(self.start_time_edit, 2, 1)
        time_layout.addWidget(QLabel("(格式: HH:MM:SS)"), 2, 2)
        
        time_layout.addWidget(QLabel("结束时间："), 3, 0)
        self.end_time_edit = QLineEdit("17:00:00")
        time_layout.addWidget(self.end_time_edit, 3, 1)
        time_layout.addWidget(QLabel("(格式: HH:MM:SS)"), 3, 2)
        
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)
        
        # 抽样设置
        sampling_group = QGroupBox("抽样设置")
        sampling_layout = QHBoxLayout()
        
        sampling_layout.addWidget(QLabel("抽帧间隔："))
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1000)
        self.interval_spin.setValue(1)
        sampling_layout.addWidget(self.interval_spin)
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["秒", "分钟", "小时", "天"])
        self.interval_combo.setCurrentText("分钟")
        sampling_layout.addWidget(self.interval_combo)
        
        sampling_layout.addStretch()
        sampling_group.setLayout(sampling_layout)
        layout.addWidget(sampling_group)
        
        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QGridLayout()
        
        output_layout.addWidget(QLabel("输出目录："), 0, 0)
        self.output_dir_edit = QLineEdit("./output")
        output_layout.addWidget(self.output_dir_edit, 0, 1)
        
        output_browse_btn = QPushButton("浏览...")
        output_browse_btn.setStyleSheet("background-color: #95a5a6;")
        output_browse_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(output_browse_btn, 0, 2)
        
        output_layout.addWidget(QLabel("输出格式："), 1, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["jpg", "png", "bmp"])
        output_layout.addWidget(self.format_combo, 1, 1)
        
        output_layout.addWidget(QLabel("输出质量："), 2, 0)
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(95)
        output_layout.addWidget(self.quality_slider, 2, 1)
        
        self.quality_label = QLabel("95")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        output_layout.addWidget(self.quality_label, 2, 2)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        preview_btn = QPushButton("👀 预览抽帧计划")
        preview_btn.setStyleSheet("background-color: #95a5a6;")
        preview_btn.clicked.connect(self.preview_extraction)
        
        extract_btn = QPushButton("🎯 执行抽帧任务")
        extract_btn.clicked.connect(self.execute_extraction)
        
        btn_layout.addWidget(preview_btn)
        btn_layout.addWidget(extract_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "⚙️ 抽帧设置")
    
    def create_composition_tab(self):
        """创建视频合成标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 输入设置
        input_group = QGroupBox("输入设置")
        input_layout = QHBoxLayout()
        
        input_layout.addWidget(QLabel("帧文件目录："))
        self.frames_dir_edit = QLineEdit()
        self.frames_dir_edit.setPlaceholderText("选择包含帧文件的目录")
        input_layout.addWidget(self.frames_dir_edit)
        
        frames_browse_btn = QPushButton("浏览...")
        frames_browse_btn.setStyleSheet("background-color: #95a5a6;")
        frames_browse_btn.clicked.connect(self.browse_frames_dir)
        input_layout.addWidget(frames_browse_btn)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 视频参数设置
        video_group = QGroupBox("视频参数设置")
        video_layout = QGridLayout()
        
        video_layout.addWidget(QLabel("输出文件："), 0, 0)
        self.output_file_edit = QLineEdit("timelapse.mp4")
        video_layout.addWidget(self.output_file_edit, 0, 1)
        
        video_layout.addWidget(QLabel("帧率 (FPS)："), 1, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        video_layout.addWidget(self.fps_spin, 1, 1)
        
        video_layout.addWidget(QLabel("分辨率："), 2, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["640x480", "1280x720", "1920x1080", "2560x1440", "3840x2160"])
        self.resolution_combo.setCurrentText("1920x1080")
        video_layout.addWidget(self.resolution_combo, 2, 1)
        
        video_layout.addWidget(QLabel("视频编码器："), 3, 0)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["h264", "h265", "vp9", "av1"])
        video_layout.addWidget(self.codec_combo, 3, 1)
        
        video_group.setLayout(video_layout)
        layout.addWidget(video_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        compose_btn = QPushButton("🎬 合成视频")
        compose_btn.clicked.connect(self.compose_video)
        
        btn_layout.addWidget(compose_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 视频信息显示
        info_group = QGroupBox("视频信息")
        info_layout = QVBoxLayout()
        
        self.video_text = QTextEdit()
        self.video_text.setReadOnly(True)
        self.video_text.setMaximumHeight(200)
        
        info_layout.addWidget(self.video_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 初始说明
        self.video_text.append("视频合成说明：\n")
        self.video_text.append("1. 确保已完成视频帧提取")
        self.video_text.append("2. 选择包含帧文件的目录")
        self.video_text.append("3. 设置视频参数（帧率、分辨率、编码器）")
        self.video_text.append("4. 点击\"合成视频\"按钮\n")
        self.video_text.append("支持的编码器：")
        self.video_text.append("• H.264: 广泛兼容，适合大多数场景")
        self.video_text.append("• H.265: 更高压缩率，适合4K视频")
        self.video_text.append("• VP9: 开源编码，适合网络分享")
        self.video_text.append("• AV1: 最新编码，压缩效率最高")
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "🎬 视频合成")
    
    def create_log_tab(self):
        """创建运行日志标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 日志显示
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas, Monaco, monospace; font-size: 12px;")
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ 清空日志")
        clear_btn.setStyleSheet("background-color: #95a5a6;")
        clear_btn.clicked.connect(self.clear_log)
        
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "📊 任务进度")
    
    def setup_logging(self):
        """设置日志"""
        class QTextEditHandler(logging.Handler):
            def __init__(self, text_edit):
                super().__init__()
                self.text_edit = text_edit
            
            def emit(self, record):
                msg = self.format(record)
                self.text_edit.append(msg)
        
        handler = QTextEditHandler(self.log_text)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        logger = logging.getLogger('videoframe')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    # 事件处理方法
    def browse_video_dir(self):
        """浏览视频目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择视频文件目录")
        if directory:
            self.video_dir_edit.setText(directory)
            self.log_message(f"已选择视频目录: {directory}")
    
    def browse_output_dir(self):
        """浏览输出目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_dir_edit.setText(directory)
    
    def browse_frames_dir(self):
        """浏览帧文件目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择帧文件目录")
        if directory:
            self.frames_dir_edit.setText(directory)
    
    def scan_videos(self):
        """扫描视频文件"""
        video_dir = self.video_dir_edit.text()
        if not video_dir:
            QMessageBox.warning(self, "警告", "请先选择视频文件目录")
            return
        
        if not Path(video_dir).exists():
            QMessageBox.critical(self, "错误", "视频目录不存在")
            return
        
        # 初始化索引管理器（使用视频目录下的数据库）
        video_dir = self.video_dir_edit.text()
        db_path = str(Path(video_dir).resolve() / '.videoframe' / 'index.db')
        self.index_manager = VideoIndexManager(db_path)
        
        # 创建工作线程
        self.current_worker = ScanWorker(
            self.index_manager,
            video_dir,
            self.recursive_check.isChecked(),
            self.force_rebuild_check.isChecked(),
            self.quick_mode_check.isChecked()
        )
        
        self.current_worker.progress.connect(self.on_scan_progress)
        self.current_worker.finished.connect(self.on_scan_finished)
        self.current_worker.error.connect(self.on_worker_error)
        self.current_worker.start()
        
        self.task_label.setText("正在扫描视频文件...")
        self.statusBar().showMessage("正在扫描视频文件...")
    
    def on_scan_progress(self, message):
        """扫描进度更新"""
        self.task_label.setText(message)
    
    def on_scan_finished(self, result):
        """扫描完成"""
        self.scanned_label.setText(str(result['indexed']))
        
        self.index_text.clear()
        self.index_text.append(f"扫描完成！\n")
        self.index_text.append(f"总文件数: {result['total']}")
        self.index_text.append(f"成功索引: {result['indexed']}")
        self.index_text.append(f"失败: {result['failed']}\n")
        
        if result['errors']:
            self.index_text.append("错误信息:")
            for error in result['errors'][:5]:
                self.index_text.append(f"  • {error}")
        
        # 获取统计信息并更新日期范围
        if self.index_manager:
            stats = self.index_manager.get_statistics()
            if stats.get('earliest_time') and stats.get('latest_time'):
                earliest = stats['earliest_time']
                latest = stats['latest_time']
                
                # 设置日期范围
                min_date = QDate(earliest.year, earliest.month, earliest.day)
                max_date = QDate(latest.year, latest.month, latest.day)
                
                self.start_date_edit.setMinimumDate(min_date)
                self.start_date_edit.setMaximumDate(max_date)
                self.start_date_edit.setDate(min_date)
                self.start_date_edit.setEnabled(True)
                self.start_date_hint.setText(f"(可选范围: {earliest.strftime('%Y-%m-%d')} ~ {latest.strftime('%Y-%m-%d')})")
                
                self.end_date_edit.setMinimumDate(min_date)
                self.end_date_edit.setMaximumDate(max_date)
                self.end_date_edit.setDate(max_date)
                self.end_date_edit.setEnabled(True)
                self.end_date_hint.setText(f"(可选范围: {earliest.strftime('%Y-%m-%d')} ~ {latest.strftime('%Y-%m-%d')})")
                
                self.index_text.append(f"\n视频时间范围: {earliest.strftime('%Y-%m-%d')} ~ {latest.strftime('%Y-%m-%d')}")
                self.index_text.append("已自动设置日期范围，可在\"抽帧设置\"中调整")
        
        self.log_message(f"扫描完成: {result['indexed']}/{result['total']} 视频已索引")
        self.task_label.setText("扫描完成")
        self.statusBar().showMessage("扫描完成")
    
    def on_worker_error(self, error_message):
        """工作线程错误"""
        QMessageBox.critical(self, "错误", error_message)
        self.log_message(f"错误: {error_message}", level='ERROR')
        self.task_label.setText("任务失败")
        self.statusBar().showMessage("任务失败")
    
    def show_statistics(self):
        """显示统计信息"""
        if not self.index_manager:
            QMessageBox.information(self, "提示", "请先扫描视频文件")
            return
        
        stats = self.index_manager.get_statistics()
        
        self.index_text.clear()
        self.index_text.append("索引统计信息\n")
        self.index_text.append(f"总视频数: {stats['total_videos']}")
        self.index_text.append(f"已索引: {stats['indexed_videos']}")
        self.index_text.append(f"总大小: {self.format_size(stats['total_size'])}")
        
        if stats['earliest_time']:
            self.index_text.append(f"最早时间: {stats['earliest_time']}")
        if stats['latest_time']:
            self.index_text.append(f"最晚时间: {stats['latest_time']}")
    
    def preview_extraction(self):
        """预览抽帧计划"""
        if not self.index_manager:
            QMessageBox.information(self, "提示", "请先扫描视频文件")
            return
        
        try:
            rule = self._create_extraction_rule()
            engine = ExtractionEngine(self.index_manager)
            preview = engine.preview_extraction(rule)
            
            QMessageBox.information(
                self,
                "抽帧计划预览",
                f"总提取点: {preview['total_points']}\n"
                f"总帧数: {preview['total_frames']}\n\n"
                f"日期范围: {preview['date_range']['start']} ~ {preview['date_range']['end']}\n"
                f"时间段: {preview['time_selection']['start']} ~ {preview['time_selection']['end']}\n"
                f"采样间隔: {preview['sampling']['interval']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"预览失败: {str(e)}")
    
    def execute_extraction(self):
        """执行抽帧任务"""
        if not self.index_manager:
            QMessageBox.information(self, "提示", "请先扫描视频文件")
            return
        
        try:
            rule = self._create_extraction_rule()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"规则配置错误: {str(e)}")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要执行抽帧任务吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # 创建工作线程
        self.current_worker = ExtractionWorker(
            self.index_manager,
            rule,
            self.output_dir_edit.text()
        )
        
        self.current_worker.progress.connect(self.on_extraction_progress)
        self.current_worker.finished.connect(self.on_extraction_finished)
        self.current_worker.error.connect(self.on_worker_error)
        self.current_worker.start()
        
        self.task_label.setText("正在执行抽帧任务...")
        self.statusBar().showMessage("正在执行抽帧任务...")
    
    def on_extraction_progress(self, current, total):
        """抽帧进度更新"""
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{progress}% ({current}/{total})")
    
    def on_extraction_finished(self, count):
        """抽帧完成"""
        self.extracted_label.setText(str(count))
        self.log_message(f"抽帧完成: {count} 帧已提取")
        QMessageBox.information(self, "成功", f"抽帧完成！\n成功提取 {count} 帧")
        self.task_label.setText("抽帧完成")
        self.statusBar().showMessage("抽帧完成")
    
    def compose_video(self):
        """合成视频"""
        frames_dir = self.frames_dir_edit.text()
        if not frames_dir or not Path(frames_dir).exists():
            QMessageBox.critical(self, "错误", "请选择有效的帧文件目录")
            return
        
        output_file = self.output_file_edit.text()
        if not output_file:
            QMessageBox.critical(self, "错误", "请指定输出文件名")
            return
        
        # 解析分辨率
        resolution_str = self.resolution_combo.currentText()
        width, height = map(int, resolution_str.split('x'))
        
        # 创建工作线程
        self.current_worker = CompositionWorker(
            frames_dir,
            output_file,
            self.fps_spin.value(),
            (width, height),
            self.codec_combo.currentText()
        )
        
        self.current_worker.progress.connect(self.on_composition_progress)
        self.current_worker.finished.connect(self.on_composition_finished)
        self.current_worker.error.connect(self.on_worker_error)
        self.current_worker.start()
        
        self.task_label.setText("正在合成视频...")
        self.statusBar().showMessage("正在合成视频...")
    
    def on_composition_progress(self, current, total):
        """合成进度更新"""
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{progress}% ({current}/{total})")
    
    def on_composition_finished(self, result):
        """合成完成"""
        self.composed_label.setText("1")
        
        self.video_text.clear()
        self.video_text.append("视频合成完成！\n")
        self.video_text.append(f"输出文件: {result['output_path']}")
        self.video_text.append(f"总帧数: {result['total_frames']}")
        self.video_text.append(f"时长: {result['duration']:.2f}秒")
        self.video_text.append(f"文件大小: {self.format_size(result['file_size'])}")
        
        self.log_message(f"视频合成完成: {result['output_path']}")
        QMessageBox.information(self, "成功", f"视频合成完成！\n输出文件: {result['output_path']}")
        self.task_label.setText("合成完成")
        self.statusBar().showMessage("合成完成")
    
    def _create_extraction_rule(self):
        """创建抽帧规则"""
        # 从日期选择器获取日期
        if not self.start_date_edit.isEnabled() or not self.end_date_edit.isEnabled():
            raise ValueError("请先扫描视频文件以设置日期范围")
        
        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()
        
        start_date = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day()).date()
        end_date = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day()).date()
        
        # 解析时间
        try:
            start_time = datetime.strptime(self.start_time_edit.text(), '%H:%M:%S').time()
            end_time = datetime.strptime(self.end_time_edit.text(), '%H:%M:%S').time()
        except ValueError:
            raise ValueError("时间格式错误，请使用 HH:MM:SS 格式")
        
        # 解析间隔
        interval_value = self.interval_spin.value()
        unit = self.interval_combo.currentText()
        
        if unit == "秒":
            interval = timedelta(seconds=interval_value)
        elif unit == "分钟":
            interval = timedelta(minutes=interval_value)
        elif unit == "小时":
            interval = timedelta(hours=interval_value)
        elif unit == "天":
            interval = timedelta(days=interval_value)
        else:
            interval = timedelta(minutes=interval_value)
        
        return ExtractionRule(
            name="GUI抽帧规则",
            description="从GUI创建的抽帧规则",
            date_range=DateRange(
                start_date=start_date,
                end_date=end_date
            ),
            time_selection=TimeSelection(
                start_time=start_time,
                end_time=end_time
            ),
            sampling=Sampling(
                interval=interval
            ),
            output=OutputConfig(
                format=self.format_combo.currentText(),
                quality=self.quality_slider.value(),
                output_dir=self.output_dir_edit.text()
            )
        )
    
    def log_message(self, message, level='INFO'):
        """记录日志消息"""
        logger = logging.getLogger('videoframe')
        if level == 'ERROR':
            logger.error(message)
        elif level == 'WARNING':
            logger.warning(message)
        else:
            logger.info(message)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
    
    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        if self.index_manager:
            try:
                self.index_manager.close()
            except Exception as e:
                logger.warning(f"Failed to close database: {e}")
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
        super().closeEvent(event)
    
    @staticmethod
    def format_size(size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = VideoFrameGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
