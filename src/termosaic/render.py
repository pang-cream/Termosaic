from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from typing import Literal

from PIL import Image

RenderMode = Literal["half", "full"]
SampleMode = Literal["feature", "average", "nearest"]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class RenderSize:
    width: int
    height: int


@dataclass(frozen=True)
class CropPlan:
    left: int
    top: int
    width: int
    height: int
    background: Color


@dataclass(frozen=True)
class FeaturePoint:
    x: int
    y: int
    mean: Color


@dataclass(frozen=True)
class RenderPlan:
    size: RenderSize
    sample: SampleMode
    scale: float
    crop: CropPlan
    feature_points: tuple[FeaturePoint, ...]


def terminal_limits(mode: RenderMode) -> RenderSize:
    size = shutil.get_terminal_size((120, 40))
    vertical_factor = 2 if mode == "half" else 1
    return RenderSize(size.columns, max(1, size.lines * vertical_factor))


def fit_size(
    source_width: int,
    source_height: int,
    *,
    width: int | None,
    height: int | None,
    mode: RenderMode,
) -> RenderSize:
    if source_width <= 0 or source_height <= 0:
        raise ValueError("source dimensions must be positive")

    vertical_factor = 2 if mode == "half" else 1
    requested_pixel_height = height * vertical_factor if height is not None else None

    if width is not None and requested_pixel_height is not None:
        return RenderSize(max(1, width), max(1, requested_pixel_height))

    if width is not None:
        fitted_height = round(source_height * (width / source_width))
        return RenderSize(max(1, width), max(1, fitted_height))

    if requested_pixel_height is not None:
        fitted_width = round(source_width * (requested_pixel_height / source_height))
        return RenderSize(max(1, fitted_width), max(1, requested_pixel_height))

    limits = terminal_limits(mode)
    scale = min(limits.width / source_width, limits.height / source_height)
    return RenderSize(max(1, round(source_width * scale)), max(1, round(source_height * scale)))


def prepare_image(
    image: Image.Image,
    size: RenderSize,
    background: Color,
    *,
    sample: SampleMode,
    scale: float,
) -> Image.Image:
    image = flatten_image(image, background)
    plan = build_render_plan(image, size, sample=sample, scale=scale)
    return apply_render_plan(image, plan)


def flatten_image(image: Image.Image, background: Color) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    image = image.convert("RGBA")
    canvas = Image.new("RGBA", image.size, (*background, 255))
    return Image.alpha_composite(canvas, image).convert("RGB")


def build_render_plan(image: Image.Image, size: RenderSize, *, sample: SampleMode, scale: float) -> RenderPlan:
    image = image.convert("RGB")
    crop = build_crop_plan(image, size, scale)
    feature_points: tuple[FeaturePoint, ...] = ()
    if sample == "feature":
        framed = apply_crop_plan(image, crop)
        feature_points = build_feature_points(framed, size, crop.background)
    return RenderPlan(size=size, sample=sample, scale=scale, crop=crop, feature_points=feature_points)


def apply_render_plan(image: Image.Image, plan: RenderPlan) -> Image.Image:
    image = image.convert("RGB")
    framed = apply_crop_plan(image, plan.crop)

    if plan.sample == "feature":
        return resize_feature_sample_with_plan(framed, plan)
    if plan.sample == "nearest":
        return framed.resize((plan.size.width, plan.size.height), Image.Resampling.NEAREST)
    return framed.resize((plan.size.width, plan.size.height), Image.Resampling.BOX)


def build_crop_plan(image: Image.Image, size: RenderSize, scale: float) -> CropPlan:
    image = image.convert("RGB")
    source_width, source_height = image.size
    background = estimate_border_color(image)
    left, top, right, bottom = find_subject_box(image, background)

    subject_width = max(1, right - left)
    subject_height = max(1, bottom - top)
    target_aspect = size.width / size.height
    fill = max(0.05, 0.78 * scale)

    crop_width = max(subject_width / fill, subject_height * target_aspect / fill)
    crop_height = crop_width / target_aspect
    if crop_height < subject_height / fill:
        crop_height = subject_height / fill
        crop_width = crop_height * target_aspect

    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    crop_width = max(1, math.ceil(crop_width))
    crop_height = max(1, math.ceil(crop_height))
    crop_left = round(center_x - crop_width / 2)
    crop_top = round(center_y - crop_height / 2)
    return CropPlan(left=crop_left, top=crop_top, width=crop_width, height=crop_height, background=background)


def apply_crop_plan(image: Image.Image, crop: CropPlan) -> Image.Image:
    source_width, source_height = image.size
    crop_right = crop.left + crop.width
    crop_bottom = crop.top + crop.height
    source_left = max(0, crop.left)
    source_top = max(0, crop.top)
    source_right = min(source_width, crop_right)
    source_bottom = min(source_height, crop_bottom)

    output = Image.new("RGB", (crop.width, crop.height), crop.background)
    if source_right > source_left and source_bottom > source_top:
        region = image.crop((source_left, source_top, source_right, source_bottom))
        output.paste(region, (source_left - crop.left, source_top - crop.top))
    return output


