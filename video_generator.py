import io
import logging
import math
import os
import random
import subprocess
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from music import SAMPLE_RATE, build_music_track
from voice import synthesize_voice

logger = logging.getLogger(__name__)

VIDEO_WIDTH = 1200
VIDEO_HEIGHT = 630
VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920
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
    # Use a private generator. Seeding the global random module here made every
    # random.choice() elsewhere in the app (e.g. image vs video in
    # publisher.prepare_post) replay the same sequence, so posts always came
    # out as images.
    rng = random.Random(42)
    for _ in range(count):
        px = rng.randint(0, w)
        py = rng.randint(0, h)
        drift = math.sin(frame * 0.05 + px * 0.01) * 3
        px = int(px + drift) % w
        alpha = rng.randint(15, 40)
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


def _remove_tree(path: str) -> None:
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            try:
                os.unlink(os.path.join(root, name))
            except Exception:
                pass
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except Exception:
                pass
    try:
        os.rmdir(path)
    except Exception:
        pass


def _vertical_background(bg: Image.Image) -> Image.Image:
    w, h = VERTICAL_WIDTH, VERTICAL_HEIGHT
    src_ratio = bg.width / bg.height
    dst_ratio = w / h

    if src_ratio > dst_ratio:
        crop_w = int(bg.height * dst_ratio)
        left = (bg.width - crop_w) // 2
        canvas = bg.crop((left, 0, left + crop_w, bg.height)).resize((w, h), Image.LANCZOS)
    else:
        crop_h = int(bg.width / dst_ratio)
        top = (bg.height - crop_h) // 2
        canvas = bg.crop((0, top, bg.width, top + crop_h)).resize((w, h), Image.LANCZOS)

    blurred = bg.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius=28))
    return Image.blend(blurred, canvas, 0.62)


VERTICAL_ZOOM_STEPS = 8


def prepare_vertical_canvas(bg: Image.Image) -> list[Image.Image]:
    w, h = VERTICAL_WIDTH, VERTICAL_HEIGHT

    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    _draw_gradient(ImageDraw.Draw(gradient), w, h, (0, 0, 0, 40), (0, 0, 0, 190))
    graded = Image.alpha_composite(_vertical_background(bg).convert("RGBA"), gradient).convert("RGB")

    levels = [graded]
    for step in range(1, VERTICAL_ZOOM_STEPS):
        scale = 1.0 + (step / (VERTICAL_ZOOM_STEPS - 1)) * 0.05
        new_w, new_h = int(w * scale), int(h * scale)
        zoomed = graded.resize((new_w, new_h), Image.BILINEAR)
        offset_x = (new_w - w) // 2
        offset_y = (new_h - h) // 2
        levels.append(zoomed.crop((offset_x, offset_y, offset_x + w, offset_y + h)))
    return levels


