import struct

import pytest

from detector.audio_pcm import FULL_SCALE, decode_i2s_samples, extract_audio_features
from detector.parser import AudioClueParser
from detector.thresholds import Thresholds


def pack_words(words: list[int]) -> bytes:
    return struct.pack(f"<{len(words)}i", *words)


def test_decode_silence_is_zero():
    raw = pack_words([0, 0, 0, 0])

    samples = decode_i2s_samples(raw)

    assert samples == [0.0, 0.0, 0.0, 0.0]


def test_decode_full_scale_positive_and_negative():
    positive_word = (FULL_SCALE - 1) << 8  # max positive 24-bit value left-justified in the 32-bit slot
    negative_word = -FULL_SCALE << 8  # min negative 24-bit value -- exactly int32 min once shifted
    raw = pack_words([positive_word, negative_word])

    samples = decode_i2s_samples(raw)

    assert samples[0] == pytest.approx(1.0, abs=1e-6)
    assert samples[1] == pytest.approx(-1.0)


def test_decode_rejects_buffer_not_multiple_of_four():
    with pytest.raises(ValueError):
        decode_i2s_samples(b"\x00\x01\x02")


def test_extract_features_silence():
    frame = extract_audio_features([0.0] * 100, timestamp_ms=0, window_ms=100)

    assert frame.peak_amplitude == 0.0
    assert frame.rms_energy == 0.0


def test_extract_features_impulse_peak_exceeds_average_energy():
    samples = [0.02] * 99 + [0.9]  # one sharp transient amid near-silence

    frame = extract_audio_features(samples, timestamp_ms=0, window_ms=100)

    assert frame.peak_amplitude == pytest.approx(0.9)
    assert frame.rms_energy < frame.peak_amplitude


def test_extract_features_rejects_empty_window():
    with pytest.raises(ValueError):
        extract_audio_features([], timestamp_ms=0, window_ms=100)


def test_decoded_impulse_feeds_into_clue_parser_as_impulse():
    positive_word = int(0.9 * FULL_SCALE) << 8
    raw = pack_words([positive_word] * 10)
    samples = decode_i2s_samples(raw)
    frame = extract_audio_features(samples, timestamp_ms=0, window_ms=100)

    clue = AudioClueParser(Thresholds()).parse(frame)

    assert clue.impulse is True
