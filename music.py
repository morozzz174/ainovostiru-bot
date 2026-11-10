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

SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}

DEFAULT_TRANSPOSITIONS = (-4, -2, -1, 0, 0, 1, 1, 2, 3)

STYLES = {
    "calm": {
        "root": 220.00,
        "chords": ((0, 7, 12), (-3, 4, 9), (5, 12, 17), (2, 9, 14)),
        "bpm": 82,
        "pad": 0.30,
        "arp": 0.20,
        "pluck_decay": 5.0,
        "drum_kind": "sparse",
        "bright": (1.0, 0.42, 0.18, 0.08, 0.04),
        "hook": 0.22,
        "scale": "major",
        "swing": 0.0,
        "trans": (-3, -1, 0, 1, 2),
    },
    "upbeat": {
        "root": 261.63,
        "chords": ((0, 4, 7), (5, 9, 12), (7, 11, 14), (2, 5, 9)),
        "bpm": 124,
        "pad": 0.20,
        "arp": 0.26,
        "pluck_decay": 7.0,
        "drum_kind": "four",
        "bright": (1.0, 0.50, 0.30, 0.16, 0.09),
        "hook": 0.50,
        "scale": "major",
        "swing": 0.0,
        "trans": (-3, -1, 0, 0, 1, 1, 2, 2, 4),
    },
    "mystery": {
        "root": 196.00,
        "chords": ((0, 7, 14), (-2, 5, 12), (3, 10, 15), (-4, 3, 10)),
        "bpm": 88,
        "pad": 0.38,
        "arp": 0.18,
        "pluck_decay": 3.4,
        "drum_kind": None,
        "bright": (1.0, 0.26, 0.12, 0.06, 0.03),
        "hook": 0.28,
        "scale": "minor",
        "swing": 0.0,
        "trans": (-5, -4, -2, -1, 0),
    },
    "epic": {
        "root": 174.61,
        "chords": ((0, 7, 12), (-5, 2, 7), (3, 10, 15), (-2, 5, 12)),
        "bpm": 82,
        "pad": 0.40,
        "arp": 0.22,
        "pluck_decay": 4.0,
        "drum_kind": "sparse",
        "bright": (1.0, 0.35, 0.16, 0.09, 0.05),
        "hook": 0.36,
        "scale": "minor",
        "swing": 0.0,
        "trans": (-4, -2, 0, 0, 1),
    },
    "tender": {
        "root": 246.94,
        "chords": ((0, 4, 7), (5, 9, 12), (2, 5, 9), (-3, 4, 9)),
        "bpm": 78,
        "pad": 0.38,
        "arp": 0.16,
        "pluck_decay": 3.2,
        "drum_kind": None,
        "bright": (1.0, 0.35, 0.22, 0.12, 0.06),
        "hook": 0.20,
        "scale": "major",
        "swing": 0.08,
        "trans": (-2, 0, 0, 1, 2),
    },
    "ambient": {
        "root": 146.83,
        "chords": ((0, 7, 16), (-5, 2, 11), (3, 10, 19), (5, 12, 21)),
        "bpm": 58,
        "pad": 0.48,
        "arp": 0.10,
        "pluck_decay": 2.4,
        "drum_kind": None,
        "bright": (1.0, 0.28, 0.12, 0.06, 0.03),
        "hook": 0.10,
        "scale": "major",
        "swing": 0.0,
        "trans": (-3, -1, 0, 2, 4),
    },
    "inspiring": {
        "root": 293.66,
        "chords": ((0, 7, 12), (4, 9, 16), (5, 12, 17), (7, 14, 19)),
        "bpm": 112,
        "pad": 0.32,
        "arp": 0.30,
        "pluck_decay": 6.5,
        "drum_kind": "four",
        "bright": (1.0, 0.50, 0.28, 0.16, 0.10),
        "hook": 0.50,
        "scale": "major",
        "swing": 0.0,
        "trans": (-2, -1, 0, 1, 2, 3, 4),
    },
    "lofi": {
        "root": 196.00,
        "chords": ((0, 4, 7), (-2, 3, 7), (5, 9, 12), (-5, 2, 7)),
        "bpm": 82,
        "pad": 0.30,
        "arp": 0.22,
        "pluck_decay": 5.5,
        "drum_kind": "backbeat",
        "bright": (1.0, 0.30, 0.12, 0.05, 0.02),
        "hook": 0.28,
        "scale": "minor",
        "swing": 0.18,
        "trans": (-3, -1, 0, 0, 2),
    },
    "pulse": {
        "root": 174.61,
        "chords": ((0, 7, 10), (-2, 5, 8), (-4, 3, 7), (-5, 2, 5)),
        "bpm": 122,
        "pad": 0.16,
        "arp": 0.26,
        "pluck_decay": 9.0,
        "drum_kind": "four",
        "bright": (1.0, 0.55, 0.40, 0.20, 0.12),
        "hook": 0.46,
        "scale": "minor",
        "swing": 0.0,
        "trans": (-2, -1, 0, 0, 1, 2),
    },
    "trailer": {
        "root": 130.81,
        "chords": ((0, 7, 12), (-5, 0, 7), (-3, 4, 11), (-7, 0, 5)),
        "bpm": 96,
        "pad": 0.44,
        "arp": 0.28,
        "pluck_decay": 3.4,
        "drum_kind": "sparse",
        "bright": (1.0, 0.60, 0.45, 0.25, 0.15),
        "hook": 0.40,
        "scale": "minor",
        "swing": 0.0,
        "trans": (-4, -2, 0, 0, 1),
    },
    "documentary": {
        "root": 164.81,
        "chords": ((0, 5, 10), (0, 7, 12), (-4, 3, 7), (2, 5, 9)),
        "bpm": 100,
        "pad": 0.36,
        "arp": 0.18,
        "pluck_decay": 4.6,
        "drum_kind": "backbeat",
        "bright": (1.0, 0.45, 0.25, 0.12, 0.07),
        "hook": 0.40,
        "scale": "major",
        "swing": 0.0,
        "trans": (-2, -1, 0, 1, 2, 3),
    },
    "spark": {
        "root": 329.63,
        "chords": ((0, 4, 9), (2, 7, 11), (4, 9, 14), (7, 12, 16)),
        "bpm": 128,
        "pad": 0.14,
        "arp": 0.34,
        "pluck_decay": 10.0,
        "drum_kind": "four",
        "bright": (1.0, 0.55, 0.38, 0.20, 0.12),
        "hook": 0.55,
        "scale": "major",
        "swing": 0.0,
        "trans": (-1, 0, 0, 1, 2, 3),
    },
    "neon": {
        "root": 220.00,
        "chords": ((0, 3, 7), (3, 7, 10), (-2, 2, 7), (-4, 0, 3)),
        "bpm": 100,
        "pad": 0.18,
        "arp": 0.30,
        "pluck_decay": 6.0,
        "drum_kind": "four",
        "bright": (1.0, 0.60, 0.50, 0.30, 0.20),
        "hook": 0.50,
        "scale": "minor",
        "swing": 0.0,
        "trans": (-2, -1, 0, 0, 1, 2),
    },
    "bounce": {
        "root": 233.08,
        "chords": ((0, 4, 7), (-1, 4, 8), (5, 9, 12), (2, 5, 9)),
        "bpm": 118,
        "pad": 0.18,
        "arp": 0.32,
        "pluck_decay": 8.0,
        "drum_kind": "backbeat",
        "bright": (1.0, 0.50, 0.32, 0.18, 0.10),
        "hook": 0.45,
        "scale": "major",
        "swing": 0.08,
        "trans": (-2, -1, 0, 1, 1, 2, 3),
    },
    "floating": {
        "root": 155.56,
        "chords": ((0, 7, 14), (2, 9, 14), (5, 12, 19), (0, 5, 12)),
        "bpm": 92,
        "pad": 0.34,
        "arp": 0.14,
        "pluck_decay": 3.6,
        "drum_kind": None,
        "bright": (1.0, 0.40, 0.22, 0.12, 0.07),
        "hook": 0.30,
        "scale": "major",
        "swing": 0.0,
        "trans": (-2, 0, 1, 2, 3),
    },
    "motion": {
        "root": 130.81,
        "chords": ((0, 7, 12), (9, 14, 17), (5, 12, 17), (2, 9, 14)),
        "bpm": 132,
        "pad": 0.20,
        "arp": 0.32,
        "pluck_decay": 7.5,
        "drum_kind": "four",
        "bright": (1.0, 0.52, 0.36, 0.20, 0.12),
        "hook": 0.42,
        "scale": "minor",
        "swing": 0.0,
        "trans": (-2, 0, 0, 1, 2, 3),
    },
}

