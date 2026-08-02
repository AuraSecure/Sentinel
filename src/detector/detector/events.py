"""Raw sensor read shapes for LD2410C (radar) and INMP441 (mic).

These mirror the real protocol/output shapes so mock data stays close to what
the hardware will actually produce (LD2410C engineering-mode frame fields;
INMP441 pre-aggregated feature window, never raw PCM -- see knowledge-base.md
"What privacy-first means in practice").
"""

from dataclasses import dataclass
from enum import Enum, auto


class RadarTargetState(Enum):
    NONE = auto()
    MOVING = auto()
    STATIONARY = auto()
    BOTH = auto()


@dataclass(frozen=True)
class RadarFrame:
    """One LD2410C engineering-mode read."""

    timestamp_ms: int
    target_state: RadarTargetState
    moving_energy: int  # 0-100 gate energy, 0 if no moving target
    moving_distance_cm: int | None
    stationary_energy: int  # 0-100 gate energy, 0 if no stationary target
    stationary_distance_cm: int | None


@dataclass(frozen=True)
class AudioFrame:
    """One INMP441 feature window, already reduced to impulse/energy features."""

    timestamp_ms: int
    window_ms: int
    peak_amplitude: float  # normalized 0.0-1.0
    rms_energy: float  # normalized 0.0-1.0
