# Termosaic

<p align="center">
  <strong>English</strong>
  <span>&nbsp;│&nbsp;</span>
  <a href="README.zh-CN.md">中文</a>
</p>

<table>
  <tr>
    <td align="center"><strong>Source video</strong></td>
    <td align="center"><strong>Terminal mosaic GIF</strong></td>
  </tr>
  <tr>
    <td align="center">
      <a href="Data/cat.mp4">
        <img src="assets/cat-source-preview.gif" alt="Source cat video preview" width="360">
      </a>
    </td>
    <td align="center">
      <img src="assets/cat-terminal-mosaic.gif" alt="A cat video rendered as terminal mosaic blocks" width="360">
    </td>
  </tr>
</table>

Termosaic renders images, GIFs, and videos as true-color mosaic blocks directly in your terminal. It opens a fullscreen terminal view, centers the rendered frame, loops animated media, and keeps static images on screen until you press `Ctrl-C`.

The project is designed for high-resolution terminal playback. By default it uses upper-half block characters (`▀`), so each terminal cell carries two vertical color samples.

## Name

**Termosaic** is short for **terminal mosaic**. It describes the core idea directly: media converted into a mosaic made of terminal color blocks.

## Features

- Render images, GIFs, and videos in a true-color terminal.
- Fullscreen terminal playback with centered output.
- Static images stay visible until interrupted.
- GIFs and videos loop until interrupted.
- Video frames are cached after the first rendered pass, so later loops replay from memory.
- First-frame subject framing keeps animated subjects stable instead of zooming in and out.
- `feature` sampling preserves representative pixels such as edges, eyes, and nose details.
- `average` sampling is available when you want smoother, pooled color blocks.
- Playback speed, output size, subject scale, frame rate, and cache behavior are configurable.
- English help by default, Chinese help via `--zh` or `--lang zh`.

## Requirements

- Python 3.10 or newer.
- [Pillow](https://python-pillow.org/) for image processing.
- `ffmpeg` and `ffprobe` for video playback.
- A terminal with ANSI true-color support.

## Install

### Recommended: uv

From the project root:

```bash
uv run termosaic --help
```

`uv run` creates or reuses the local project environment and runs the CLI without a manual install step.

If your shell is not already using the Python environment where `uv` is installed, you can run through Conda:

```bash
conda run -n agent uv run termosaic --help
```

### Editable install with pip

If you want a direct `termosaic` command inside your active Python environment:

```bash
python -m pip install -e .
termosaic --help
```

## Usage

Render a static image:

```bash
uv run termosaic image.png
```

Play a GIF:

```bash
uv run termosaic animation.gif
```

Play a video:

```bash
uv run termosaic video.mp4 --kind video
```

Use the included cat sample:

```bash
uv run termosaic Data/cat.mp4 --kind video
```

Show help:

```bash
uv run termosaic --help
uv run termosaic --help --zh
uv run termosaic --help --lang zh
```

## Common Options

Increase output width:

```bash
uv run termosaic Data/cat.mp4 --kind video --width 160
```

Control output height. In `half` mode, `--height 40` samples 80 image rows:

```bash
uv run termosaic image.png --width 120 --height 40
```

Change sampling mode:

```bash
uv run termosaic Data/cat.mp4 --kind video --sample feature
uv run termosaic Data/cat.mp4 --kind video --sample average
uv run termosaic Data/cat.mp4 --kind video --sample nearest
```

Control subject scale:

```bash
uv run termosaic Data/cat.mp4 --kind video --scale 1.3
uv run termosaic Data/cat.mp4 --kind video --scale 0.7
```

Change playback speed:

```bash
uv run termosaic Data/cat.mp4 --kind video --speed 2
uv run termosaic animation.gif --speed 0.5
```

Disable video frame caching for long videos:

```bash
uv run termosaic Data/cat.mp4 --kind video --no-cache
```

## Option Reference

| Option | Description |
| --- | --- |
| `input` | Image, GIF, or video file path. |
| `--kind auto\|image\|video` | Input type. `auto` tries image/GIF first, then video. |
| `--mode half\|full` | Block mode. `half` uses upper-half blocks for higher vertical resolution. |
| `--sample feature\|average\|nearest` | Pixel sampling mode. Default: `feature`. |
| `--scale SCALE` | Subject scale. `1` is default, `1.5` is closer, `0.7` is farther. |
| `--width WIDTH` | Output width in terminal columns. Auto-fits when omitted. |
| `--height HEIGHT` | Output height in terminal rows. `half` mode samples twice as many image rows. |
| `--background #RRGGBB` | Background color for transparent images. |
| `--fps FPS` | GIF or video playback FPS. |
| `--max-fps FPS` | Auto playback FPS cap. Default: `30`. |
| `--speed SPEED` | Playback speed multiplier. `2` is double speed, `0.5` is half speed. |
| `--no-cache` | Disable rendered video frame caching. Useful for long videos. |
| `--zh` | Show Chinese help when used with `--help`. |
| `--lang en\|zh` | Help language selector. Default: `en`. |

## Sampling Modes

`feature` is the default. It estimates the background and subject framing from the first frame, keeps the subject fixed, and chooses representative pixels inside each mosaic block. This helps preserve edges and facial/object details that average pooling can wash out.

`average` uses fixed subject framing with smooth average sampling. It is visually softer but can blend subject edges with the background.

`nearest` picks nearest pixels and is the simplest mode.

## Development

Run from source:

```bash
uv run termosaic --help
```

Compile-check the package:

```bash
python -m py_compile src/termosaic/*.py
```

The source package is `termosaic`, and the CLI command is `termosaic`.
