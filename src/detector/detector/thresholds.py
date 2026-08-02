"""Central, adjustable sensitivity values -- module 5 of the firmware architecture
plan in notes/knowledge-base.md. Nothing else in this package should hardcode a
magic threshold; it should come from here.
"""

from dataclasses import dataclass


@dataclass
class Thresholds:
    # Radar (LD2410C reports gate energy 0-100)
    radar_motion_energy_min: int = 35
    radar_presence_energy_min: int = 20

    # Audio (normalized 0.0-1.0 features)
    audio_impulse_peak_min: float = 0.6
    audio_impulse_rms_min: float = 0.25

    # Timing
    tick_ms: int = 100
    verification_window_ms: int = 8_000
    alignment_window_ms: int = 1_000  # max gap between radar drop and audio impulse to count as "aligned"

    # Evidence weights (see fusion.score_tick)
    weight_motion_drop: float = 3.0
    weight_audio_impulse: float = 2.5
    weight_aligned_bonus: float = 2.0
    weight_motion_resumed: float = -4.0

    # Stillness-with-presence accrues slowly and caps out, so a long, ordinary
    # bout of sitting still never outscores a real fall on its own -- the cap
    # keeps this a corroborating signal, not the deciding one.
    weight_presence_no_motion: float = 0.15
    presence_no_motion_cap_ticks: int = 20

    confirm_score: float = 10.0
