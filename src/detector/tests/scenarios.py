"""Synthetic sensor sequences for the scenarios named in
notes/knowledge-base.md's testing strategy: normal motion, sitting down,
object drop, possible fall, recovery, non-recovery.

"Possible fall" is the shared onset of scenario_fall_confirmed and
scenario_fall_recovered below -- the point of the verification window is that
the same onset can resolve either way depending on what happens next.
"""

from detector.events import AudioFrame, RadarFrame, RadarTargetState

TICK_MS = 100


class _TickBuilder:
    def __init__(self):
        self.ticks: list[tuple[RadarFrame, AudioFrame]] = []

    def add(
        self,
        count: int,
        *,
        state: RadarTargetState,
        moving_energy: int = 0,
        stationary_energy: int = 0,
        peak: float = 0.05,
        rms: float = 0.03,
    ) -> "_TickBuilder":
        start = len(self.ticks) * TICK_MS
        for i in range(count):
            ts = start + i * TICK_MS
            self.ticks.append(
                (
                    RadarFrame(ts, state, moving_energy, None, stationary_energy, None),
                    AudioFrame(ts, TICK_MS, peak, rms),
                )
            )
        return self

    def build(self) -> list[tuple[RadarFrame, AudioFrame]]:
        return self.ticks


def scenario_normal_motion():
    """Continuous walking, nothing unusual. Should never even open a verification window."""
    return _TickBuilder().add(100, state=RadarTargetState.MOVING, moving_energy=60).build()


def scenario_sitting_down():
    """Walk to a chair, sit (soft bump, not an impulse), then normal fidgeting.
    Should be dismissed -- this is one of the named false-positive cases."""
    b = _TickBuilder()
    b.add(10, state=RadarTargetState.MOVING, moving_energy=55)
    b.add(1, state=RadarTargetState.STATIONARY, stationary_energy=50, peak=0.4, rms=0.15)
    b.add(15, state=RadarTargetState.STATIONARY, stationary_energy=50)
    b.add(2, state=RadarTargetState.MOVING, moving_energy=45)
    b.add(20, state=RadarTargetState.STATIONARY, stationary_energy=50)
    b.add(2, state=RadarTargetState.MOVING, moving_energy=45)
    b.add(60, state=RadarTargetState.STATIONARY, stationary_energy=50)
    return b.build()


def scenario_object_drop():
    """Something drops/bangs nearby while the person keeps walking normally --
    an audio impulse with no correlated radar change. Should be dismissed."""
    b = _TickBuilder()
    b.add(20, state=RadarTargetState.MOVING, moving_energy=55)
    b.add(1, state=RadarTargetState.MOVING, moving_energy=55, peak=0.75, rms=0.4)
    b.add(90, state=RadarTargetState.MOVING, moving_energy=55)
    return b.build()


def scenario_fall_confirmed():
    """Possible fall, non-recovery: motion drop + aligned impact, then the
    person stays down through the whole verification window. Should confirm."""
    b = _TickBuilder()
    b.add(10, state=RadarTargetState.MOVING, moving_energy=55)
    b.add(1, state=RadarTargetState.STATIONARY, stationary_energy=45, peak=0.85, rms=0.5)
    b.add(90, state=RadarTargetState.STATIONARY, stationary_energy=45)
    return b.build()


def scenario_fall_recovered():
    """Possible fall, recovery: identical onset to scenario_fall_confirmed, but
    the person gets back up within a second. Should be dismissed."""
    b = _TickBuilder()
    b.add(10, state=RadarTargetState.MOVING, moving_energy=55)
    b.add(1, state=RadarTargetState.STATIONARY, stationary_energy=45, peak=0.85, rms=0.5)
    b.add(4, state=RadarTargetState.STATIONARY, stationary_energy=45)
    b.add(5, state=RadarTargetState.MOVING, moving_energy=55)
    b.add(80, state=RadarTargetState.MOVING, moving_energy=55)
    return b.build()
