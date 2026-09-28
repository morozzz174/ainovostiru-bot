import io
import logging
import math
import os
import random
import wave

import numpy as np

import config

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100

STYLES = {
    "calm": {
        "root": 220.00,
        "chords": ((0, 7, 12), (-3, 4, 9), (5, 12, 17), (2, 9, 14)),
        "bpm": 68,
        "pad": 0.36,
        "arp": 0.20,
        "pluck_decay": 5.0,
        "drums": False,
        "bright": (1.0, 0.28, 0.10),
    },
    "upbeat": {
        "root": 261.63,
        "chords": ((0, 4, 7), (5, 9, 12), (7, 11, 14), (2, 5, 9)),
        "bpm": 112,
        "pad": 0.22,
        "arp": 0.28,
        "pluck_decay": 8.0,
        "drums": True,
        "bright": (1.0, 0.45, 0.22),
    },
    "mystery": {
        "root": 196.00,
        "chords": ((0, 7, 14), (-2, 5, 12), (3, 10, 15), (-4, 3, 10)),
        "bpm": 84,
        "pad": 0.40,
        "arp": 0.16,
        "pluck_decay": 3.2,
        "drums": False,
        "bright": (1.0, 0.18, 0.06),
    },
    "epic": {
        "root": 174.61,
        "chords": ((0, 7, 12), (-5, 2, 7), (3, 10, 15), (-2, 5, 12)),
        "bpm": 76,
        "pad": 0.42,
        "arp": 0.24,
        "pluck_decay": 4.0,
        "drums": True,
        "bright": (1.0, 0.32, 0.14),
    },
}

THEME_STYLES = {
    "ai": ("upbeat", "calm", "epic", "mystery"),
    "facts": ("calm", "mystery", "epic"),
}


