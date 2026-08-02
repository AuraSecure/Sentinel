from detector.events import RadarTargetState
from detector.parser import RadarClueParser
from detector.radar_protocol import FOOTER, HEADER, RadarFrameStreamDecoder
from detector.thresholds import Thresholds


def build_frame(
    target_state: int,
    moving_distance: int,
    moving_energy: int,
    stationary_distance: int,
    stationary_energy: int,
    detection_distance: int,
    checksum: int = 0x00,
) -> bytes:
    payload = bytes(
        [
            0x02,
            0xAA,
            target_state,
            moving_distance & 0xFF,
            (moving_distance >> 8) & 0xFF,
            moving_energy,
            stationary_distance & 0xFF,
            (stationary_distance >> 8) & 0xFF,
            stationary_energy,
            detection_distance & 0xFF,
            (detection_distance >> 8) & 0xFF,
            0x55,
            checksum,
        ]
    )
    length = len(payload)
    return HEADER + bytes([length & 0xFF, (length >> 8) & 0xFF]) + payload + FOOTER


def test_decode_single_complete_frame():
    frame = build_frame(
        target_state=0x03,
        moving_distance=120,
        moving_energy=70,
        stationary_distance=118,
        stationary_energy=55,
        detection_distance=118,
    )
    decoder = RadarFrameStreamDecoder()

    frames = decoder.feed(frame, timestamp_ms=1000)

    assert len(frames) == 1
    result = frames[0]
    assert result.target_state == RadarTargetState.BOTH
    assert result.moving_distance_cm == 120
    assert result.moving_energy == 70
    assert result.stationary_distance_cm == 118
    assert result.stationary_energy == 55
    assert result.timestamp_ms == 1000


def test_decoded_frame_feeds_into_clue_parser():
    frame = build_frame(
        target_state=0x01,
        moving_distance=150,
        moving_energy=80,
        stationary_distance=0,
        stationary_energy=0,
        detection_distance=150,
    )
    decoder = RadarFrameStreamDecoder()
    radar_frame = decoder.feed(frame, timestamp_ms=500)[0]

    clue = RadarClueParser(Thresholds()).parse(radar_frame)

    assert clue.presence is True
    assert clue.motion_active is True
    assert clue.energy == 80


def test_frame_split_across_two_feeds():
    frame = build_frame(0x02, 0, 0, 100, 40, 100)
    decoder = RadarFrameStreamDecoder()

    first_half, second_half = frame[:10], frame[10:]
    assert decoder.feed(first_half, timestamp_ms=0) == []
    frames = decoder.feed(second_half, timestamp_ms=100)

    assert len(frames) == 1
    assert frames[0].stationary_energy == 40


def test_ignores_leading_garbage():
    frame = build_frame(0x00, 0, 0, 0, 0, 0)
    decoder = RadarFrameStreamDecoder()

    frames = decoder.feed(b"\x00\x11\x22\xf4\xf3" + frame, timestamp_ms=0)

    assert len(frames) == 1
    assert frames[0].target_state == RadarTargetState.NONE


def test_multiple_frames_in_one_chunk():
    frame_a = build_frame(0x01, 80, 60, 0, 0, 80)
    frame_b = build_frame(0x02, 0, 0, 90, 45, 90)
    decoder = RadarFrameStreamDecoder()

    frames = decoder.feed(frame_a + frame_b, timestamp_ms=0)

    assert len(frames) == 2
    assert frames[0].moving_energy == 60
    assert frames[1].stationary_energy == 45


def test_resyncs_after_corrupt_footer():
    good_payload_length_bytes = bytes([13, 0])
    corrupt = HEADER + good_payload_length_bytes + bytes(13) + b"\x00\x00\x00\x00"  # wrong footer
    frame = build_frame(0x03, 50, 90, 50, 90, 50)
    decoder = RadarFrameStreamDecoder()

    frames = decoder.feed(corrupt + frame, timestamp_ms=0)

    assert len(frames) == 1
    assert frames[0].moving_energy == 90
