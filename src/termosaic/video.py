from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float | None


def probe_video(path: Path) -> VideoInfo:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise ValueError(f"no video stream found: {path}")

    stream = streams[0]
    fps = _parse_rate(stream.get("avg_frame_rate")) or _parse_rate(stream.get("r_frame_rate"))
    return VideoInfo(width=int(stream["width"]), height=int(stream["height"]), fps=fps)


def open_frame_stream(path: Path, *, width: int, height: int, fps: float) -> subprocess.Popen[bytes]:
    scale = f"scale={width}:{height}:flags=lanczos,fps={fps}"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        scale,
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _parse_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