THEME_STYLES = {
    "ai": ("upbeat", "spark", "pulse", "neon", "motion", "inspiring", "documentary", "epic"),
    "facts": ("mystery", "documentary", "neon", "motion", "epic", "trailer", "pulse", "upbeat"),
    "beauty": ("tender", "floating", "inspiring", "lofi", "calm", "spark", "bounce"),
}


def _sine(freq: float, n: int) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    return np.sin(2.0 * np.pi * freq * t, dtype=np.float32)


def _adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a = min(n, max(1, int(attack * SAMPLE_RATE)))
    d = min(n - a, max(1, int(decay * SAMPLE_RATE)))
    r = min(n - a - d, max(1, int(release * SAMPLE_RATE)))
    s = max(0, n - a - d - r)
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
        f = freq * (i + 1)
        # A quiet detuned copy of every partial fattens the sound without mud.
        tone += _sine(f, n) * weight
        tone += _sine(f * 1.003, n) * weight * 0.28
    env = _adsr(n, min(0.09, dur * 0.12), dur * 0.18, 0.72, min(0.5, dur * 0.3))
    return tone * env * amp


def _pluck(freq: float, dur: float, amp: float, decay: float) -> np.ndarray:
    n = max(1, int(dur * SAMPLE_RATE))
    tone = _sine(freq, n) * 0.75 + _sine(freq * 2.0, n) * 0.20 + _sine(freq * 4.0, n) * 0.05
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return tone * np.exp(-ramp * decay) * amp


