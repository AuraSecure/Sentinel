"""Fusion logic -- module 4 of the firmware architecture plan. Combines radar
+ audio clues into weighted evidence per tick, per the fusion rules in
notes/knowledge-base.md: a candidate event needs radar OR audio; confidence
rises with aligned, corroborating evidence and falls fast the moment normal
movement resumes.
"""

from dataclasses import dataclass

from .parser import AudioClue, RadarClue
from .thresholds import Thresholds


@dataclass
class FusionContext:
    """Rolling state fusion needs across ticks to judge sensor time-alignment
    and how long stillness/repeated-impulse evidence has been accruing."""

    last_motion_drop_ts: int | None = None
    consecutive_still_ticks: int = 0
    audio_impulse_count: int = 0


def is_candidate_trigger(radar: RadarClue, audio: AudioClue) -> bool:
    return radar.motion_dropped or audio.impulse


def score_tick(radar: RadarClue, audio: AudioClue, ctx: FusionContext, thresholds: Thresholds) -> float:
    """Weighted evidence delta for one verification-window tick."""
    t = thresholds
    delta = 0.0

    if radar.motion_dropped:
        delta += t.weight_motion_drop
        ctx.last_motion_drop_ts = radar.timestamp_ms

    if audio.impulse:
        # Base impulse weight caps out after a few occurrences so sustained,
        # radar-uncorroborated noise (a TV, an alarm, music) can never alone
        # add up to a confirm -- only a genuine aligned hit, or corroborating
        # radar evidence, can close the gap from here.
        ctx.audio_impulse_count += 1
        if ctx.audio_impulse_count <= t.audio_impulse_cap:
            delta += t.weight_audio_impulse
        if ctx.last_motion_drop_ts is not None and audio.timestamp_ms - ctx.last_motion_drop_ts <= t.alignment_window_ms:
            delta += t.weight_aligned_bonus

    if radar.presence and not radar.motion_active:
        ctx.consecutive_still_ticks += 1
        if ctx.consecutive_still_ticks <= t.presence_no_motion_cap_ticks:
            delta += t.weight_presence_no_motion
    else:
        ctx.consecutive_still_ticks = 0

    if radar.motion_active and radar.energy >= t.radar_motion_energy_min:
        delta += t.weight_motion_resumed

    return delta
