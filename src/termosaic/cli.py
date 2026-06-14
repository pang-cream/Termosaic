from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageSequence, UnidentifiedImageError

from .render import (
    RenderMode,
    RenderPlan,
    RenderSize,
    SampleMode,
    apply_render_plan,
    build_render_plan,
    fit_size,
    flatten_image,
    parse_color,
    prepare_image,
    render_image,
)
from .video import open_frame_stream, probe_video, read_exact


@dataclass(frozen=True)
class DisplayFrame:
    text: str
    width: int
    rows: int


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    language = help_language(argv)
    if "-h" in argv or "--help" in argv:
        build_parser(language).print_help()
        raise SystemExit(0)

    args = build_parser(language).parse_args(argv)
    path = Path(args.input).expanduser()
    if not path.exists():
        raise SystemExit(f"file not found: {path}")

    try:
        background = parse_color(args.background)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        if args.kind in {"auto", "image"}:
            show_image(path, args=args, background=background)
        else:
            play_video(path, args=args, background=background)
    except KeyboardInterrupt:
        pass


def help_language(argv: list[str]) -> str:
    if "--zh" in argv:
        return "zh"
    if "--lang=zh" in argv:
        return "zh"
    for index, value in enumerate(argv[:-1]):
        if value == "--lang" and argv[index + 1] == "zh":
            return "zh"
    return "en"


def build_parser(language: str = "en") -> argparse.ArgumentParser:
    if language == "zh":
        return build_zh_parser()
    return build_en_parser()


def build_en_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termosaic",
        description="Render images, GIFs, or videos as true-color terminal mosaics in a centered fullscreen view.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        epilog=(
            "Examples:\n"
            "  uv run termosaic image.png\n"
            "  uv run termosaic animation.gif --speed 0.5 --sample average\n"
            "  uv run termosaic Data/cat.mp4 --kind video --speed 2 --scale 1.3 --blocks-wide 160\n"
            "  uv run termosaic --help --zh\n"
            "\n"
            "Notes:\n"
            "  Static images stay on screen until Ctrl-C; GIFs and videos loop until Ctrl-C.\n"
            "  Output is centered horizontally and vertically in the terminal page.\n"
            "  Default sample=feature: the first frame estimates background and subject framing, then keeps the subject fixed and preserves representative pixels such as edges, eyes, and nose.\n"
            "  sample=average uses the same fixed subject framing with smooth average sampling.\n"
            "  Videos cache rendered terminal frames by default, so later loops play from memory. Use --no-cache for long videos."
        ),
    )
    add_common_arguments(parser, language="en")
    return parser


def build_zh_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termosaic",
        description="把图片、GIF 或视频渲染成终端真彩色马赛克，并全屏居中显示或循环播放。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        epilog=(
            "示例:\n"
            "  uv run termosaic image.png\n"
            "  uv run termosaic animation.gif --speed 0.5 --sample average\n"
            "  uv run termosaic Data/cat.mp4 --kind video --speed 2 --scale 1.3 --blocks-wide 160\n"
            "  uv run termosaic --help --zh\n"
            "\n"
            "说明:\n"
            "  图片会停留到 Ctrl-C；GIF 和视频会循环播放到 Ctrl-C。\n"
            "  输出画面默认在终端页面中水平和垂直居中。\n"
            "  默认 sample=feature：用第一帧估计背景和主体区域，固定居中主体，并优先保留边缘、眼睛、鼻子等代表性像素。\n"
            "  sample=average：使用固定主体取景和平滑平均采样，画面更柔和，但主体边缘可能被背景颜色冲淡。\n"
            "  视频默认缓存第一轮渲染好的终端帧，第二轮开始直接从内存播放；长视频可用 --no-cache 关闭。"
        ),
    )
    add_common_arguments(parser, language="zh")
    return parser


