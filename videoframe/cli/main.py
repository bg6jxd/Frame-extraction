"""
CLI 主入口
"""
import click
import logging
import subprocess
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Optional

from videoframe import __version__
from videoframe.core import VideoIndexManager, ExtractionEngine, FrameExtractor, VideoComposer
from videoframe.models import ExtractionRule, DateRange, TimeSelection, Sampling, OutputConfig, CompositionConfig
from videoframe.utils import setup_logging, format_duration, format_file_size, ensure_dir


# 全局工具检查
def _check_ffmpeg():
    """检查 ffmpeg/ffprobe 是否可用"""
    for tool in ['ffmpeg', 'ffprobe']:
        if subprocess.run(['which', tool], capture_output=True).returncode != 0:
            click.echo(f"❌ 错误：未找到 {tool}，请先安装 ffmpeg")
            click.echo("   macOS: brew install ffmpeg")
            click.echo("   Ubuntu: sudo apt install ffmpeg")
            raise SystemExit(1)


@click.group()
@click.version_option(version=__version__)
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.option('--log-file', type=click.Path(), help='日志文件路径')
@click.pass_context
def cli(ctx, verbose, log_file):
    """VideoFrame - 监控视频抽帧管理工具"""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level, log_file)
    
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


def _get_db_path(directory: str, db_path: Optional[str] = None) -> str:
    """获取数据库路径，优先使用显式指定，否则基于目录生成"""
    if db_path:
        return db_path
    return str(Path(directory).resolve() / '.videoframe' / 'index.db')


