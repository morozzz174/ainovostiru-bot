import io
import logging
import math
import os
import random
import subprocess
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger(__name__)

VIDEO_WIDTH = 1200
VIDEO_HEIGHT = 630
FPS = 12
FONT_SIZE_TITLE = 64
FONT_SIZE_BRAND = 28
FONT_SIZE_SMALL = 24

_FFMPEG_PATH = "ffmpeg"
try:
    import imageio_ffmpeg as ffmpeg
    _FFMPEG_PATH = ffmpeg.get_ffmpeg_exe()
except Exception:
    pass

_FONT_CACHE = None


def _get_font(size: int):
    global _FONT_CACHE
    if _FONT_CACHE:
        return ImageFont.truetype(_FONT_CACHE, size)

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "arial.ttf",
    ]

    for path in font_candidates:
        if os.path.exists(path):
            _FONT_CACHE = path
            logger.info("Using font: %s", path)
            return ImageFont.truetype(path, size)

    font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    if not os.path.exists(font_path):
        urls = [
            "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans.ttf",
            "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf",
        ]
        for url in urls:
            try:
                import urllib.request
                urllib.request.urlretrieve(url, font_path)
                if os.path.exists(font_path) and os.path.getsize(font_path) > 1000:
                    break
            except Exception:
                continue

    if os.path.exists(font_path) and os.path.getsize(font_path) > 1000:
        _FONT_CACHE = font_path
        logger.info("Using downloaded font: %s", font_path)
        return ImageFont.truetype(font_path, size)

    logger.warning("No suitable font found, trying to install")
    try:
        subprocess.run(
            ["apt-get", "install", "-y", "fonts-dejavu-core"],
            capture_output=True, timeout=30,
        )
        dejavu = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(dejavu):
            _FONT_CACHE = dejavu
            return ImageFont.truetype(dejavu, size)
    except Exception:
        pass

    logger.warning("Fallback to default font")
    return ImageFont.load_default()


def _draw_gradient(draw: ImageDraw, w: int, h: int, top_color, bottom_color):
    for y in range(h):
        parts = 4 if len(top_color) > 3 else 3
        color = tuple(
            int(top_color[i] + (bottom_color[i] - top_color[i]) * y / h)
            for i in range(parts)
        )
        draw.line([(0, y), (w, y)], fill=color)


def _draw_particles(draw: ImageDraw, w: int, h: int, frame: int, count: int = 30):
    random.seed(42)
    for _ in range(count):
        px = random.randint(0, w)
        py = random.randint(0, h)
        drift = math.sin(frame * 0.05 + px * 0.01) * 3
        px = int(px + drift) % w
        alpha = random.randint(15, 40)
        draw.ellipse([px, py, px + 2, py + 2], fill=(255, 255, 255, alpha))


def _wrap_text(text: str, max_chars: int = 30) -> list[str]:
    text = text.replace("\n", " ")
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4]