def add_common_arguments(parser: argparse.ArgumentParser, *, language: str) -> None:
    if language == "zh":
        parser.add_argument("-h", "--help", action="store_true", help="显示参数说明并退出")
        parser.add_argument("--zh", action="store_true", help="配合 --help 输出中文帮助")
        parser.add_argument("--lang", choices=["en", "zh"], default="en", help="帮助语言；默认 en，中文用 zh")
        parser.add_argument("input", help="图片、GIF 或视频文件路径")
        parser.add_argument("--kind", choices=["auto", "image", "video"], default="auto", help="输入类型；auto 会先按图片/GIF 尝试，失败后按视频处理")
        parser.add_argument("--mode", choices=["half", "full"], default="half", help="色块模式；half 使用半块字符，纵向分辨率更高")
        parser.add_argument("--sample", choices=["feature", "average", "nearest"], default="feature", help="像素采样方式；feature 保特征，average 平滑平均，nearest 取最近点")
        parser.add_argument("--scale", type=positive_float, default=1.0, help="主体缩放倍数；1 是默认，1.5 更近，0.7 更远")
        parser.add_argument("--width", "--blocks-wide", dest="width", type=positive_int, help="输出宽度，单位是终端列/色块数；不传则自动适配终端")
        parser.add_argument("--height", "--blocks-high", dest="height", type=positive_int, help="输出高度，单位是终端行/色块数；half 模式会采样两倍图像行数")
        parser.add_argument("--background", default="#000000", help="透明图片背景色，格式为 #RRGGBB")
        parser.add_argument("--fps", type=positive_float, help="指定 GIF 或视频播放帧率")
        parser.add_argument("--max-fps", type=positive_float, default=30.0, help="自动播放帧率上限，默认 30")
        parser.add_argument("--speed", type=positive_float, default=1.0, help="播放速度倍数；2 是两倍速，0.5 是半速")
        parser.add_argument("--export-pixels", nargs="?", const="", help="导出渲染后的像素图；不带路径时自动生成文件名")
        parser.add_argument("--no-cache", action="store_true", help="关闭视频渲染帧缓存，适合很长的视频")
        return

    parser.add_argument("-h", "--help", action="store_true", help="show this help message and exit")
    parser.add_argument("--zh", action="store_true", help="show Chinese help when used with --help")
    parser.add_argument("--lang", choices=["en", "zh"], default="en", help="help language; default: en")
    parser.add_argument("input", help="image, GIF, or video file path")
    parser.add_argument("--kind", choices=["auto", "image", "video"], default="auto", help="input type; auto tries image/GIF first, then video")
    parser.add_argument("--mode", choices=["half", "full"], default="half", help="block mode; half uses upper-half blocks for higher vertical resolution")
    parser.add_argument("--sample", choices=["feature", "average", "nearest"], default="feature", help="pixel sampling mode; feature preserves details, average smooths, nearest picks nearest pixels")
    parser.add_argument("--scale", type=positive_float, default=1.0, help="subject scale; 1 is default, 1.5 is closer, 0.7 is farther")
    parser.add_argument("--width", "--blocks-wide", dest="width", type=positive_int, help="output width in terminal columns/blocks; auto-fits when omitted")
    parser.add_argument("--height", "--blocks-high", dest="height", type=positive_int, help="output height in terminal rows/blocks; half mode samples twice as many image rows")
    parser.add_argument("--background", default="#000000", help="background color for transparent images, #RRGGBB")
    parser.add_argument("--fps", type=positive_float, help="GIF or video playback FPS")
    parser.add_argument("--max-fps", type=positive_float, default=30.0, help="auto playback FPS cap; default: 30")
    parser.add_argument("--speed", type=positive_float, default=1.0, help="playback speed multiplier; 2 is double speed, 0.5 is half speed")
    parser.add_argument("--export-pixels", nargs="?", const="", help="export rendered pixel image; optional output path")
    parser.add_argument("--no-cache", action="store_true", help="disable rendered video frame cache; useful for long videos")


def show_image(path: Path, *, args: argparse.Namespace, background: tuple[int, int, int]) -> None:
    try:
        with Image.open(path) as image:
            if getattr(image, "is_animated", False) and getattr(image, "n_frames", 1) > 1:
                frames, durations = prepare_animation(image, path=path, args=args, background=background)
                with terminal_session():
                    play_animation(frames, durations)
            else:
                size = fit_size(image.width, image.height, width=args.width, height=args.height, mode=args.mode)
                frame = prepare_image(image, size, background, sample=args.sample, scale=args.scale)
                export_path = pixel_export_path(path, args.export_pixels, animated=False)
                if export_path is not None:
                    save_pixel_image(frame, export_path)
                with terminal_session():
                    write_frame(frame, mode=args.mode)
                    wait_forever()
    except UnidentifiedImageError as exc:
        if args.kind == "image":
            raise SystemExit(f"not a readable image: {path}") from exc
        play_video(path, args=args, background=background)


