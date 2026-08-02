from detector.events import RadarFrame, RadarTargetState
from detector.fusion import FusionContext, score_tick
from detector.parser import AudioClue, RadarClue, RadarClueParser
from detector.state_machine import FallState, FallStateMachine
from detector.thresholds import Thresholds


def radar_clue(ts, presence=False, motion_active=False, motion_dropped=False, energy=0):
    return RadarClue(ts, presence, motion_active, motion_dropped, energy)


def audio_clue(ts, impulse=False, energy=0.0):
    return AudioClue(ts, impulse, energy)


def test_motion_active_boundary_exactly_at_threshold():
    t = Thresholds()
    at_threshold = RadarClueParser(t).parse(RadarFrame(0, RadarTargetState.MOVING, t.radar_motion_energy_min, None, 0, None))
    below_threshold = RadarClueParser(t).parse(
        RadarFrame(0, RadarTargetState.MOVING, t.radar_motion_energy_min - 1, None, 0, None)
    )

    assert at_threshold.motion_active is True
    assert below_threshold.motion_active is False


def test_alignment_bonus_applies_exactly_at_window_edge():
    # presence stays False throughout so the stillness-bonus branch can't
    # confound the delta being asserted on -- this test isolates alignment only.
    t = Thresholds()
    ctx = FusionContext()
    score_tick(radar_clue(0, motion_dropped=True), audio_clue(0), ctx, t)

    delta = score_tick(radar_clue(t.alignment_window_ms), audio_clue(t.alignment_window_ms, impulse=True), ctx, t)

    assert delta == t.weight_audio_impulse + t.weight_aligned_bonus


def test_alignment_bonus_missing_just_past_window_edge():
    t = Thresholds()
    ctx = FusionContext()
    score_tick(radar_clue(0, motion_dropped=True), audio_clue(0), ctx, t)

    late_ts = t.alignment_window_ms + t.tick_ms
    delta = score_tick(radar_clue(late_ts), audio_clue(late_ts, impulse=True), ctx, t)

    assert delta == t.weight_audio_impulse


def test_repeated_unaligned_audio_impulses_alone_never_confirm():
    """Loud, repeated, radar-uncorroborated noise (TV, alarm, music) should
    never be enough on its own -- fusion needs at least some radar evidence."""
    machine = FallStateMachine()
    state = FallState.IDLE

    for i in range(60):
        ts = i * 100
        state = machine.step(radar_clue(ts), audio_clue(ts, impulse=True, energy=0.9))

    assert state != FallState.CONFIRMED_FALL


def test_back_to_back_candidate_events_score_independently():
    machine = FallStateMachine()
    state = FallState.IDLE

    machine.step(radar_clue(0, presence=True, motion_dropped=True), audio_clue(0, impulse=True, energy=0.5))
    ts = 0
    for i in range(1, 40):
        ts = i * 100
        state = machine.step(radar_clue(ts, presence=True), audio_clue(ts))
        if state == FallState.CONFIRMED_FALL:
            break
    assert state == FallState.CONFIRMED_FALL

    ts += 100
    second_state = machine.step(radar_clue(ts), audio_clue(ts))

    assert second_state == FallState.BASELINE
    assert machine.score == 0.0
