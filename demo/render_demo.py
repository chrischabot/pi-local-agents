#!/usr/bin/env python3
"""Render the captured Pi streams into a polished terminal-style MP4."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "demo" / "captures"
OUTPUT = ROOT / "demo" / "pi-agents-intro.mp4"
WIDTH, HEIGHT, FPS = 1920, 1080, 30
FONT_REGULAR = "/System/Library/Fonts/SFNSMono.ttf"
FONT_ITALIC = "/System/Library/Fonts/SFNSMonoItalic.ttf"

BG = "#07100F"
PANEL = "#0C1715"
PANEL_2 = "#101F1C"
BORDER = "#21312D"
TEXT = "#E8F0ED"
MUTED = "#7E918B"
DIM = "#51645E"
GREEN = "#7FE7C4"


def font(size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_ITALIC if italic else FONT_REGULAR, size)


F_16 = font(16)
F_18 = font(18)
F_20 = font(20)
F_22 = font(22)
F_24 = font(24)
F_28 = font(28)
F_34 = font(34)
F_46 = font(46)
F_72 = font(72)
F_112 = font(112)


def ease_out(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def lerp(a: float, b: float, amount: float) -> float:
    return a + (b - a) * amount


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def mix(first: str, second: str, amount: float) -> tuple[int, int, int]:
    a, b = hex_rgb(first), hex_rgb(second)
    return tuple(round(lerp(a[index], b[index], amount)) for index in range(3))


def wrap_text(draw: ImageDraw.ImageDraw, value: str, face, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in value.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = words.pop(0)
        for word in words:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=face)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def strip_fence(value: str) -> str:
    lines = value.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines.pop(0)
    if lines and lines[-1].strip() == "```":
        lines.pop()
    return "\n".join(lines)


@dataclass
class Scene:
    capture: dict
    start: float
    command_end: float
    startup_end: float
    prompt_end: float
    stream_end: float
    hold_end: float
    end: float

    @property
    def meta(self) -> dict:
        return self.capture["scene"]


def build_timeline() -> tuple[list[Scene], float]:
    cursor = 3.2
    scenes: list[Scene] = []
    for path in [
        CAPTURE_DIR / "qwen.json",
        CAPTURE_DIR / "gemma.json",
        CAPTURE_DIR / "glimmer.json",
        CAPTURE_DIR / "deepseek-flash.json",
    ]:
        capture = json.loads(path.read_text())
        token_events = capture["token_events"]
        stream_duration = max(0.35, token_events[-1]["t"] - token_events[0]["t"])
        start = cursor
        command_end = start + 0.8
        startup_end = command_end + 1.2
        prompt_end = startup_end + 1.45
        stream_end = prompt_end + stream_duration
        hold_end = stream_end + (3.2 if capture["scene"]["slug"] == "deepseek-flash" else 1.9)
        end = hold_end + 0.75
        scenes.append(
            Scene(
                capture,
                start,
                command_end,
                startup_end,
                prompt_end,
                stream_end,
                hold_end,
                end,
            )
        )
        cursor = end + 0.45
    return scenes, cursor + 1.8


def draw_background(draw: ImageDraw.ImageDraw, t: float) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=BG)
    for index in range(7):
        radius = 260 + index * 120
        alpha = 0.06 * (1 - index / 8)
        color = mix(BG, "#2C8A72", alpha)
        x = WIDTH - 150 + math.sin(t * 0.14) * 18
        y = -50
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=2)
    draw.line((0, HEIGHT - 82, WIDTH, HEIGHT - 82), fill="#14231F", width=1)


def draw_terminal_chrome(draw: ImageDraw.ImageDraw, accent: str = GREEN) -> None:
    x, y, w, h = 120, 72, 1680, 894
    draw.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=PANEL, outline=BORDER, width=2)
    draw.rounded_rectangle((x + 1, y + 1, x + w - 1, y + 68), radius=23, fill=PANEL_2)
    draw.rectangle((x + 1, y + 43, x + w - 1, y + 69), fill=PANEL_2)
    for offset, color in enumerate(("#FF6B67", "#F5C35B", "#5DD48A")):
        cx = x + 34 + offset * 28
        draw.ellipse((cx, y + 26, cx + 13, y + 39), fill=color)
    draw.text((x + 112, y + 23), "pi-agents  —  ~/pi-agents", fill=MUTED, font=F_18)
    draw.rounded_rectangle((x + w - 138, y + 18, x + w - 28, y + 48), radius=15, fill="#162824")
    draw.text((x + w - 110, y + 24), "π  pi", fill=accent, font=F_16)


def draw_footer(draw: ImageDraw.ImageDraw) -> None:
    draw.text((120, 1004), "GENUINE MODEL OUTPUT", fill=MUTED, font=F_16)
    draw.ellipse((358, 1011, 366, 1019), fill=GREEN)
    draw.text((382, 1004), "TOKEN STREAM 1×", fill=TEXT, font=F_16)
    right = "ONLY STARTUP GAPS ARE COMPRESSED"
    width = draw.textbbox((0, 0), right, font=F_16)[2]
    draw.text((1800 - width, 1004), right, fill=MUTED, font=F_16)


def draw_intro(draw: ImageDraw.ImageDraw, t: float) -> None:
    draw_terminal_chrome(draw)
    progress = ease_out((t - 0.25) / 0.85)
    x = int(220 + (1 - progress) * 55)
    draw.text((x, 238), "PI", fill=MUTED, font=F_112)
    pi_width = draw.textbbox((x, 238), "PI", font=F_112)[2] - x
    draw.text((x + pi_width + 30, 238), "AGENTS", fill=GREEN, font=F_112)
    draw.text((x, 390), "One command. The right model. A lightweight harness.", fill=TEXT, font=F_34)
    draw.text((x, 458), "Local when privacy matters.", fill=MUTED, font=F_24)
    draw.text((x, 502), "Hosted when the hardest work needs more reach.", fill=MUTED, font=F_24)
    labels = [("qwen", "LOCAL"), ("gemma", "LOCAL"), ("glimmer", "LOCAL"), ("deepseek-flash", "API")]
    badge_x = x
    for command, kind in labels:
        command_w = draw.textbbox((0, 0), command, font=F_20)[2]
        kind_w = draw.textbbox((0, 0), kind, font=F_16)[2]
        badge_w = command_w + kind_w + 62
        draw.rounded_rectangle((badge_x, 630, badge_x + badge_w, 692), radius=14, fill="#12221F", outline="#263B35")
        draw.text((badge_x + 18, 644), command, fill=TEXT, font=F_20)
        draw.text((badge_x + badge_w - kind_w - 16, 648), kind, fill=GREEN, font=F_16)
        badge_x += badge_w + 18
    draw.text((x, 798), "$ qwen", fill=GREEN, font=F_28)
    if int(t * 2) % 2 == 0:
        cursor_x = x + draw.textbbox((0, 0), "$ qwen", font=F_28)[2] + 8
        draw.rectangle((cursor_x, 803, cursor_x + 14, 833), fill=GREEN)


def draw_status_bar(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    accent = scene.meta["accent"]
    x, y, w = 155, 888, 1610
    draw.rounded_rectangle((x, y, x + w, y + 45), radius=9, fill="#12221F")
    draw.ellipse((x + 18, y + 17, x + 28, y + 27), fill=accent)
    draw.text((x + 42, y + 12), scene.meta["provider"], fill=accent, font=F_16)
    model_text = scene.meta["model"]
    model_width = draw.textbbox((0, 0), model_text, font=F_16)[2]
    draw.text((x + w - model_width - 20, y + 12), model_text, fill=TEXT, font=F_16)


def draw_scene(draw: ImageDraw.ImageDraw, scene: Scene, t: float) -> None:
    local_t = t - scene.start
    accent = scene.meta["accent"]
    draw_terminal_chrome(draw, accent)
    content_x = 158
    content_y = 172
    available_w = 1604

    # Shell command, typed at a human pace.
    command = scene.meta["command"]
    command_progress = max(0.0, min(1.0, local_t / 0.68))
    visible_count = math.floor(len(command) * command_progress + 0.0001)
    visible_command = command[:visible_count]
    draw.text((content_x, content_y), "$", fill=accent, font=F_24)
    draw.text((content_x + 34, content_y), visible_command, fill=TEXT, font=F_24)
    if t < scene.command_end and int(t * 5) % 2 == 0:
        cursor_x = content_x + 34 + draw.textbbox((0, 0), visible_command, font=F_24)[2] + 5
        draw.rectangle((cursor_x, content_y + 3, cursor_x + 12, content_y + 29), fill=accent)

    if t < scene.command_end:
        draw_status_bar(draw, scene)
        return

    # The compressed startup section remains explicit about the real wait.
    if t < scene.startup_end:
        phase = (t - scene.command_end) / (scene.startup_end - scene.command_end)
        spinner = "◐◓◑◒"[int(phase * 12) % 4]
        hosted = scene.meta["provider"].startswith("HOSTED")
        status = "connecting to hosted model" if hosted else "starting local model on Metal"
        draw.text((content_x, 252), spinner, fill=accent, font=F_28)
        draw.text((content_x + 46, 254), status, fill=MUTED, font=F_20)
        real_wait = float(scene.capture["first_token"])
        label = f"real first token: {real_wait:.1f}s  ·  compressed here to 1.2s"
        draw.rounded_rectangle((content_x, 312, content_x + 548, 358), radius=10, fill="#142723")
        draw.text((content_x + 16, 324), label, fill=accent, font=F_16)
        draw_status_bar(draw, scene)
        return

    # Pi prompt panel.
    draw.text((content_x, 248), "YOU", fill=accent, font=F_16)
    draw.rounded_rectangle((content_x, 278, content_x + available_w, 380), radius=14, fill="#12211E", outline="#233A34")
    prompt_phase = max(0.0, min(1.0, (t - scene.startup_end) / 1.2))
    prompt = scene.meta["prompt_display"]
    prompt_chars = math.floor(len(prompt) * ease_out(prompt_phase))
    prompt_visible = prompt[:prompt_chars]
    prompt_lines = wrap_text(draw, prompt_visible, F_20, available_w - 48)
    for index, line in enumerate(prompt_lines[:2]):
        draw.text((content_x + 22, 296 + index * 31), line, fill=TEXT, font=F_20)

    if t < scene.prompt_end:
        draw_status_bar(draw, scene)
        return

    draw.text((content_x, 430), scene.meta["model"].upper(), fill=MUTED, font=F_16)
    elapsed_stream = max(0.0, t - scene.prompt_end)
    first_token = float(scene.capture["token_events"][0]["t"])
    output = "".join(
        str(event["delta"])
        for event in scene.capture["token_events"]
        if float(event["t"]) - first_token <= elapsed_stream + 0.0001
    )
    output = strip_fence(output)
    is_ascii = scene.meta["slug"] == "deepseek-flash"
    output_face = F_22 if is_ascii else F_24
    line_height = 32 if is_ascii else 38
    output_lines = output.splitlines() if is_ascii else wrap_text(draw, output, output_face, available_w - 28)
    y = 466
    for index, line in enumerate(output_lines[:10]):
        color = accent if is_ascii and index < max(0, len(output_lines) - 1) else TEXT
        draw.text((content_x, y + index * line_height), line, fill=color, font=output_face)
    if t < scene.stream_end and int(t * 4) % 2 == 0:
        if output_lines:
            last_line = output_lines[-1]
            cursor_x = content_x + draw.textbbox((0, 0), last_line, font=output_face)[2] + 6
            cursor_y = y + (len(output_lines) - 1) * line_height + 4
        else:
            cursor_x, cursor_y = content_x, y + 4
        draw.rectangle((cursor_x, cursor_y, cursor_x + 11, cursor_y + 24), fill=accent)

    if t >= scene.hold_end:
        progress = ease_out((t - scene.hold_end) / (scene.end - scene.hold_end))
        exit_text = "^D   session closed"
        draw.text((content_x, 828), exit_text, fill=mix(DIM, TEXT, progress), font=F_18)
    draw_status_bar(draw, scene)


def render() -> None:
    scenes, duration = build_timeline()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = subprocess.Popen(
        [
            "/opt/homebrew/bin/ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{WIDTH}x{HEIGHT}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ],
        stdin=subprocess.PIPE,
    )
    assert ffmpeg.stdin is not None
    total_frames = math.ceil(duration * FPS)
    for frame_number in range(total_frames):
        t = frame_number / FPS
        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(image)
        draw_background(draw, t)
        active = next((scene for scene in scenes if scene.start <= t <= scene.end), None)
        if t < scenes[0].start:
            draw_intro(draw, t)
        elif active:
            draw_scene(draw, active, t)
        else:
            previous = max((scene for scene in scenes if scene.end < t), key=lambda item: item.end, default=None)
            following = next((scene for scene in scenes if scene.start > t), None)
            if previous and following:
                draw_scene(draw, previous if t - previous.end < following.start - t else following, t)
            else:
                draw_terminal_chrome(draw)
                draw.text((225, 365), "pi-agents", fill=GREEN, font=F_72)
                draw.text((225, 468), "Pick a model. Start shipping.", fill=TEXT, font=F_34)
        draw_footer(draw)
        ffmpeg.stdin.write(image.tobytes())
        if frame_number % (FPS * 5) == 0:
            print(f"Rendered {frame_number / FPS:.0f}s / {duration:.0f}s", flush=True)
    ffmpeg.stdin.close()
    return_code = ffmpeg.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg exited with {return_code}")
    print(f"Wrote {OUTPUT} ({duration:.1f}s)")


if __name__ == "__main__":
    render()