def play_video(path: Path, *, args: argparse.Namespace, background: tuple[int, int, int]) -> None:
    if not _has_command("ffmpeg") or not _has_command("ffprobe"):
        raise SystemExit("video playback requires ffmpeg and ffprobe in PATH")

    try:
        info = probe_video(path)
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise SystemExit(f"could not read video metadata: {path}") from exc

    fps = args.fps or min(info.fps or 24.0, args.max_fps)
    frame_interval = 1.0 / (fps * args.speed)
    target_size = fit_size(info.width, info.height, width=args.width, height=args.height, mode=args.mode)
    render_plan: RenderPlan | None = None
    cached_frames: list[DisplayFrame] | None = None if args.no_cache else []
    export_path = pixel_export_path(path, args.export_pixels, animated=True)
    pixel_frame_cache: list[Image.Image] | None = [] if export_path is not None else None
    exported = False

    with terminal_session():
        while True:
            if cached_frames:
                play_cached_frames(cached_frames, frame_interval)
                continue

            frames, render_plan = play_video_once(
                path,
                args=args,
                source_width=info.width,
                source_height=info.height,
                target_size=target_size,
                background=background,
                fps=fps,
                frame_interval=frame_interval,
                render_plan=render_plan,
                frame_cache=cached_frames,
                pixel_frame_cache=None if exported else pixel_frame_cache,
            )
            if frames == 0:
                raise SystemExit(f"ffmpeg produced no frames: {path}")
            if export_path is not None and pixel_frame_cache:
                save_pixel_animation(pixel_frame_cache, [frame_interval] * len(pixel_frame_cache), export_path)
                pixel_frame_cache = None
                exported = True


def prepare_animation(
    image: Image.Image,
    *,
    path: Path,
    args: argparse.Namespace,
    background: tuple[int, int, int],
) -> tuple[list[DisplayFrame], list[float]]:
    size = fit_size(image.width, image.height, width=args.width, height=args.height, mode=args.mode)
    frames: list[DisplayFrame] = []
    pixel_frames: list[Image.Image] = []
    durations: list[float] = []
    render_plan: RenderPlan | None = None

    for frame in ImageSequence.Iterator(image):
        durations.append(frame_duration(frame, args=args))
        flattened = flatten_image(frame.copy(), background)
        if render_plan is None:
            render_plan = build_render_plan(flattened, size, sample=args.sample, scale=args.scale)
        rendered = apply_render_plan(flattened, render_plan)
        pixel_frames.append(rendered.copy())
        frames.append(make_display_frame(rendered, mode=args.mode))

    if not frames:
        raise SystemExit("animated image has no frames")
    export_path = pixel_export_path(path, args.export_pixels, animated=True)
    if export_path is not None:
        save_pixel_animation(pixel_frames, durations, export_path)
    return frames, durations


def frame_duration(frame: Image.Image, *, args: argparse.Namespace) -> float:
    if args.fps is not None:
        return 1.0 / (args.fps * args.speed)

    milliseconds = frame.info.get("duration", 100)
    duration = max(float(milliseconds) / 1000.0, 0.02) / args.speed
    return max(duration, 1.0 / args.max_fps)


def play_animation(frames: list[DisplayFrame], durations: list[float]) -> None:
    while True:
        for frame, duration in zip(frames, durations):
            started_at = time.perf_counter()
            write_display_frame(frame)
            delay = duration - (time.perf_counter() - started_at)
            if delay > 0:
                time.sleep(delay)


def play_cached_frames(frames: list[DisplayFrame], frame_interval: float) -> None:
    for frame in frames:
        started_at = time.perf_counter()
        write_display_frame(frame)
        delay = frame_interval - (time.perf_counter() - started_at)
        if delay > 0:
            time.sleep(delay)