def _sine(freq: float, n: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    return np.sin(2.0 * np.pi * freq * t, dtype=np.float32)


def _adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a = min(n, max(1, int(attack * SAMPLE_RATE)))
    d = min(n - a, max(1, int(decay * SAMPLE_RATE)))
    r = min(n - a - d, max(1, int(release * SAMPLE_RATE)))
    s = n - a - d - r
    return np.concatenate([
        np.linspace(0.0, 1.0, a, dtype=np.float32),
        np.linspace(1.0, sustain, d, dtype=np.float32),
        np.full(s, sustain, dtype=np.float32),
        np.linspace(sustain, 0.0, r, dtype=np.float32),
    ])


def _pad(freq: float, dur: float, amp: float, bright) -> np.ndarray:
    n = max(1, int(dur * SAMPLE_RATE))
    tone = np.zeros(n, dtype=np.float32)
    for i, weight in enumerate(bright):
        tone += _sine(freq * (i + 1), n) * weight
    env = _adsr(n, dur * 0.35, dur * 0.2, 0.8, dur * 0.45)
    return tone * env * amp


def _pluck(freq: float, dur: float, amp: float, decay: float) -> np.ndarray:
    n = max(1, int(dur * SAMPLE_RATE))
    tone = _sine(freq, n) * 0.82 + _sine(freq * 2.0, n) * 0.18
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return tone * np.exp(-ramp * decay) * amp


def _kick(dur: float = 0.2, amp: float = 0.55) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    sweep = 120.0 * np.exp(-26.0 * t) + 44.0
    return np.sin(2.0 * np.pi * np.cumsum(sweep) / SAMPLE_RATE) * np.exp(-15.0 * t) * amp


def _hat(rng: np.random.Generator, dur: float = 0.06, amp: float = 0.10) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = np.diff(noise, prepend=np.float32(0.0))
    ramp = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    return noise * np.exp(-70.0 * ramp) * amp


def _snare(rng: np.random.Generator, dur: float = 0.16, amp: float = 0.22) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = np.diff(noise, prepend=np.float32(0.0))
    ramp = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    return (noise * np.exp(-26.0 * ramp) + _sine(190.0, n) * np.exp(-40.0 * ramp) * 0.4) * amp


def _echo(signal: np.ndarray, taps) -> np.ndarray:
    out = signal.copy()
    for delay, gain in taps:
        d = int(delay * SAMPLE_RATE)
        if 0 < d < len(signal):
            out[d:] += signal[:-d] * gain
    return out


def synthesize(duration: float, style: str, seed: int) -> np.ndarray:
    cfg = STYLES.get(style, STYLES["calm"])
    rng = np.random.default_rng(seed)
    total = max(1, int(duration * SAMPLE_RATE))
    left = np.zeros(total, dtype=np.float32)
    right = np.zeros(total, dtype=np.float32)

    beat = 60.0 / cfg["bpm"]
    bar = beat * 4
    chords = cfg["chords"]
    bright = cfg["bright"]

    def mix(mono: np.ndarray, start: int, pan: float, spread: float = 0.0) -> None:
        if start >= total or not len(mono):
            return
        end = min(total, start + len(mono))
        part = mono[: end - start]
        left[start:end] += part * (1.0 - pan * 0.5)
        right[start:end] += part * (1.0 + pan * 0.5)
        if spread > 0.0 and part.any():
            d = int(spread * SAMPLE_RATE)
            tap = start + d
            if tap < total:
                tap_end = min(total, tap + len(part))
                gain = 0.34 if pan > 0 else 0.30
                if pan > 0:
                    right[tap:tap_end] += part[: tap_end - tap] * gain
                else:
                    left[tap:tap_end] += part[: tap_end - tap] * gain

    n_bars = max(1, int(math.ceil(duration / bar)))
    for i in range(n_bars):
        start = int(i * bar * SAMPLE_RATE)
        if start >= total:
            break
        chord = chords[i % len(chords)]
        for j, semis in enumerate(chord):
            freq = cfg["root"] * (2.0 ** (semis / 12.0))
            seg = _pad(freq, bar * 1.15, cfg["pad"] / len(chord), bright)
            pan = -0.55 if j % 2 == 0 else 0.55
            spread = 0.016 if j % 2 == 0 else 0.011
            if j == 2:
                pan *= 0.35
                spread = 0.0
            mix(seg, start, pan, spread)

    step = beat / 2.0
    pattern = (0, 1, 2, 1, 2, 0, 1, 2)
    for k in range(int(duration / step)):
        start = int(k * step * SAMPLE_RATE)
        if start >= total:
            break
        chord = chords[int(k * step / bar) % len(chords)]
        semis = chord[pattern[k % len(pattern)]]
        freq = cfg["root"] * (2.0 ** (semis / 12.0)) * (1.0 + rng.uniform(-0.004, 0.004))
        seg = _pluck(freq, min(step * 1.6, duration), cfg["arp"], cfg["pluck_decay"])
        mix(seg, start, 0.3 if k % 2 == 0 else -0.3)

    if cfg["drums"]:
        for b in range(int(duration / beat)):
            start = int(b * beat * SAMPLE_RATE)
            if start >= total:
                break
            if b % 4 in (0, 2):
                mix(_kick(), start, 0.0)
            if b % 4 in (1, 3):
                mix(_snare(rng), start, -0.12)
        eighth = beat / 2.0
        for h in range(int(duration / eighth)):
            start = int(h * eighth * SAMPLE_RATE)
            if start >= total:
                break
            mix(_hat(rng, amp=0.10 if h % 2 else 0.06), start, 0.4 if h % 2 == 0 else -0.4)

    haas = int(0.018 * SAMPLE_RATE)
    if 0 < haas < total:
        delayed = np.zeros(total, dtype=np.float32)
        delayed[haas:] = right[:-haas]
        right = right * 0.82 + delayed * 0.32

    for signal in (left, right):
        faded = _echo(signal, ((0.13, 0.26), (0.19, 0.18), (0.31, 0.12), (0.47, 0.10)))
        signal[:] = faded

    peak = float(max(np.abs(left).max(), np.abs(right).max()))
    if peak > 0:
        scale = 0.92 / peak
        left *= scale
        right *= scale

    fade = min(int(0.7 * SAMPLE_RATE), total // 2)
    if fade > 0:
        ramp_in = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        ramp_out = np.linspace(1.0, 0.0, fade, dtype=np.float32)
        left[:fade] *= ramp_in
        right[:fade] *= ramp_in
        left[-fade:] *= ramp_out
        right[-fade:] *= ramp_out

    return np.stack([left, right])


def _to_wav(channels: np.ndarray) -> bytes:
    pcm = (np.clip(channels, -1.0, 1.0) * 32767.0).astype(np.int16)
    frames = np.ascontiguousarray(pcm.T) if pcm.ndim == 2 else pcm
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(pcm.shape[0] if pcm.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(frames.tobytes())
    return buf.getvalue()


def pick_style() -> str:
    if config.MUSIC_STYLE in STYLES:
        return config.MUSIC_STYLE
    options = THEME_STYLES.get(config.THEME, tuple(STYLES))
    return random.choice(options)


def build_music_track(duration: float, seed: int | None = None) -> bytes | None:
    if not config.MUSIC_ENABLED:
        logger.info("Music: disabled by config")
        return None

    if config.MUSIC_FILE:
        if not os.path.exists(config.MUSIC_FILE):
            logger.warning("MUSIC_FILE not found: %s", config.MUSIC_FILE)
        else:
            with open(config.MUSIC_FILE, "rb") as f:
                logger.info("Music: using file %s", config.MUSIC_FILE)
                return f.read()

    if seed is None:
        if config.MUSIC_SEED:
            seed = int(config.MUSIC_SEED)
        else:
            seed = random.randint(0, 2 ** 31 - 1)

    style = pick_style()
    audio = _to_wav(synthesize(duration, style, seed))
    logger.info("Music: %s style, seed %d, %.1fs, %d KB", style, seed, duration, len(audio) // 1024)
    return audio
