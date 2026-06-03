import io
import logging
import os
import subprocess
import tempfile

try:
    import imageio_ffmpeg as ffmpeg
    _FFMPEG_PATH = ffmpeg.get_ffmpeg_exe()
    HAS_FFMPEG = os.path.exists(_FFMPEG_PATH)
except Exception:
    _FFMPEG_PATH = "ffmpeg"
    HAS_FFMPEG = False

import config

logger = logging.getLogger(__name__)

VIDEO_WIDTH = 1200
VIDEO_HEIGHT = 630
VIDEO_FPS = 24


def image_to_video(image_buf: io.BytesIO, duration: float = 0) -> io.BytesIO | None:
    if not HAS_FFMPEG:
        logger.warning("FFmpeg not found, video mode disabled")
        return None

    if duration <= 0:
        duration = config.VIDEO_DURATION

    tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")

    try:
        image_buf.seek(0)
        tmp_img.write(image_buf.read())
        tmp_img.close()

        cmd = [
            _FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-i", tmp_img.name,
            "-c:v", "libx264",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=1,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,zoompan=z='if(eq(on,1),1,min(zoom+0.002,1.1))':d={int(duration*VIDEO_FPS)}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}",
            "-an",
            tmp_video.name,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)

        tmp_video.close()
        with open(tmp_video.name, "rb") as f:
            video_bytes = f.read()

        result = io.BytesIO(video_bytes)
        result.seek(0)
        logger.info("Video generated: %d bytes (%.1fs)", len(video_bytes), duration)
        return result

    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg timeout")
        return None
    except subprocess.CalledProcessError as e:
        logger.warning("FFmpeg error: %s", e.stderr.decode()[:200] if e.stderr else str(e))
        return None
    except Exception as e:
        logger.warning("Video generation failed: %s", e)
        return None
    finally:
        for p in [tmp_img.name, tmp_video.name]:
            try:
                os.unlink(p)
            except Exception:
                pass