def play_video_once(
    path: Path,
    *,
    args: argparse.Namespace,
    source_width: int,
    source_height: int,
    target_size: RenderSize,
    background: tuple[int, int, int],
    fps: float,
    frame_interval: float,
    render_plan: RenderPlan | None,
    frame_cache: list[DisplayFrame] | None,
    pixel_frame_cache: list[Image.Image] | None,
) -> tuple[int, RenderPlan | None]:
    decode_size = video_decode_size(source_width, source_height, target_size, sample=args.sample)
    process = open_frame_stream(path, width=decode_size.width, height=decode_size.height, fps=fps)
    if process.stdout is None:
        raise SystemExit("ffmpeg did not provide a frame stream")

    frame_size = decode_size.width * decode_size.height * 3
    next_frame_at = time.perf_counter()
    frames = 0
    plan = render_plan

    try:
        while True:
            raw = read_exact(process.stdout, frame_size)
            if len(raw) != frame_size:
                break
            image = Image.frombytes("RGB", (decode_size.width, decode_size.height), raw)
            flattened = flatten_image(image, background)
            if plan is None:
                plan = build_render_plan(flattened, target_size, sample=args.sample, scale=args.scale)
            frame = apply_render_plan(flattened, plan)
            display_frame = make_display_frame(frame, mode=args.mode)
            if frame_cache is not None:
                frame_cache.append(display_frame)
            if pixel_frame_cache is not None:
                pixel_frame_cache.append(frame.copy())
            write_display_frame(display_frame)
            frames += 1

            next_frame_at += frame_interval
            delay = next_frame_at - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_frame_at = time.perf_counter()
    finally:
        process.terminate()

    return frames, plan


def video_decode_size(width: int, height: int, target_size: RenderSize, *, sample: SampleMode) -> RenderSize:
    factor = 1 if sample == "nearest" else 4
    wanted_width = min(width, max(target_size.width, target_size.width * factor))
    wanted_height = min(height, max(target_size.height, target_size.height * factor))
    scale = min(wanted_width / width, wanted_height / height, 1.0)
    return RenderSize(max(1, round(width * scale)), max(1, round(height * scale)))


def write_frame(image: Image.Image, *, mode: RenderMode) -> None:
    write_display_frame(make_display_frame(image, mode=mode))


def make_display_frame(image: Image.Image, *, mode: RenderMode) -> DisplayFrame:
    rows = (image.height + 1) // 2 if mode == "half" else image.height
    return DisplayFrame(text=render_image(image, mode=mode), width=image.width, rows=rows)


def pixel_export_path(input_path: Path, value: str | None, *, animated: bool) -> Path | None:
    if value is None:
        return None

    suffix = ".gif" if animated else ".png"
    if value == "":
        return input_path.with_name(f"{input_path.stem}-termosaic{suffix}")

    path = Path(value).expanduser()
    if path.suffix == "":
        path = path.with_suffix(suffix)
    return path


def save_pixel_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_pixel_animation(frames: list[Image.Image], durations: list[float], path: Path) -> None:
    if not frames:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    milliseconds = [max(20, round(duration * 1000)) for duration in durations]
    indexed_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for frame in frames]
    indexed_frames[0].save(
        path,
        save_all=True,
        append_images=indexed_frames[1:],
        duration=milliseconds,
        loop=0,
        optimize=True,
        disposal=2,
    )


def write_display_frame(frame: DisplayFrame) -> None:
    terminal = shutil.get_terminal_size((frame.width, frame.rows))
    left_padding = max(0, (terminal.columns - frame.width) // 2)
    top_padding = max(0, (terminal.lines - frame.rows) // 2)
    prefix = " " * left_padding

    sys.stdout.write("\x1b[H")
    for _ in range(top_padding):
        sys.stdout.write("\x1b[K\n")
    for index, line in enumerate(frame.text.splitlines()):
        sys.stdout.write(prefix)
        sys.stdout.write(line)
        sys.stdout.write("\x1b[0m\x1b[K")
        if index + 1 < frame.rows:
            sys.stdout.write("\n")
    sys.stdout.flush()


def wait_forever() -> None:
    while True:
        time.sleep(3600)


@contextmanager
def terminal_session() -> Iterator[None]:
    sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
    sys.stdout.flush()
    try:
        yield
    finally:
        cleanup_terminal()


def cleanup_terminal() -> None:
    sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
    sys.stdout.flush()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def _has_command(name: str) -> bool:
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False