def _lead(freq: float, dur: float, amp: float, decay: float) -> np.ndarray:
    """Hook melody: a brighter multi-partial voice with a fast attack."""
    n = max(1, int(dur * SAMPLE_RATE))
    tone = (
        _sine(freq, n)
        + 0.55 * _sine(freq * 2.0, n)
        + 0.30 * _sine(freq * 3.0, n)
        + 0.15 * _sine(freq * 4.0, n)
        + 0.12 * _sine(freq * 1.006, n)
    )
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    gain = np.exp(-ramp * decay)
    attack = min(n, int(0.008 * SAMPLE_RATE))
    gain[:attack] *= np.linspace(0.0, 1.0, attack, dtype=np.float32)
    return tone * gain * amp


def _kick(dur: float = 0.2, amp: float = 0.55) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    sweep = 120.0 * np.exp(-26.0 * t) + 44.0
    return np.sin(2.0 * np.pi * np.cumsum(sweep) / SAMPLE_RATE) * np.exp(-15.0 * t) * amp


def _hat(rng: np.random.Generator, dur: float = 0.06, amp: float = 0.10, decay: float = 70.0) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = np.diff(noise, prepend=np.float32(0.0))
    ramp = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    return noise * np.exp(-decay * ramp) * amp


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


def _bass(freq: float, dur: float, amp: float) -> np.ndarray:
    n = max(1, int(dur * SAMPLE_RATE))
    tone = _sine(freq, n) + 0.22 * _sine(freq * 2.0, n)
    return tone * _adsr(n, 0.012, dur * 0.3, 0.62, dur * 0.35) * amp


