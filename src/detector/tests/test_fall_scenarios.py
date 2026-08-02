from detector.parser import AudioClueParser, RadarClueParser
from detector.state_machine import FallState, FallStateMachine
from detector.thresholds import Thresholds

from scenarios import (
    scenario_fall_confirmed,
    scenario_fall_recovered,
    scenario_normal_motion,
    scenario_object_drop,
    scenario_sitting_down,
)

TERMINAL_STATES = (FallState.CONFIRMED_FALL, FallState.DISMISSED_RECOVERED)


def run_scenario(ticks):
    thresholds = Thresholds()
    radar_parser = RadarClueParser(thresholds)
    audio_parser = AudioClueParser(thresholds)
    machine = FallStateMachine(thresholds)

    terminal = None
    for radar_frame, audio_frame in ticks:
        state = machine.step(radar_parser.parse(radar_frame), audio_parser.parse(audio_frame))
        if terminal is None and state in TERMINAL_STATES:
            terminal = state
    return terminal, machine


def test_normal_motion_never_triggers():
    terminal, machine = run_scenario(scenario_normal_motion())
    assert terminal is None
    assert machine.state == FallState.BASELINE


def test_sitting_down_is_dismissed():
    terminal, _ = run_scenario(scenario_sitting_down())
    assert terminal == FallState.DISMISSED_RECOVERED


def test_object_drop_is_dismissed():
    terminal, _ = run_scenario(scenario_object_drop())
    assert terminal == FallState.DISMISSED_RECOVERED


def test_fall_with_no_recovery_is_confirmed():
    terminal, _ = run_scenario(scenario_fall_confirmed())
    assert terminal == FallState.CONFIRMED_FALL


def test_fall_with_quick_recovery_is_dismissed():
    terminal, _ = run_scenario(scenario_fall_recovered())
    assert terminal == FallState.DISMISSED_RECOVERED
