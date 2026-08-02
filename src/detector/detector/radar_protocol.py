"""Byte-level decoder for the real LD2410C UART data-report protocol --
module 1 (sensor drivers) of the firmware architecture plan.

Frame shape (confirmed against the official HLK-LD2410C serial protocol docs
and cross-checked against open-source LD2410 UART libraries):

    [F4 F3 F2 F1] [length: u16 LE] [payload...] [F8 F7 F6 F5]

Payload (first 11 bytes, present in both basic and engineering report modes):
    byte 0     report type   (0x01 = engineering, 0x02 = basic)
    byte 1     head marker   (0xAA)
    byte 2     target state  (0x00 none, 0x01 moving, 0x02 stationary, 0x03 both)
    bytes 3-4  moving target distance, cm   (u16 LE)
    byte 5     moving target energy         (0-100)
    bytes 6-7  stationary target distance, cm (u16 LE)
    byte 8     stationary target energy     (0-100)
    bytes 9-10 detection distance, cm       (u16 LE)

Engineering mode appends per-gate energy bytes after that; not modeled here
since events.RadarFrame doesn't carry per-gate detail. The payload always
ends with a tail marker (0x55) and a checksum byte -- the checksum algorithm
wasn't confirmed in the sources checked, so it's only checked for presence,
not validated. Separate command/ACK frames (header FD FC FB FA) exist for
configuration; this decoder ignores anything that isn't a data-report frame.

TODO once hardware exists: confirm the checksum algorithm and engineering
gate layout against real captured frames, per the KB's "replace synthetic
assumptions with real logs" plan.
"""

from __future__ import annotations

from .events import RadarFrame, RadarTargetState

HEADER = b"\xf4\xf3\xf2\xf1"
FOOTER = b"\xf8\xf7\xf6\xf5"
HEAD_MARKER = 0xAA
TAIL_MARKER = 0x55
MAX_PLAUSIBLE_LENGTH = 128  # real frames top out well under this; guards against a corrupt length field stalling forever

_TARGET_STATE_MAP = {
    0x00: RadarTargetState.NONE,
    0x01: RadarTargetState.MOVING,
    0x02: RadarTargetState.STATIONARY,
    0x03: RadarTargetState.BOTH,
}


class InvalidRadarFrame(ValueError):
    pass


def decode_radar_payload(payload: bytes, timestamp_ms: int) -> RadarFrame:
    """Decode the fixed-layout portion of an LD2410C data-report payload
    (the bytes between the length field and the footer)."""
    if len(payload) < 11:
        raise InvalidRadarFrame(f"payload too short: {len(payload)} bytes")
    if payload[1] != HEAD_MARKER:
        raise InvalidRadarFrame(f"missing head marker, got 0x{payload[1]:02x}")
    if payload[-2] != TAIL_MARKER:
        raise InvalidRadarFrame(f"missing tail marker, got 0x{payload[-2]:02x}")

    target_state_byte = payload[2]
    if target_state_byte not in _TARGET_STATE_MAP:
        raise InvalidRadarFrame(f"unknown target state 0x{target_state_byte:02x}")

    moving_distance = payload[3] | (payload[4] << 8)
    moving_energy = payload[5]
    stationary_distance = payload[6] | (payload[7] << 8)
    stationary_energy = payload[8]

    return RadarFrame(
        timestamp_ms=timestamp_ms,
        target_state=_TARGET_STATE_MAP[target_state_byte],
        moving_energy=moving_energy,
        moving_distance_cm=moving_distance,
        stationary_energy=stationary_energy,
        stationary_distance_cm=stationary_distance,
    )


class RadarFrameStreamDecoder:
    """Feed raw UART bytes in as they arrive; get back any complete data
    frames found so far. Handles partial frames split across reads and
    resyncs past noise or non-data (command/ACK) frames."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, chunk: bytes, timestamp_ms: int) -> list[RadarFrame]:
        self._buffer.extend(chunk)
        frames: list[RadarFrame] = []

        while True:
            start = self._buffer.find(HEADER)
            if start == -1:
                self._drop_all_but_partial_header()
                break
            if start > 0:
                del self._buffer[:start]

            if len(self._buffer) < 6:
                break  # need at least header + length field

            length = self._buffer[4] | (self._buffer[5] << 8)
            if length > MAX_PLAUSIBLE_LENGTH:
                del self._buffer[:1]  # header matched by coincidence -- resync
                continue

            frame_end = 6 + length + len(FOOTER)
            if len(self._buffer) < frame_end:
                break  # frame not fully arrived yet

            payload = bytes(self._buffer[6 : 6 + length])
            footer = bytes(self._buffer[6 + length : frame_end])

            if footer != FOOTER:
                del self._buffer[:1]  # header matched by coincidence -- resync
                continue

            try:
                frames.append(decode_radar_payload(payload, timestamp_ms))
            except InvalidRadarFrame:
                pass  # malformed frame -- drop it, keep resyncing

            del self._buffer[:frame_end]

        return frames

    def _drop_all_but_partial_header(self) -> None:
        for keep in (3, 2, 1):
            if bytes(self._buffer[-keep:]) == HEADER[:keep]:
                del self._buffer[: len(self._buffer) - keep]
                return
        self._buffer.clear()