def _riser(rng: np.random.Generator, dur: float = 1.2, amp: float = 0.12) -> np.ndarray:
    n = max(1, int(dur * SAMPLE_RATE))
    noise = rng.standard_normal(n).astype(np.float32)
    for _ in range(4):
        noise = np.diff(noise, prepend=np.float32(0.0))
    env = (np.linspace(0.0, 1.0, n, dtype=np.float32) ** 2.4) * np.exp(-np.linspace(0, 1, n) * 0.6)
    return (noise * env * amp).astype(np.float32)


def _impulse_response(rng: np.random.Generator, seconds: float = 1.2, decay: float = 3.4) -> np.ndarray:
    n = max(16, int(seconds * SAMPLE_RATE))
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    ir = (rng.standard_normal(n).astype(np.float32) * np.exp(-decay * t))
    ir[0] = 0.0
    pre = max(4, int(0.006 * SAMPLE_RATE))
    ir[:pre] *= np.linspace(0.0, 1.0, pre, dtype=np.float32)
    return ir


def _convolve(signal: np.ndarray, ir: np.ndarray) -> np.ndarray:
    if not len(signal) or ir is None or not len(ir):
        return signal
    size = 1 << (len(signal) + len(ir) - 1).bit_length()
    spectrum = np.fft.rfft(signal, size) * np.fft.rfft(ir, size)
    return np.fft.irfft(spectrum, size)[: len(signal)].astype(np.float32)


ARP_PATTERNS = (
    (0, 1, 2, 1, 2, 0, 1, 2),
    (0, 2, 1, 2, 0, 2, 1, 2),
    (0, 1, 2, 2, 1, 0, 2, 1),
    (2, 1, 0, 1, 2, 1, 0, 1),
)


def _degree_index(scale: tuple, semi: float) -> int:
    return min(range(len(scale)), key=lambda i: (abs(scale[i] - semi), i))


def _drum_events(rng: np.random.Generator, kind: str, duration: float, beat: float) -> list[tuple[float, str, float]]:
    """Groove grid: (time in beats, instrument, velocity)."""
    events: list[tuple[float, str, float]] = []
    total = int(duration / beat)
    if kind == "four":
        for b in range(total):
            events.append((b, "kick", 1.0))
            if b % 4 in (1, 3):
                events.append((b, "snare", 0.8))
            events.append((b, "hat", 0.55))
            events.append((b + 0.5, "open", 1.0))
    elif kind == "backbeat":
        for b in range(total):
            if b % 4 in (0, 2):
                events.append((b, "kick", 1.0))
                if b % 4 == 2 and rng.random() < 0.4:
                    events.append((b + 0.75, "kick", 0.55))
            if b % 4 in (1, 3):
                events.append((b, "snare", 1.0))
            events.append((b, "hat", 0.55))
            events.append((b + 0.5, "hat", 1.0))
    elif kind == "sparse":
        for b in range(total):
            if b % 4 == 0:
                events.append((b, "kick", 0.9))
            if b % 4 == 2:
                events.append((b, "snare", 0.6))
            if b % 2 == 1:
                events.append((b + 0.5, "hat", 0.45))
    return events