def make_frame(
    bg: Image.Image,
    title: str,
    source: str,
    frame: int,
    total_frames: int,
) -> Image.Image:
    w, h = VIDEO_WIDTH, VIDEO_HEIGHT
    progress = frame / total_frames

    bg_w, bg_h = bg.size
    scale = max(w / bg_w, h / bg_h) * (1.0 + progress * 0.06)
    new_w = int(bg_w * scale)
    new_h = int(bg_h * scale)
    bg_resized = bg.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - w) // 2
    y = (new_h - h) // 2
    bg_cropped = bg_resized.crop((x, y, x + w, y + h))

    base = bg_cropped.convert("RGBA")

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    _draw_gradient(overlay_draw, w, h, (0, 0, 0, 80), (0, 0, 0, 200))
    _draw_particles(overlay_draw, w, h, frame)

    font_title = _get_font(FONT_SIZE_TITLE)
    font_brand = _get_font(FONT_SIZE_BRAND)
    font_small = _get_font(FONT_SIZE_SMALL)

    lines = _wrap_text(title)
    line_h = font_title.getbbox("Ay")[3] - font_title.getbbox("Ay")[1]
    line_gap = 10
    total_text_h = len(lines) * (line_h + line_gap) - line_gap
    text_y_start = (h - total_text_h) // 2

    reveal_progress = min(1.0, progress * 2.0)
    total_chars = sum(len(l) for l in lines)
    chars_to_show = int(total_chars * reveal_progress)

    char_count = 0
    for line_idx, line in enumerate(lines):
        line_visible_chars = max(0, min(len(line), chars_to_show - char_count))
        visible_line = line[:line_visible_chars]
        char_count += len(line)

        line_bbox = font_title.getbbox(line)
        lw = line_bbox[2] - line_bbox[0]
        lx = (w - lw) // 2
        ly = text_y_start + line_idx * (line_h + line_gap)

        for ci, ch in enumerate(visible_line):
            ch_alpha = int(200 + 55 * (1 - ci / max(len(visible_line), 1)))
            ch_alpha = min(255, max(100, ch_alpha))
            overlay_draw.text((lx, ly), ch, font=font_title, fill=(255, 255, 255, ch_alpha))
            ch_bbox = font_title.getbbox(ch)
            lx += ch_bbox[2] - ch_bbox[0]

    brand_alpha = min(1.0, (progress - 0.7) / 0.2) if progress > 0.7 else 0
    if brand_alpha > 0:
        brand_text = config.BRAND_NAME or "NEWS"
        brand_bbox = font_brand.getbbox(brand_text)
        bx = (w - (brand_bbox[2] - brand_bbox[0])) // 2
        by = h - 45
        alpha = int(brand_alpha * 180)
        overlay_draw.text((bx, by), brand_text, font=font_brand, fill=(200, 200, 220, alpha))

    source_alpha = min(1.0, (progress - 0.6) / 0.2) if progress > 0.6 else 0
    if source_alpha > 0:
        alpha = int(source_alpha * 150)
        overlay_draw.text((30, h - 45), f"Источник: {source}", font=font_small, fill=(180, 200, 255, alpha))

    result = Image.alpha_composite(base, overlay).convert("RGB")
    return result


def generate_animated_frames(
    image_buf: io.BytesIO,
    title: str,
    source: str,
    duration: float,
) -> list[Image.Image]:
    image_buf.seek(0)
    bg = Image.open(image_buf).convert("RGB")

    total_frames = max(int(FPS * duration), 1)
    frames = []
    for i in range(total_frames):
        frame = make_frame(bg, title, source, i, total_frames)
        frames.append(frame)
    return frames


def image_to_video(
    image_buf: io.BytesIO,
    title: str = "",
    source: str = "",
    duration: float = 0,
) -> io.BytesIO | None:
    if not os.path.exists(_FFMPEG_PATH):
        try:
            subprocess.run([_FFMPEG_PATH, "-version"], capture_output=True, timeout=5)
        except Exception:
            logger.warning("FFmpeg not found, video mode disabled")
            return None

    if duration <= 0:
        duration = config.VIDEO_DURATION

    tmp_dir = tempfile.mkdtemp()
    tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")

    try:
        frames = generate_animated_frames(image_buf, title, source, duration)
        if not frames:
            return None

        for i, frame in enumerate(frames):
            frame_path = os.path.join(tmp_dir, f"frame_{i:04d}.png")
            frame.save(frame_path)

        input_pattern = os.path.join(tmp_dir, "frame_%04d.png")
        cmd = [
            _FFMPEG_PATH,
            "-y",
            "-framerate", str(FPS),
            "-i", input_pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "23",
            "-an",
            tmp_video.name,
        ]
        subprocess.run(cmd, capture_output=True, timeout=60, check=True)

        tmp_video.close()
        with open(tmp_video.name, "rb") as f:
            video_bytes = f.read()

        result = io.BytesIO(video_bytes)
        result.seek(0)
        logger.info("Video generated: %d bytes (%.1fs, %d frames)", len(video_bytes), duration, len(frames))
        return result

    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg timeout")
        return None
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode()[:500] if e.stderr else str(e)
        logger.warning("FFmpeg error: %s", err)
        return None
    except Exception as e:
        logger.warning("Video generation failed: %s", e)
        return None
    finally:
        for root, dirs, files in os.walk(tmp_dir, topdown=False):
            for f in files:
                try:
                    os.unlink(os.path.join(root, f))
                except Exception:
                    pass
            try:
                os.rmdir(root)
            except Exception:
                pass
        try:
            os.unlink(tmp_video.name)
        except Exception:
            pass
