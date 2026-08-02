"""Fall state machine -- module 2 of the firmware architecture plan.

States: idle -> pre-event baseline -> candidate event -> verification window
-> confirmed fall / dismissed-recovered -> reset. Each verification-window
tick accumulates weighted evidence (see fusion.py) rather than deciding on a
single instant, per the "weighted-accumulation-per-state" model in
notes/knowledge-base.md.
"""

from dataclasses import dataclass
from enum import Enum, auto

from .fusion import FusionContext, is_candidate_trigger, score_tick
from .parser import AudioClue, RadarClue
from .thresholds import Thresholds


class FallState(Enum):
    IDLE = auto()
    BASELINE = auto()
    CANDIDATE = auto()
    VERIFICATION = auto()
    CONFIRMED_FALL = auto()
    DISMISSED_RECOVERED = auto()


@dataclass(frozen=True)
class ScoreSample:
    timestamp_ms: int
    state: FallState
    score: float


class FallStateMachine:
    """Consumes one (RadarClue, AudioClue) pair per tick."""

    def __init__(self, thresholds: Thresholds | None = None):
        self.thresholds = thresholds or Thresholds()
        self.state = FallState.IDLE
        self.score = 0.0
        self.history: list[ScoreSample] = []
        self._fusion_ctx = FusionContext()
        self._window_start_ms: int | None = None

    def step(self, radar: RadarClue, audio: AudioClue) -> FallState:
        if self.state in (FallState.CONFIRMED_FALL, FallState.DISMISSED_RECOVERED):
            self._reset()

        if self.state in (FallState.IDLE, FallState.BASELINE):
            self.state = FallState.BASELINE
            if is_candidate_trigger(radar, audio):
                self._open_verification_window(radar, audio)
        elif self.state == FallState.VERIFICATION:
            self._advance_verification(radar, audio)
        else:
            raise AssertionError(f"unreachable state {self.state}")

        self.history.append(ScoreSample(radar.timestamp_ms, self.state, self.score))
        return self.state

    def _open_verification_window(self, radar: RadarClue, audio: AudioClue) -> None:
        self.state = FallState.CANDIDATE
        self._window_start_ms = radar.timestamp_ms
        self.score = 0.0
        self._fusion_ctx = FusionContext()
        self.state = FallState.VERIFICATION
        self._advance_verification(radar, audio)

    def _advance_verification(self, radar: RadarClue, audio: AudioClue) -> None:
        self.score = max(self.score + score_tick(radar, audio, self._fusion_ctx, self.thresholds), 0.0)
        elapsed = radar.timestamp_ms - self._window_start_ms

        if self.score >= self.thresholds.confirm_score:
            self.state = FallState.CONFIRMED_FALL
        elif elapsed >= self.thresholds.verification_window_ms:
            self.state = FallState.DISMISSED_RECOVERED

    def _reset(self) -> None:
        self.state = FallState.IDLE
        self.score = 0.0
        self._window_start_ms = None
        self._fusion_ctx = FusionContext()
