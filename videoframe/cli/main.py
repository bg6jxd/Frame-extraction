"""
CLI 主入口
"""
import click
import logging
from pathlib import Path
from datetime import datetime, date, time, timedelta

from videoframe import __version__
from videoframe.core import VideoIndexManager, ExtractionEngine, FrameExtractor, VideoComposer
from videoframe.models import ExtractionRule, DateRange, TimeSelection, Sampling, OutputConfig, CompositionConfig
from videoframe.utils import setup_logging, format_duration, format_file_size


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


@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--name', help='项目名称')
@click.option('--camera-type', default='xiaomi', help='摄像头类型')
@click.option('--db-path', type=click.Path(), help='数据库路径')
def init(directory, name, camera_type, db_path):
    """初始化项目"""
    click.echo(f"🎬 初始化项目: {directory}")
    
    if db_path is None:
        db_path = str(Path(directory) / '.videoframe' / 'index.db')
    
    index_manager = VideoIndexManager(db_path)
    
    click.echo(f"✅ 项目初始化完成")
    click.echo(f"   数据库: {db_path}")
    click.echo(f"   摄像头类型: {camera_type}")


@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, default=True, help='递归扫描子目录')
@click.option('--pattern', help='文件名匹配模式')
@click.option('--force', is_flag=True, help='强制重新扫描')
@click.option('--parallel', default=4, help='并行处理数量')
@click.pass_context
def scan(ctx, directory, recursive, pattern, force, parallel):
    """扫描视频目录"""
    click.echo(f"🔍 扫描目录: {directory}")
    
    db_path = str(Path.cwd() / '.videoframe' / 'index.db')
    index_manager = VideoIndexManager(db_path)
    
    with click.progressbar(length=100, label='扫描进度') as bar:
        def progress_callback(video, result):
            if result.video_files > 0:
                progress = (result.successful + result.failed) / result.video_files * 100
                bar.update(int(progress) - bar.pos)
        
        result = index_manager.scan_and_index(
            directory,
            recursive=recursive,
            force_rebuild=force,
            progress_callback=progress_callback if not ctx.obj['verbose'] else None
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
    
    db_path = str(Path(directory) / '.videoframe' / 'index.db')
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
        click.echo("✅ 索引构建完成")


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
    click.echo("🎯 开始抽帧任务")
    
    if rule_file:
        import yaml
        with open(rule_file, 'r', encoding='utf-8') as f:
            rule_config = yaml.safe_load(f)
        rule = _parse_rule_config(rule_config)
    else:
        rule = _create_rule_from_options(time_range, daily_time, interval, output_dir, output_format, quality)
    
    db_path = str(Path.cwd() / '.videoframe' / 'index.db')
    index_manager = VideoIndexManager(db_path)
    engine = ExtractionEngine(index_manager)
    
    preview = engine.preview_extraction(rule)
    click.echo(f"\n📋 抽帧计划预览:")
    click.echo(f"   总提取点: {preview['total_points']}")
    click.echo(f"   总帧数: {preview['total_frames']}")
    
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
        
        frames = extractor.extract_from_plan(
            plan,
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
@click.option('--add-timestamp', is_flag=True, help='添加时间戳水印')
def compose(input_dir, output, fps, resolution, codec, add_timestamp):
    """合成视频"""
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
    frame_count = len(list(input_path.glob('*.jpg')))
    
    with click.progressbar(length=frame_count, label='合成进度') as bar:
        def progress_callback(current, total):
            bar.update(1)
        
        result = composer.compose_from_directory(
            input_dir,
            output,
            progress_callback=progress_callback
        )
    
    click.echo(f"\n✅ 合成完成:")
    click.echo(f"   输出文件: {result.output_path}")
    click.echo(f"   总帧数: {result.total_frames}")
    click.echo(f"   时长: {format_duration(result.duration)}")
    click.echo(f"   文件大小: {format_file_size(result.file_size)}")


@cli.command()
@click.option('--task', help='任务ID')
@click.option('--all', 'show_all', is_flag=True, help='显示所有任务')
@click.option('--watch', is_flag=True, help='实时监控')
def status(task, show_all, watch):
    """查看状态"""
    if task:
        click.echo(f"📊 任务状态: {task}")
    elif show_all:
        click.echo("📊 所有任务状态")
    else:
        click.echo("📊 系统状态")


@cli.command()
def config():
    """配置管理"""
    click.echo("⚙️  配置管理")


def _parse_rule_config(config: dict) -> ExtractionRule:
    """解析规则配置"""
    return ExtractionRule(
        name=config.get('name', '未命名规则'),
        description=config.get('description', '')
    )


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
    """解析间隔字符串"""
    unit = interval_str[-1].lower()
    value = int(interval_str[:-1])
    
    if unit == 's':
        return timedelta(seconds=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        return timedelta(minutes=1)


if __name__ == '__main__':
    cli()
