# Termosaic

<p align="center">
  <a href="README.md">English</a>
  <span>&nbsp;│&nbsp;</span>
  <strong>中文</strong>
</p>

<table>
  <tr>
    <td align="center"><strong>原视频</strong></td>
    <td align="center"><strong>终端马赛克 GIF</strong></td>
  </tr>
  <tr>
    <td align="center">
      <a href="Data/cat.mp4">
        <img src="assets/cat-source-preview.gif" alt="原视频预览" width="360">
      </a>
    </td>
    <td align="center">
      <img src="assets/cat-terminal-mosaic.gif" alt="在终端中渲染成马赛克色块的小猫视频" width="360">
    </td>
  </tr>
</table>

Termosaic 可以把图片、GIF 和视频直接渲染成终端里的真彩色马赛克色块。程序会进入全屏终端页面，把画面放在终端中间；静态图片会一直停留到 `Ctrl-C`，GIF 和视频会循环播放到 `Ctrl-C`。

默认渲染模式使用上半块字符 `▀`，一个终端字符格可以显示上下两个颜色采样点，因此在同样终端尺寸下能保留更高的竖向分辨率。

## 名称

**Termosaic** 来自 **terminal mosaic**，含义就是“终端马赛克”。这个名字短、直观，也适合作为 GitHub 项目名和命令名。

## 功能

- 在真彩色终端中渲染图片、GIF 和视频。
- 全屏播放，输出画面默认在终端页面中水平和垂直居中。
- 静态图片一直显示直到中断。
- GIF 和视频循环播放直到中断。
- 视频第一轮渲染后会缓存终端文本帧，第二轮开始直接从内存播放。
- GIF 和视频都会使用第一帧固定主体取景，避免主体一会儿放大一会儿缩小。
- 默认 `feature` 采样会优先保留边缘、眼睛、鼻子等代表性像素。
- 需要平滑平均效果时，可以使用 `average` 采样。
- 可配置播放速度、输出尺寸、主体缩放、帧率和缓存行为。
- 默认英文帮助，使用 `--zh` 或 `--lang zh` 查看中文帮助。

## 环境要求

- Python 3.10 或更新版本。
- 使用 [Pillow](https://python-pillow.org/) 处理图片。
- 视频播放需要 `ffmpeg` 和 `ffprobe`。
- 终端需要支持 ANSI true-color。

## 安装

### 推荐：uv

在项目根目录运行：

```bash
uv run termosaic --help
```

`uv run` 会创建或复用本项目的本地环境，并直接运行 CLI，不需要手动安装。

如果当前 shell 没有使用安装了 `uv` 的 Python 环境，可以通过 Conda 运行：

```bash
conda run -n agent uv run termosaic --help
```

### 使用 pip 可编辑安装

如果希望在当前 Python 环境里直接得到 `termosaic` 命令：

```bash
python -m pip install -e .
termosaic --help
```

## 使用方式

渲染静态图片：

```bash
uv run termosaic image.png
```

播放 GIF：

```bash
uv run termosaic animation.gif
```

播放视频：

```bash
uv run termosaic video.mp4 --kind video
```

播放项目中的小猫示例：

```bash
uv run termosaic Data/cat.mp4 --kind video
```

查看帮助：

```bash
uv run termosaic --help
uv run termosaic --help --zh
uv run termosaic --help --lang zh
```

## 常用参数

增加输出宽度：

```bash
uv run termosaic Data/cat.mp4 --kind video --width 160
```

指定输出高度。默认 `half` 模式下，`--height 40` 会采样 80 行图像像素：

```bash
uv run termosaic image.png --width 120 --height 40
```

切换采样方式：

```bash
uv run termosaic Data/cat.mp4 --kind video --sample feature
uv run termosaic Data/cat.mp4 --kind video --sample average
uv run termosaic Data/cat.mp4 --kind video --sample nearest
```

控制主体缩放：

```bash
uv run termosaic Data/cat.mp4 --kind video --scale 1.3
uv run termosaic Data/cat.mp4 --kind video --scale 0.7
```

调整播放速度：

```bash
uv run termosaic Data/cat.mp4 --kind video --speed 2
uv run termosaic animation.gif --speed 0.5
```

长视频如果不想缓存渲染帧，可以关闭缓存：

```bash
uv run termosaic Data/cat.mp4 --kind video --no-cache
```

## 参数说明

| 参数 | 说明 |
| --- | --- |
| `input` | 图片、GIF 或视频文件路径。 |
| `--kind auto\|image\|video` | 输入类型。`auto` 会先尝试图片/GIF，失败后按视频处理。 |
| `--mode half\|full` | 色块模式。`half` 使用上半块字符，竖向分辨率更高。 |
| `--sample feature\|average\|nearest` | 像素采样方式。默认是 `feature`。 |
| `--scale SCALE` | 主体缩放倍数。`1` 是默认，`1.5` 更近，`0.7` 更远。 |
| `--width WIDTH` | 输出宽度，单位是终端列。不传则自动适配终端。 |
| `--height HEIGHT` | 输出高度，单位是终端行。`half` 模式会采样两倍图像行数。 |
| `--background #RRGGBB` | 透明图片背景色。 |
| `--fps FPS` | 指定 GIF 或视频播放帧率。 |
| `--max-fps FPS` | 自动播放帧率上限。默认 `30`。 |
| `--speed SPEED` | 播放速度倍数。`2` 是两倍速，`0.5` 是半速。 |
| `--no-cache` | 关闭视频渲染帧缓存，适合很长的视频。 |
| `--zh` | 配合 `--help` 输出中文帮助。 |
| `--lang en\|zh` | 帮助语言选择。默认 `en`。 |

## 采样方式

`feature` 是默认方式。它会根据第一帧估计背景和主体取景，固定主体位置，然后在每个马赛克块里选择更有代表性的像素。这样能减少平均采样把主体边缘和背景混淡的问题，也更容易保留眼睛、鼻子、轮廓等特征。

`average` 使用固定主体取景和平滑平均采样，画面更柔和，但边缘更容易被背景颜色冲淡。

`nearest` 使用最近点采样，是最简单的采样方式。

## 开发

从源码运行：

```bash
uv run termosaic --help
```

编译检查：

```bash
python -m py_compile src/termosaic/*.py
```

源码包名是 `termosaic`，命令名也是 `termosaic`。
