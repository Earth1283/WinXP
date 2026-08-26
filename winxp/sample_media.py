"""Procedurally-synthesized placeholder audio -- no external files needed,
so Media Player has something real to play without the sim ever touching
the host filesystem. Same "no external assets" philosophy as winxp/icons.py.

These are plain sine-tone sequences, not derived from or resembling any
real recording -- generated with stdlib wave/math only.
"""
from __future__ import annotations

import io
import math
import struct
import wave

SAMPLE_RATE = 11025


def _tone(freq, duration, volume=0.5):
    n = int(SAMPLE_RATE * duration)
    if freq <= 0:
        return b"\x00\x00" * n
    return b"".join(
        struct.pack("<h", int(volume * 32767 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)))
        for i in range(n)
    )


def _synthesize(notes) -> bytes:
    """notes: list of (freq_hz, duration_s) tuples; freq 0 = silence."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        for freq, dur in notes:
            w.writeframes(_tone(freq, dur))
    return buf.getvalue()


def chime() -> bytes:
    """Short ascending tone sequence."""
    return _synthesize([(523, 0.18), (659, 0.18), (784, 0.18), (1046, 0.30)])


def sample_tune() -> bytes:
    """A short original tone sequence, nothing derived from any real piece."""
    seq = [523, 587, 659, 523, 659, 784, 659, 523, 494, 523]
    return _synthesize([(f, 0.20) for f in seq])