def make_vertical_frame(
    levels: list[Image.Image],
    title: str,
    source: str,
    frame: int,
    total_frames: int,
) -> Image.Image:
    w, h = VERTICAL_WIDTH, VERTICAL_HEIGHT
    progress = frame / max(total_frames - 1, 1)

    index = min(VERTICAL_ZOOM_STEPS - 1, int(progress * VERTICAL_ZOOM_STEPS))
    canvas = levels[index].copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    _draw_particles(draw, w, h, frame, count=44)

    font_title = _get_font(76)
    font_brand = _get_font(44)
    font_small = _get_font(36)

    lines = _wrap_text(title, max_chars=18)[:6]
    line_h = font_title.getbbox("Ay")[3] - font_title.getbbox("Ay")[1]
    gap = 18
    block_h = len(lines) * (line_h + gap) - gap
    y = (h - block_h) // 2

    total_chars = sum(len(line) for line in lines)
    reveal = min(1.0, progress * 1.9)
    chars_to_show = int(total_chars * reveal)
    seen = 0
    for line in lines:
        take = max(0, min(len(line), chars_to_show - seen))
        seen += len(line)
        visible = line[:take]
        if not visible:
            y += line_h + gap
            continue
        line_w = font_title.getbbox(line)[2]
        draw.text(((w - line_w) // 2, y), visible, font=font_title, fill=(255, 255, 255, 235))
        y += line_h + gap

    brand = config.BRAND_NAME or "NEWS"
    if progress > 0.15:
        alpha = int(200 * min(1.0, (progress - 0.15) / 0.25))
        draw.text((60, 90), brand, font=font_brand, fill=(200, 200, 225, alpha))

    if progress > 0.55:
        alpha = int(190 * min(1.0, (progress - 0.55) / 0.25))
        draw.text((60, h - 150), f"Источник: {source}", font=font_small, fill=(180, 205, 255, alpha))

    bar_top = h - 46
    draw.rectangle([60, bar_top, w - 60, bar_top + 8], fill=(255, 255, 255, 45))
    draw.rectangle([60, bar_top, 60 + int((w - 120) * progress), bar_top + 8], fill=(110, 190, 255, 230))

    return canvas


def iter_vertical_frames(
    image_buf: io.BytesIO,
    title: str,
    source: str,
    duration: float,
):
    image_buf.seek(0)
    bg = Image.open(image_buf).convert("RGB")
    canvas = prepare_vertical_canvas(bg)

    total_frames = max(int(FPS * duration), 1)
    for i in range(total_frames):
        yield make_vertical_frame(canvas, title, source, i, total_frames)


def image_to_video_vertical(
    image_buf: io.BytesIO,
    title: str = "",
    source: str = "",
    duration: float = 0,
    description: str = "",
) -> io.BytesIO | None:
    if not _ffmpeg_ready():
        return None

    if duration <= 0:
        duration = config.VIDEO_DURATION

    tmp_dir = tempfile.mkdtemp()
    tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    err_log = os.path.join(tmp_dir, "ffmpeg.log")
    music_path = None
    voice_path = None

    try:
        audio = build_music_track(duration)
        if audio:
            music_path = os.path.join(tmp_dir, "music.wav")
            with open(music_path, "wb") as f:
                f.write(audio)

        speech = synthesize_voice(title, description)
        if speech:
            voice_path = os.path.join(tmp_dir, "voice.mp3")
            with open(voice_path, "wb") as f:
                f.write(speech)

        cmd = [
            _FFMPEG_PATH, "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{VERTICAL_WIDTH}x{VERTICAL_HEIGHT}",
            "-framerate", str(FPS),
            "-i", "pipe:0",
        ]
        music_idx = None
        voice_idx = None
        if music_path:
            music_idx = 1
            cmd += ["-i", music_path]
        if voice_path:
            voice_idx = 2 if music_path else 1
            cmd += ["-i", voice_path]

        cmd += [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", config.VIDEO_PRESET,
            "-crf", "23",
        ]

        filters = []
        if music_path and voice_path:
            common = "aformat=sample_fmts=fltp:sample_rates=%d:channel_layouts=stereo" % SAMPLE_RATE
            bed = max(0.05, config.MUSIC_VOLUME * 0.7)
            filters.append("[%d:a]volume=%.2f[bg]" % (music_idx, bed))
            filters.append("[%d:a]%s,highpass=f=90[sp]" % (voice_idx, common))
            filters.append("[bg][sp]amix=inputs=2:duration=longest:normalize=0[a]")
            fade_in = 0.4
        elif music_path:
            filters.append(
                "[%d:a]volume=%.2f,aformat=sample_fmts=fltp:sample_rates=%d:channel_layouts=stereo[a]"
                % (music_idx, config.MUSIC_VOLUME, SAMPLE_RATE)
            )
            fade_in = 0.6
        elif voice_path:
            filters.append(
                "[%d:a]aformat=sample_fmts=fltp:sample_rates=%d:channel_layouts=stereo[a]"
                % (voice_idx, SAMPLE_RATE)
            )
            fade_in = 0.4
        else:
            fade_in = 0.0

        if filters:
            fade_out = max(0.0, duration - 0.9)
            filters.append(
                "[a]alimiter=limit=0.95,afade=t=in:st=0:d=%.2f,afade=t=out:st=%.2f:d=0.9[aout]"
                % (fade_in, fade_out)
            )
            cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
                    "-c:a", "aac", "-b:a", "128k", "-ar", str(SAMPLE_RATE), "-ac", "2", "-shortest"]
        else:
            cmd += ["-an"]

        cmd += ["-movflags", "+faststart", tmp_video.name]

        frames = 0
        with open(err_log, "wb") as err:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=err,
            )
            try:
                for frame in iter_vertical_frames(image_buf, title, source, duration):
                    proc.stdin.write(frame.tobytes())
                    frames += 1
            except BrokenPipeError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
                code = proc.wait(timeout=300)

        if code != 0:
            with open(err_log, "rb") as f:
                raw = f.read().decode("utf-8", "ignore")
            lines = [ln for ln in raw.splitlines() if "Error" in ln or "Invalid" in ln]
            logger.warning("FFmpeg vertical error (exit %d): %s", code, " | ".join(lines[-6:]) or raw[-400:])
            return None

        tmp_video.close()
        with open(tmp_video.name, "rb") as f:
            video_bytes = f.read()

        result = io.BytesIO(video_bytes)
        result.seek(0)
        logger.info("Vertical video: %d bytes (%.1fs, %d frames, music=%s, voice=%s)",
                    len(video_bytes), duration, frames, bool(music_path), bool(voice_path))
        return result

    except Exception as e:
        logger.warning("Vertical video generation failed: %s", e)
        return None
    finally:
        _remove_tree(tmp_dir)
        try:
            os.unlink(tmp_video.name)
        except Exception:
            pass