def find_subject_box(image: Image.Image, background: Color) -> tuple[int, int, int, int]:
    width, height = image.size
    pixels = image.load()
    step = max(1, max(width, height) // 500)
    threshold = 48
    left = width
    top = height
    right = 0
    bottom = 0

    for y in range(0, height, step):
        for x in range(0, width, step):
            color = pixels[x, y]
            distance = color_distance(color, background)
            saturation = max(color) - min(color)
            if distance > threshold or (distance > threshold // 2 and saturation > 55):
                left = min(left, x)
                top = min(top, y)
                right = max(right, x + step)
                bottom = max(bottom, y + step)

    if left >= right or top >= bottom:
        return (0, 0, width, height)

    margin_x = max(step, round((right - left) * 0.08))
    margin_y = max(step, round((bottom - top) * 0.08))
    left = max(0, left - margin_x)
    top = max(0, top - margin_y)
    right = min(width, right + margin_x)
    bottom = min(height, bottom + margin_y)

    box_width = right - left
    box_height = bottom - top
    if box_width > width * 0.94 and box_height > height * 0.94:
        return (0, 0, width, height)

    return (left, top, right, bottom)


def build_feature_points(image: Image.Image, size: RenderSize, background: Color) -> tuple[FeaturePoint, ...]:
    image = image.convert("RGB")
    source_width, source_height = image.size
    pixels = image.load()
    points: list[FeaturePoint] = []

    for y in range(size.height):
        y0 = (y * source_height) // size.height
        y1 = min(source_height, max(y0 + 1, ((y + 1) * source_height) // size.height))
        for x in range(size.width):
            x0 = (x * source_width) // size.width
            x1 = min(source_width, max(x0 + 1, ((x + 1) * source_width) // size.width))
            points.append(select_feature_point(pixels, x0, y0, x1, y1, background))

    return tuple(points)


def resize_feature_sample_with_plan(image: Image.Image, plan: RenderPlan) -> Image.Image:
    image = image.convert("RGB")
    output = Image.new("RGB", (plan.size.width, plan.size.height))
    output_pixels = output.load()
    pixels = image.load()

    for index, point in enumerate(plan.feature_points):
        x = min(image.width - 1, max(0, point.x))
        y = min(image.height - 1, max(0, point.y))
        output_pixels[index % plan.size.width, index // plan.size.width] = pixels[x, y]

    return output


def select_feature_point(pixels, x0: int, y0: int, x1: int, y1: int, background: Color) -> FeaturePoint:
    points = sample_points(x0, y0, x1, y1)
    colors = [pixels[x, y] for x, y in points]
    mean = channel_mean(colors)
    center_x = (x0 + x1 - 1) / 2
    center_y = (y0 + y1 - 1) / 2
    best_xy = points[0]
    best_score = float("-inf")

    for (x, y), color in zip(points, colors):
        saturation = max(color) - min(color)
        score = (
            1.45 * color_distance(color, background)
            + 0.85 * color_distance(color, mean)
            + 0.35 * saturation
            - 0.02 * (abs(x - center_x) + abs(y - center_y))
        )
        if score > best_score:
            best_score = score
            best_xy = (x, y)

    return FeaturePoint(x=best_xy[0], y=best_xy[1], mean=mean)


def sample_points(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    width = x1 - x0
    height = y1 - y0
    if width <= 4 and height <= 4:
        return [(x, y) for y in range(y0, y1) for x in range(x0, x1)]

    columns = min(4, width)
    rows = min(4, height)
    points: list[tuple[int, int]] = []
    for row in range(rows):
        y = y0 + min(height - 1, (row * height + height // 2) // rows)
        for column in range(columns):
            x = x0 + min(width - 1, (column * width + width // 2) // columns)
            points.append((x, y))
    return points


def estimate_border_color(image: Image.Image) -> Color:
    width, height = image.size
    pixels = image.load()
    step = max(1, (width + height) // 400)
    colors: list[Color] = []

    for x in range(0, width, step):
        colors.append(pixels[x, 0])
        colors.append(pixels[x, height - 1])
    for y in range(0, height, step):
        colors.append(pixels[0, y])
        colors.append(pixels[width - 1, y])

    return channel_median(colors)


def channel_mean(colors: list[Color]) -> Color:
    count = len(colors)
    return (
        sum(color[0] for color in colors) // count,
        sum(color[1] for color in colors) // count,
        sum(color[2] for color in colors) // count,
    )


def channel_median(colors: list[Color]) -> Color:
    middle = len(colors) // 2
    return (
        sorted(color[0] for color in colors)[middle],
        sorted(color[1] for color in colors)[middle],
        sorted(color[2] for color in colors)[middle],
    )


def color_distance(left: Color, right: Color) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1]) + abs(left[2] - right[2])


def render_image(image: Image.Image, *, mode: RenderMode) -> str:
    if mode == "half":
        return render_half_blocks(image)
    return render_full_blocks(image)


def render_half_blocks(image: Image.Image) -> str:
    image = image.convert("RGB")
    width, height = image.size
    pixels = image.load()
    rows: list[str] = []

    for y in range(0, height, 2):
        parts: list[str] = []
        for x in range(width):
            top = pixels[x, y]
            bottom = pixels[x, y + 1] if y + 1 < height else (0, 0, 0)
            parts.append(
                f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m"
                f"\x1b[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m▀"
            )
        parts.append("\x1b[0m")
        rows.append("".join(parts))

    return "\n".join(rows)


def render_full_blocks(image: Image.Image) -> str:
    image = image.convert("RGB")
    width, height = image.size
    pixels = image.load()
    rows: list[str] = []

    for y in range(height):
        parts: list[str] = []
        for x in range(width):
            red, green, blue = pixels[x, y]
            parts.append(f"\x1b[48;2;{red};{green};{blue}m ")
        parts.append("\x1b[0m")
        rows.append("".join(parts))

    return "\n".join(rows)


def parse_color(value: str) -> Color:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise ValueError("color must use #RRGGBB format")
    try:
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
    except ValueError as exc:
        raise ValueError("color must use #RRGGBB format") from exc
    return red, green, blue