def synthesize(duration: float, style: str, seed: int) -> np.ndarray:
    cfg = STYLES.get(style, STYLES["calm"])
    rng = np.random.default_rng(seed)
    total = max(1, int(duration * SAMPLE_RATE))
    left = np.zeros(total, dtype=np.float32)
    right = np.zeros(total, dtype=np.float32)

    # Everything (key, tempo, drum/arp dropout) derives from the seed, so a
    # given seed always renders the same clip yet different seeds sound apart.
    trans_pool = cfg.get("trans", DEFAULT_TRANSPOSITIONS)
    transpose = int(trans_pool[int(rng.integers(0, len(trans_pool)))])
    root = cfg["root"] * (2.0 ** (transpose / 12.0))
    bpm = cfg["bpm"] * float(rng.uniform(0.95, 1.08))
    beat = 60.0 / bpm
    bar = beat * 4
    step = beat / 2.0
    swing = cfg.get("swing", 0.0)
    scale = SCALES[cfg.get("scale", "major")]
    chords = cfg["chords"]
    bright = cfg["bright"]

    drum_kind = cfg.get("drum_kind")
    with_drums = drum_kind is not None and bool(rng.random() > 0.12)
    with_arp = bool(rng.random() > 0.12)
    with_bass = bool(rng.random() > 0.10)
    pad_gain = cfg["pad"] * float(rng.uniform(0.8, 1.15))
    arp_gain = cfg["arp"] * float(rng.uniform(0.75, 1.2))
    hook_amp = float(cfg.get("hook", 0.0)) * float(rng.uniform(0.85, 1.15))
    pattern = ARP_PATTERNS[int(rng.integers(0, len(ARP_PATTERNS)))]

    wet_left = np.zeros(total, dtype=np.float32)
    wet_right = np.zeros(total, dtype=np.float32)
    kick_times: list[int] = []

    def mix(
        mono: np.ndarray,
        start: int,
        pan: float,
        spread: float = 0.0,
        send: float = 0.0,
    ) -> None:
        if start >= total or start < 0 or not len(mono):
            return
        end = min(total, start + len(mono))
        part = mono[: end - start]
        left_gain = 1.0 - pan * 0.5
        right_gain = 1.0 + pan * 0.5
        left[start:end] += part * left_gain
        right[start:end] += part * right_gain
        if send > 0.0:
            wet_left[start:end] += part * left_gain * send
            wet_right[start:end] += part * right_gain * send
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

    def shifted(t_beats: float) -> int:
        if swing > 0.0 and (t_beats / step) % 2.0 == 1.0:
            t_beats += swing * step
        return int(t_beats * SAMPLE_RATE)

    # Drums first so the sidechain duck can be applied while pads are mixed.
    if with_drums:
        for t_beats, name, vel in _drum_events(rng, drum_kind, duration, beat):
            at = shifted(t_beats)
            if at >= total:
                break
            if name == "kick":
                mix(_kick(amp=0.52 * vel), at, 0.0)
                kick_times.append(at)
            elif name == "snare":
                mix(_snare(rng, amp=0.20 * vel), at, -0.14)
            elif name == "hat":
                mix(_hat(rng, amp=0.075 * vel), at, 0.4 if int(t_beats) % 2 == 0 else -0.4)
            elif name == "open":
                mix(_hat(rng, dur=0.30, amp=0.12 * vel, decay=18.0), at, -0.3)

    duck = np.ones(total, dtype=np.float32)
    if kick_times:
        span = int(0.24 * SAMPLE_RATE)
        for at in kick_times:
            end = min(total, at + span)
            if end <= at:
                continue
            shape = np.exp(-np.arange(end - at, dtype=np.float32) / SAMPLE_RATE * 16.0)
            duck[at:end] *= 0.55 + 0.45 * shape

    n_bars = max(1, int(math.ceil(duration / bar)))
    for i in range(n_bars):
        start = int(i * bar * SAMPLE_RATE)
        if start >= total:
            break
        chord = chords[i % len(chords)]
        for j, semis in enumerate(chord):
            freq = root * (2.0 ** (semis / 12.0))
            seg = _pad(freq, bar * 1.15, pad_gain / len(chord), bright)
            end = min(total, start + len(seg))
            seg[: end - start] *= duck[start:end]
            pan = -0.55 if j % 2 == 0 else 0.55
            spread = 0.016 if j % 2 == 0 else 0.011
            if j == 2:
                pan *= 0.35
                spread = 0.0
            mix(seg, start, pan, spread, send=0.85)

    if with_bass:
        bass_amp = float(rng.uniform(0.12, 0.22))
        for i in range(n_bars):
            bar_start = int(i * bar * SAMPLE_RATE)
            if bar_start >= total:
                break
            chord = chords[i % len(chords)]
            freq = root * 0.5 * (2.0 ** (chord[0] / 12.0))
            for offset_beats, length, vel in (
                (0.0, 1.5, 1.0),
                (2.0, 1.0, 1.0),
                (2.75, 0.6, 0.8),
            ):
                at = int((i * bar + offset_beats * beat) * SAMPLE_RATE)
                if at >= total:
                    break
                mix(_bass(freq, length * beat, bass_amp * vel), at, 0.0, send=0.12)

    if with_arp:
        for k in range(int(duration / step)):
            t_beats = k * step
            start = shifted(t_beats)
            if start >= total:
                break
            bar_i = int(t_beats / bar) % len(chords)
            chord = chords[bar_i]
            semis = chord[pattern[k % len(pattern)]]
            freq = root * (2.0 ** (semis / 12.0)) * (1.0 + rng.uniform(-0.004, 0.004))
            seg = _pluck(freq, min(step * 1.6, duration), arp_gain, cfg["pluck_decay"])
            mix(seg, start, 0.3 if k % 2 == 0 else -0.3, send=0.4)

    # Hook melody: a random walk over the scale that resolves onto chord tones
    # on every downbeat, so it stays musical instead of the old churning pads.
    if hook_amp > 0.02 and duration > bar * 0.75:
        n_hook = int(duration / step)
        idx: int | None = None
        rest_p = 0.30 if hook_amp < 0.3 else 0.22
        for k in range(n_hook):
            t_beats = k * step
            fs = t_beats % bar
            chord = chords[int(t_beats / bar) % len(chords)]
            if idx is None:
                idx = _degree_index(scale, chord[0]) - 2
            if fs == 0.0:
                chord_semi = chord[0] if rng.random() < 0.6 else chord[-1]
                idx = _degree_index(scale, chord_semi)
            else:
                move = int(rng.integers(-1, 2))
                if rng.random() < 0.12:
                    move *= 2
                idx = max(-3, min(len(scale), idx + move))
            if rng.random() <= rest_p:
                continue
            semi = scale[idx % len(scale)] + 12 * (idx // len(scale))
            freq = root * 2.0 * (2.0 ** (semi / 12.0))
            vel = 1.0 if fs == 0.0 else 0.9
            seg = _lead(freq, min(step * 1.8, duration), hook_amp * vel, decay=4.0)
            mix(seg, shifted(t_beats), 0.18, send=0.35)

    if bool(rng.random() > 0.45) and total > int(3.0 * SAMPLE_RATE):
        rise = _riser(rng, dur=1.2, amp=0.12)
        mix(rise, 0, 0.0)
        stab_at = int(1.25 * SAMPLE_RATE)
        for semis in chords[0]:
            note = _pluck(root * (2.0 ** (semis / 12.0)), 0.9, 0.16, 6.0)
            mix(note, stab_at, rng.uniform(-0.4, 0.4), send=0.5)

    if kick_times and len(wet_left) > 0:
        span = int(0.26 * SAMPLE_RATE)
        for at in kick_times:
            end = min(total, at + span)
            if end <= at:
                continue
            shape = np.exp(-np.arange(end - at, dtype=np.float32) / SAMPLE_RATE * 16.0)
            wet_left[at:end] *= 0.62 + 0.38 * shape
            wet_right[at:end] *= 0.62 + 0.38 * shape

    wet_ir = _impulse_response(rng, seconds=float(rng.uniform(0.9, 1.6)), decay=float(rng.uniform(2.8, 4.2)))
    if np.abs(wet_left).max() > 0 or np.abs(wet_right).max() > 0:
        wet_gain = float(rng.uniform(0.24, 0.4))
        left += _convolve(wet_left, wet_ir) * wet_gain
        right += _convolve(wet_right, wet_ir) * wet_gain

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
        scale_peak = 0.92 / peak
        left *= scale_peak
        right *= scale_peak

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
