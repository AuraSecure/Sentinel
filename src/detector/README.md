# Detector (Python sandbox)

This is where the fall-detection logic actually gets built and proven before it ever touches the ESP32-S3.

Software-first, per `notes/knowledge-base.md`: the state machine, sensor parsers, and scoring/fusion logic all get written and tested here in plain Python against protocol-accurate mock sensor data (real LD2410C UART frames, real INMP441 I2S sample shapes) — not real hardware, not vague stand-ins. Once a piece of logic is proven against synthetic scenarios, it's a much smaller, lower-risk job to port it to firmware.

## Why Python first
- Fast iteration — change a threshold, rerun, see the result immediately.
- Easy to plot/inspect signals and decisions.
- The state machine and scoring logic are sensor-agnostic (they consume parsed events, not raw bytes), so this code has a real shot at porting close to 1:1 later. Only the low-level parsers/drivers need a rewrite in C/C++.

## Structure

```text
detector/
├── detector/       # the actual package: parsers, state machine, scoring, fusion
└── tests/          # pytest suite — replayable scenarios (normal motion, sit-down,
                     # drop, fall, recovery, non-recovery)
```

## Setup

```bash
cd src/detector
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

## Running tests

```bash
pytest
```

## Status

Core detection logic is in place and passing tests (19/19): sensor event contracts (`events.py`), tunable thresholds (`thresholds.py`), the radar/audio clue parser (`parser.py`), fusion scoring (`fusion.py`), the fall state machine (`state_machine.py`), and now real byte-level sensor decoding: `radar_protocol.py` decodes the actual LD2410C UART data-frame protocol (header/length/payload/footer, stream buffering, resync on noise), and `audio_pcm.py` decodes raw INMP441 I2S PCM into peak/RMS features. `tests/scenarios.py` covers normal motion, sitting down, object drop, and fall with/without recovery.

Not done yet: neither decoder has seen real hardware. The LD2410C checksum algorithm isn't validated (presence-checked only), and the INMP441 bit-shift used to unpack samples is a documented best guess -- both are called out explicitly in their module docstrings as needing confirmation against real captured logs. Threshold tuning and the firmware port are also still ahead. See `notes/knowledge-base.md` for the full picture and next steps.
