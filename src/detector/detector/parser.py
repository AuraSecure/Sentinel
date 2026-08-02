"""Signal parser -- module 3 of the firmware architecture plan. Converts raw
sensor frames into simplified event clues (motion spike, stillness, audio
spike, presence change) that the fusion/state-machine layers reason about.
"""

from dataclasses import dataclass

from .events import AudioFrame, RadarFrame, RadarTargetState
from .thresholds import Thresholds


@dataclass(frozen=True)
class RadarClue:
    timestamp_ms: int
    presence: bool
    motion_active: bool
    motion_dropped: bool  # transitioned from moving -> not-moving this tick
    energy: int  # dominant target energy this tick


@dataclass(frozen=True)
class AudioClue:
    timestamp_ms: int
    impulse: bool  # short, sharp transient consistent with an impact
    energy: float


class RadarClueParser:
    """Stateful: needs the previous frame to detect a moving-to-still transition."""

    def __init__(self, thresholds: Thresholds):
        self._thresholds = thresholds
        self._was_moving = False

    def parse(self, frame: RadarFrame) -> RadarClue:
        t = self._thresholds
        motion_active = (
            frame.target_state in (RadarTargetState.MOVING, RadarTargetState.BOTH)
            and frame.moving_energy >= t.radar_motion_energy_min
        )
        presence = frame.target_state != RadarTargetState.NONE
        motion_dropped = self._was_moving and not motion_active
        self._was_moving = motion_active
        energy = max(frame.moving_energy, frame.stationary_energy)
        return RadarClue(frame.timestamp_ms, presence, motion_active, motion_dropped, energy)


class AudioClueParser:
    def __init__(self, thresholds: Thresholds):
        self._thresholds = thresholds

    def parse(self, frame: AudioFrame) -> AudioClue:
        t = self._thresholds
        impulse = frame.peak_amplitude >= t.audio_impulse_peak_min and frame.rms_energy >= t.audio_impulse_rms_min
        return AudioClue(frame.timestamp_ms, impulse, frame.rms_energy)