def generate_animated_frames(
    image_buf: io.BytesIO,
    title: str,
    source: str,
    duration: float,
) -> list[Image.Image]:
    return list(iter_frames(image_buf, title, source, duration))


def iter_frames(
    image_buf: io.BytesIO,
    title: str,
    source: str,
    duration: float,
):
    image_buf.seek(0)
    bg = Image.open(image_buf).convert("RGB")

    total_frames = max(int(FPS * duration), 1)
    for i in range(total_frames):
        yield make_frame(bg, title, source, i, total_frames)


def _ffmpeg_ready() -> bool:
    if os.path.exists(_FFMPEG_PATH):
        return True
    try:
        subprocess.run([_FFMPEG_PATH, "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        logger.warning("FFmpeg not found, video mode disabled")
        return False


def image_to_video(
    image_buf: io.BytesIO,
    title: str = "",
    source: str = "",
    duration: float = 0,
    description: str = "",
) -> io.BytesIO | None:
    if not _ffmpeg_ready():
        return None

    if duration <= 0:
        duration = config.VIDEO_DURATION

    tmp_dir = tempfile.mkdtemp()
    tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    err_log = os.path.join(tmp_dir, "ffmpeg.log")
    music_path = None
    voice_path = None

    try:
        audio = build_music_track(duration)
        if audio:
            music_path = os.path.join(tmp_dir, "music.wav")
            with open(music_path, "wb") as f:
                f.write(audio)

        speech = synthesize_voice(title, description)
        if speech:
            voice_path = os.path.join(tmp_dir, "voice.mp3")
            with open(voice_path, "wb") as f:
                f.write(speech)

        fade_out = max(0.0, duration - 0.9)
        cmd = [
            _FFMPEG_PATH,
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
            "-framerate", str(FPS),
            "-i", "pipe:0",
        ]
        if music_path:
            music_idx = 1
            cmd += ["-i", music_path]
        else:
            music_idx = None
        if voice_path:
            voice_idx = 2 if music_path else 1
            cmd += ["-i", voice_path]
        else:
            voice_idx = None

        cmd += [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "23",
        ]

        filters = []
        if music_path and voice_path:
            common = "aformat=sample_fmts=fltp:sample_rates=%d:channel_layouts=stereo" % SAMPLE_RATE
            bed = max(0.05, config.MUSIC_VOLUME * 0.7)
            filters.append("[%d:a]volume=%.2f[bg]" % (music_idx, bed))
            filters.append("[%d:a]%s,highpass=f=90[sp]" % (voice_idx, common))
            filters.append("[bg][sp]amix=inputs=2:duration=longest:normalize=0[a]")
            fade_in = 0.4
        elif music_path:
            filters.append(
                "[%d:a]volume=%.2f,aformat=sample_fmts=fltp:sample_rates=%d:channel_layouts=stereo[a]"
                % (music_idx, config.MUSIC_VOLUME, SAMPLE_RATE)
            )
            fade_in = 0.6
        elif voice_path:
            filters.append(
                "[%d:a]aformat=sample_fmts=fltp:sample_rates=%d:channel_layouts=stereo[a]"
                % (voice_idx, SAMPLE_RATE)
            )
            fade_in = 0.4
        else:
            fade_in = 0.0

        if filters:
            filters.append(
                "[a]alimiter=limit=0.95,afade=t=in:st=0:d=%.2f,afade=t=out:st=%.2f:d=0.9[aout]"
                % (fade_in, fade_out)
            )
            cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]"]
        else:
            cmd += ["-an"]

        if music_path or voice_path:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", str(SAMPLE_RATE), "-ac", "2", "-shortest"]

        cmd += ["-movflags", "+faststart", tmp_video.name]

        frames = 0
        with open(err_log, "wb") as err:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=err,
            )
            try:
                for frame in iter_frames(image_buf, title, source, duration):
                    proc.stdin.write(frame.tobytes())
                    frames += 1
            except BrokenPipeError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
                code = proc.wait(timeout=180)

        if code != 0:
            with open(err_log, "rb") as f:
                raw = f.read().decode("utf-8", "ignore")
            lines = [ln for ln in raw.splitlines() if "Error" in ln or "error" in ln or "Invalid" in ln]
            logger.warning("FFmpeg error (exit %d): %s", code, " | ".join(lines[-6:]) or raw[-600:])
            return None

        tmp_video.close()
        with open(tmp_video.name, "rb") as f:
            video_bytes = f.read()

        result = io.BytesIO(video_bytes)
        result.seek(0)
        logger.info(
            "Video generated: %d bytes (%.1fs, %d frames, music=%s, voice=%s)",
            len(video_bytes), duration, frames, bool(music_path), bool(voice_path),
        )
        return result

    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg timeout")
        return None
    except Exception as e:
        logger.warning("Video generation failed: %s", e)
        return None
    finally:
        _remove_tree(tmp_dir)
        try:
            os.unlink(tmp_video.name)
        except Exception:
            pass