@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--name', default='default', help='项目名称')
@click.option('--camera-type', default='xiaomi', help='摄像头类型')
@click.option('--db-path', type=click.Path(), help='数据库路径')
def init(directory, name, camera_type, db_path):
    """初始化项目"""
    _check_ffmpeg()
    click.echo(f"🎬 初始化项目: {directory}")
    
    db_path = _get_db_path(directory, db_path)
    db_dir = Path(db_path).parent
    ensure_dir(str(db_dir))
    
    # 创建项目配置文件
    config_path = db_dir / 'project.yaml'
    if not config_path.exists():
        import yaml
        project_config = {
            'name': name,
            'camera_type': camera_type,
            'db_path': db_path,
            'created_at': datetime.now().isoformat(),
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(project_config, f, allow_unicode=True, default_flow_style=False)
        click.echo(f"   配置文件: {config_path}")
    
    # 初始化数据库
    index_manager = VideoIndexManager(db_path)
    
    click.echo(f"✅ 项目初始化完成")
    click.echo(f"   数据库: {db_path}")
    click.echo(f"   摄像头类型: {camera_type}")
    click.echo(f"   项目名称: {name}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, default=False, help='递归扫描子目录')
@click.option('--pattern', help='文件名匹配模式')
@click.option('--force', is_flag=True, help='强制重新扫描')
@click.option('--parallel', default=4, help='并行处理数量')
@click.option('--quick/--no-quick', default=True, help='快速模式（仅解析文件名）')
@click.pass_context
def scan(ctx, directory, recursive, pattern, force, parallel, quick):
    """扫描视频目录"""
    _check_ffmpeg()
    click.echo(f"🔍 扫描目录: {directory}")
    
    db_path = _get_db_path(directory)
    index_manager = VideoIndexManager(db_path)
    
    # 预估文件数量用于进度条
    dir_path = Path(directory).resolve()
    if recursive:
        total_estimate = sum(1 for f in dir_path.rglob('*') if f.is_file() and f.suffix.lower() in ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'))
    else:
        total_estimate = sum(1 for f in dir_path.glob('*') if f.is_file() and f.suffix.lower() in ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'))
    
    with click.progressbar(length=total_estimate or 1, label='扫描进度') as bar:
        result = index_manager.scan_and_index(
            directory,
            recursive=recursive,
            pattern=pattern,
            force_rebuild=force,
            quick_mode=quick,
            progress_callback=lambda v, r: bar.update(1) if total_estimate > 0 else None
        )
    
    click.echo(f"\n✅ 扫描完成:")
    click.echo(f"   总文件数: {result.total_videos}")
    click.echo(f"   成功索引: {result.indexed}")
    click.echo(f"   失败: {result.failed}")
    
    if result.errors and ctx.obj['verbose']:
        click.echo("\n❌ 错误信息:")
        for error in result.errors[:5]:
            click.echo(f"   - {error}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True), required=False)
@click.option('--rebuild', is_flag=True, help='重建索引')
@click.option('--show-stats', is_flag=True, help='显示统计信息')
def index(directory, rebuild, show_stats):
    """构建索引"""
    if directory is None:
        directory = '.'
    
    _check_ffmpeg()
    db_path = _get_db_path(directory)
    index_manager = VideoIndexManager(db_path)
    
    if show_stats:
        stats = index_manager.get_statistics()
        click.echo("📊 索引统计:")
        click.echo(f"   总视频数: {stats['total_videos']}")
        click.echo(f"   已索引: {stats['indexed_videos']}")
        click.echo(f"   总大小: {format_file_size(stats['total_size'])}")
        if stats['earliest_time']:
            click.echo(f"   最早时间: {stats['earliest_time']}")
        if stats['latest_time']:
            click.echo(f"   最晚时间: {stats['latest_time']}")
    else:
        click.echo("🔨 构建索引...")
        # 实际执行扫描和索引
        result = index_manager.scan_and_index(
            directory,
            recursive=True,
            force_rebuild=rebuild,
            quick_mode=True
        )
        click.echo(f"✅ 索引构建完成:")
        click.echo(f"   总视频数: {result.total_videos}")
        click.echo(f"   成功索引: {result.indexed}")
        click.echo(f"   失败: {result.failed}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True), required=False)
@click.option('--time-range', help='时间范围 (格式: YYYY-MM-DD~YYYY-MM-DD)')
@click.option('--camera-id', help='摄像头ID过滤')
def coverage(directory, time_range, camera_id):
    """查看视频覆盖情况"""
    if directory is None:
        directory = '.'
    
    db_path = _get_db_path(directory)
    index_manager = VideoIndexManager(db_path)
    
    if time_range:
        start_str, end_str = time_range.split('~')
        start_time = datetime.strptime(start_str.strip(), '%Y-%m-%d')
        end_time = datetime.strptime(end_str.strip(), '%Y-%m-%d')
    else:
        stats = index_manager.get_statistics()
        if stats['earliest_time'] and stats['latest_time']:
            start_time = stats['earliest_time']
            end_time = stats['latest_time']
        else:
            click.echo("❌ 没有时间范围参数且索引中没有时间数据")
            return
    
    report = index_manager.get_video_coverage(start_time, end_time, camera_id)
    
    click.echo("📊 视频覆盖报告:")
    click.echo(f"   时间范围: {start_time} ~ {end_time}")
    click.echo(f"   覆盖率: {report.coverage_ratio:.1%}")
    click.echo(f"   视频数量: {len(report.videos)}")
    click.echo(f"   时间缺口: {len(report.gaps)} 个")
    
    if report.gaps:
        click.echo("\n   缺口详情:")
        for gap_start, gap_end in report.gaps[:10]:
            gap_duration = (gap_end - gap_start).total_seconds()
            click.echo(f"   - {gap_start} ~ {gap_end} ({format_duration(gap_duration)})")


@cli.command()
@click.option('--rule-file', type=click.Path(exists=True), help='规则文件路径')
@click.option('--time-range', help='时间范围 (格式: YYYY-MM-DD~YYYY-MM-DD)')
@click.option('--daily-time', help='每日时间段 (格式: HH:MM:SS~HH:MM:SS)')
@click.option('--interval', default='1m', help='抽帧间隔 (例如: 1m, 5m, 1h)')
@click.option('--output-dir', type=click.Path(), default='./frames', help='输出目录')
@click.option('--format', 'output_format', default='jpg', help='输出格式')
@click.option('--quality', default=95, help='输出质量 (1-100)')
@click.option('--dry-run', is_flag=True, help='试运行，不实际提取')
@click.pass_context
def extract(ctx, rule_file, time_range, daily_time, interval, output_dir, output_format, quality, dry_run):
    """执行抽帧"""
    _check_ffmpeg()
    click.echo("🎯 开始抽帧任务")
    
    if rule_file:
        import yaml
        with open(rule_file, 'r', encoding='utf-8') as f:
            rule_config = yaml.safe_load(f)
        rule = _parse_rule_config(rule_config)
    else:
        rule = _create_rule_from_options(time_range, daily_time, interval, output_dir, output_format, quality)
    
    db_path = _get_db_path('.')
    index_manager = VideoIndexManager(db_path)
    engine = ExtractionEngine(index_manager)
    
    preview = engine.preview_extraction(rule)
    click.echo(f"\n📋 抽帧计划预览:")
    click.echo(f"   总提取点: {preview['total_points']}")
    click.echo(f"   总帧数: {preview['total_frames']}")
    
    if preview.get('date_range'):
        click.echo(f"   日期范围: {preview['date_range'].get('start')} ~ {preview['date_range'].get('end')}")
    if preview.get('time_selection'):
        click.echo(f"   时间段: {preview['time_selection'].get('start')} ~ {preview['time_selection'].get('end')}")
    if preview.get('sampling'):
        click.echo(f"   采样方式: {preview['sampling'].get('method')} (间隔: {preview['sampling'].get('interval')})")
    
    if dry_run:
        click.echo("\n⚠️  试运行模式，不执行实际提取")
        return
    
    if not click.confirm("\n是否继续执行抽帧？"):
        click.echo("❌ 任务已取消")
        return
    
    plan = engine.create_extraction_plan(rule)
    
    if not plan.frame_locations:
        click.echo("❌ 没有找到符合条件的视频帧")
        return
    
    extractor = FrameExtractor(output_dir)
    
    with click.progressbar(length=len(plan.frame_locations), label='提取进度') as bar:
        def progress_callback(current, total):
            bar.update(1)
        
        frames = extractor.extract_batch(
            plan.frame_locations,
            output_format=output_format,
            quality=quality,
            progress_callback=progress_callback
        )
    
    click.echo(f"\n✅ 抽帧完成:")
    click.echo(f"   成功提取: {len(frames)} 帧")
    click.echo(f"   输出目录: {output_dir}")


@cli.command()
@click.argument('input-dir', type=click.Path(exists=True), default='./frames')
@click.option('--output', '-o', default='timelapse.mp4', help='输出文件路径')
@click.option('--fps', default=30, help='输出帧率')
@click.option('--resolution', default='1920x1080', help='输出分辨率')
@click.option('--codec', default='h264', help='视频编码器')
@click.option('--format', 'frame_format', default='jpg', help='输入帧格式')
@click.option('--add-timestamp', is_flag=True, help='添加时间戳水印')
def compose(input_dir, output, fps, resolution, codec, frame_format, add_timestamp):
    """合成视频"""
    _check_ffmpeg()
    click.echo(f"🎬 开始合成视频: {output}")
    
    width, height = map(int, resolution.split('x'))
    
    config = CompositionConfig(
        fps=fps,
        resolution=(width, height),
        codec=codec,
        output_path=output,
        add_timestamp=add_timestamp
    )
    
    composer = VideoComposer(config)
    
    input_path = Path(input_dir)
    frame_count = len(list(input_path.glob(f'*.{frame_format}')))
    
    if frame_count == 0:
        click.echo(f"❌ 在 {input_dir} 中未找到 *.{frame_format} 格式的帧")
        return
    
    with click.progressbar(length=frame_count, label='合成进度') as bar:
        def progress_callback(current, total):
            bar.update(1)
        
        result = composer.compose_from_directory(
            input_dir,
            output,
            pattern=f'*.{frame_format}',
            progress_callback=progress_callback
        )
    
    click.echo(f"\n✅ 合成完成:")
    click.echo(f"   输出文件: {result.output_path}")
    click.echo(f"   总帧数: {result.total_frames}")
    click.echo(f"   时长: {format_duration(result.duration)}")
    click.echo(f"   文件大小: {format_file_size(result.file_size)}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True), required=False)
@click.option('--task', help='任务ID')
@click.option('--all', 'show_all', is_flag=True, help='显示所有任务')
@click.pass_context
def status(ctx, directory, task, show_all):
    """查看状态"""
    if directory is None:
        directory = '.'
    
    db_path = _get_db_path(directory)
    
    if task:
        click.echo(f"📊 任务状态: {task}")
        # TODO: 实现任务状态查询
        click.echo("   (任务系统待实现)")
    elif show_all:
        click.echo("📊 所有任务状态")
        # TODO: 实现所有任务查询
        click.echo("   (任务系统待实现)")
    else:
        # 显示系统状态和索引统计
        index_manager = VideoIndexManager(db_path)
        stats = index_manager.get_statistics()
        click.echo("📊 系统状态:")
        click.echo(f"   数据库: {db_path}")
        click.echo(f"   总视频数: {stats['total_videos']}")
        click.echo(f"   已索引: {stats['indexed_videos']}")
        click.echo(f"   总大小: {format_file_size(stats['total_size'])}")
        if stats['earliest_time']:
            click.echo(f"   最早时间: {stats['earliest_time']}")
        if stats['latest_time']:
            click.echo(f"   最晚时间: {stats['latest_time']}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True), required=False)
@click.option('--show', is_flag=True, help='显示当前配置')
@click.option('--set', 'set_config', multiple=True, help='设置配置 (格式: key=value)')
def config(directory, show, set_config):
    """配置管理"""
    if directory is None:
        directory = '.'
    
    db_path = _get_db_path(directory)
    config_path = Path(db_path).parent / 'project.yaml'
    
    if show:
        if config_path.exists():
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            click.echo("📋 当前配置:")
            for key, value in cfg.items():
                click.echo(f"   {key}: {value}")
        else:
            click.echo("⚠️  未找到配置文件，请先运行 init 命令初始化项目")
    elif set_config:
        import yaml
        cfg = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
        
        for item in set_config:
            if '=' in item:
                key, value = item.split('=', 1)
                cfg[key.strip()] = value.strip()
            else:
                click.echo(f"❌ 无效格式: {item} (应为 key=value)")
                return
        
        ensure_dir(str(Path(db_path).parent))
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        click.echo("✅ 配置已更新")
    else:
        click.echo("⚙️  配置管理")
        click.echo("   使用 --show 查看当前配置")
        click.echo("   使用 --set key=value 设置配置")


def _parse_rule_config(config: dict) -> ExtractionRule:
    """解析规则配置"""
    rule = ExtractionRule(
        name=config.get('name', '未命名规则'),
        description=config.get('description', '')
    )
    
    # 解析日期范围
    date_cfg = config.get('date_range', {})
    if date_cfg:
        start_date = None
        end_date = None
        if 'start_date' in date_cfg:
            start_date = datetime.fromisoformat(date_cfg['start_date']).date()
        if 'end_date' in date_cfg:
            end_date = datetime.fromisoformat(date_cfg['end_date']).date()
        rule.date_range = DateRange(
            start_date=start_date,
            end_date=end_date,
            exclude_dates=[datetime.fromisoformat(d).date() for d in date_cfg.get('exclude_dates', [])]
        )
    
    # 解析时间选择
    time_cfg = config.get('time_selection', {})
    if time_cfg:
        start_time = None
        end_time = None
        if 'start_time' in time_cfg:
            start_time = datetime.strptime(time_cfg['start_time'], '%H:%M:%S').time()
        if 'end_time' in time_cfg:
            end_time = datetime.strptime(time_cfg['end_time'], '%H:%M:%S').time()
        rule.time_selection = TimeSelection(
            type=time_cfg.get('type', 'daily_range'),
            start_time=start_time,
            end_time=end_time,
            timezone=time_cfg.get('timezone', 'Asia/Shanghai')
        )
    
    # 解析采样配置
    sampling_cfg = config.get('sampling', {})
    if sampling_cfg:
        interval_seconds = sampling_cfg.get('interval_seconds', 60)
        from videoframe.models import SamplingMethod
        method = SamplingMethod(sampling_cfg.get('method', 'interval'))
        rule.sampling = Sampling(
            method=method,
            interval=timedelta(seconds=interval_seconds),
            specific_times=[datetime.strptime(t, '%H:%M:%S').time() for t in sampling_cfg.get('specific_times', [])]
        )
    
    # 解析输出配置
    output_cfg = config.get('output', {})
    if output_cfg:
        rule.output = OutputConfig(
            format=output_cfg.get('format', 'jpg'),
            quality=output_cfg.get('quality', 95),
            resolution=output_cfg.get('resolution', 'original'),
            naming=output_cfg.get('naming', '{date}_{time}_{camera_id}_{frame_number}'),
            output_dir=output_cfg.get('output_dir', './output')
        )
    
    return rule


def _create_rule_from_options(
    time_range: str,
    daily_time: str,
    interval: str,
    output_dir: str,
    output_format: str,
    quality: int
) -> ExtractionRule:
    """从命令行选项创建规则"""
    
    if time_range:
        start_str, end_str = time_range.split('~')
        start_date = datetime.strptime(start_str.strip(), '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str.strip(), '%Y-%m-%d').date()
    else:
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()
    
    if daily_time:
        start_str, end_str = daily_time.split('~')
        start_time = datetime.strptime(start_str.strip(), '%H:%M:%S').time()
        end_time = datetime.strptime(end_str.strip(), '%H:%M:%S').time()
    else:
        start_time = time(7, 0, 0)
        end_time = time(17, 0, 0)
    
    interval_delta = _parse_interval(interval)
    
    return ExtractionRule(
        name="CLI规则",
        description="从命令行创建的规则",
        date_range=DateRange(
            start_date=start_date,
            end_date=end_date
        ),
        time_selection=TimeSelection(
            start_time=start_time,
            end_time=end_time
        ),
        sampling=Sampling(
            interval=interval_delta
        ),
        output=OutputConfig(
            format=output_format,
            quality=quality,
            output_dir=output_dir
        )
    )


def _parse_interval(interval_str: str) -> timedelta:
    """解析间隔字符串
    
    支持格式: 30s, 5m, 2h, 1d
    """
    if not interval_str or len(interval_str) < 2:
        raise click.BadParameter(f"无效的间隔格式: '{interval_str}'，应为如 '1m', '5m', '1h' 的格式")
    
    unit = interval_str[-1].lower()
    try:
        value = int(interval_str[:-1])
    except ValueError:
        raise click.BadParameter(f"无效的间隔数值: '{interval_str[:-1]}'")
    
    if unit == 's':
        return timedelta(seconds=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        raise click.BadParameter(f"无效的间隔单位: '{unit}'，应为 s/m/h/d")


if __name__ == '__main__':
    cli()
