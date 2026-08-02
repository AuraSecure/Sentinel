"""Decode raw I2S PCM sample buffers from the INMP441 and reduce them to the
impulse/energy features events.AudioFrame carries -- module 1 (sensor
drivers) of the firmware architecture plan. Per notes/knowledge-base.md,
audio is only ever kept as derived features past this module, never stored
or exposed as raw samples.

INMP441 outputs 24-bit samples inside a 32-bit I2S slot. Exactly how those
24 bits land in the 32-bit word ESP-IDF hands back varies by IDF version and
I2S config -- real-world reports disagree between >>8 and >>11, and even
report ESP-IDF-version-dependent differences for the same wiring. So the
shift is a parameter here, not a hardcoded constant, and needs confirming
against real captured hardware logs once the mic is wired up, per the KB's
"replace synthetic assumptions with real logs" plan.
"""

from __future__ import annotations

import math
import struct

from .events import AudioFrame

DEFAULT_SAMPLE_SHIFT = 8  # assumes 24-bit data left-justified in a 32-bit slot -- unconfirmed against real hardware
FULL_SCALE = 1 << 23  # 24-bit signed full scale


def decode_i2s_samples(raw: bytes, sample_shift: int = DEFAULT_SAMPLE_SHIFT) -> list[float]:
    """raw is a buffer of little-endian int32 samples, one mono sample per
    32-bit word, as handed back by the ESP-IDF I2S driver's read()."""
    if len(raw) % 4 != 0:
        raise ValueError(f"raw I2S buffer length {len(raw)} is not a multiple of 4 bytes")

    word_count = len(raw) // 4
    words = struct.unpack(f"<{word_count}i", raw)
    return [(word >> sample_shift) / FULL_SCALE for word in words]


def extract_audio_features(samples: list[float], timestamp_ms: int, window_ms: int) -> AudioFrame:
    if not samples:
        raise ValueError("cannot extract features from an empty sample window")

    peak_amplitude = max(abs(s) for s in samples)
    rms_energy = math.sqrt(sum(s * s for s in samples) / len(samples))
    return AudioFrame(
        timestamp_ms=timestamp_ms,
        window_ms=window_ms,
        peak_amplitude=min(peak_amplitude, 1.0),
        rms_energy=min(rms_energy, 1.0),
    )
