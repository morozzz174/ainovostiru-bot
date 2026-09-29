import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

import config

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+")
_MD_RE = re.compile(r"[*_`~[\]]+")
_WS_RE = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def clean_text(text: str) -> str:
    text = _URL_RE.sub(" ", text or "")
    text = _MD_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text.strip(" ,;:-—…")


def build_speech_text(title: str, description: str = "", max_chars: int = 0) -> str:
    limit = max_chars or config.VOICE_MAX_CHARS
    title = clean_text(title)
    if not title:
        return ""

    desc = clean_text(description)
    if not desc:
        return title[:limit]

    parts = [p for p in _SENTENCE_SPLIT.split(desc) if p]
    first = parts[0] if parts else ""
    room = limit - len(title) - 1
    if len(first) > room:
        first = first[:max(20, room)]
        if " " in first:
            first = first[: first.rfind(" ")]
        first = first.rstrip(" ,;:-—…")
    if len(first) < 20:
        return title[:limit]

    title = title if title[-1] in ".!?…" else title + "."
    return (title + " " + first)[:limit]


async def _synthesize(text: str, voice: str) -> bytes:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=config.VOICE_RATE)
    data = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            data += chunk["data"]
    return data


def synthesize_voice(title: str, description: str = "") -> bytes | None:
    if not config.VOICE_ENABLED:
        logger.info("Voice: disabled by config")
        return None

    text = build_speech_text(title, description)
    if len(text) < 10:
        logger.info("Voice: nothing to read")
        return None

    voices = [config.VOICE_NAME]
    if config.VOICE_FALLBACK_NAME and config.VOICE_FALLBACK_NAME not in voices:
        voices.append(config.VOICE_FALLBACK_NAME)

    retries = max(1, config.VOICE_RETRIES)
    for voice in voices:
        for attempt in range(1, retries + 1):
            try:
                data = _run(_synthesize(text, voice))
                if data:
                    logger.info("Voice: %s, %d KB, %d chars (attempt %d)", voice, len(data) // 1024, len(text), attempt)
                    return data
            except Exception as e:
                logger.warning("Voice %s attempt %d/%d failed: %s", voice, attempt, retries, e)
                time.sleep(1.5)

    logger.warning("Voice: unavailable, video stays music-only")
    return None


def speech_duration(audio: bytes) -> float:
    """Length of the generated narration in seconds.

    edge-tts returns 24 kHz mono MP3, so a constant bitrate lets us size the
    clip from the payload without spawning ffprobe. Used to stop a short
    voiceover from leaving a long silent tail in the video.
    """
    if not audio:
        return 0.0
    bitrate_kbps = 48
    return (len(audio) * 8) / (bitrate_kbps * 1000)


CHARS_PER_SECOND = 13.5


def estimate_speech_seconds(text: str) -> float:
    """Fallback narration length when the TTS payload is unavailable.

    The Russian neural voices read roughly 13.5 characters per second at the
    configured rate, which is close enough to size the clip when no audio came
    back from edge-tts.
    """
    return len(text or "") / CHARS_PER_SECOND

