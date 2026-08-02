# Sentinel Knowledge Base

This is the single source of truth for anyone (human or AI) picking up Sentinel from here. Read this before touching code or notes. If something here conflicts with an older note file, this file wins — it's the corrected, current picture.

Last updated: 2026-08-01 (detector logic pass)

## What Sentinel is, right now

Sentinel is a **local, privacy-first fall detection node** — not fall protection, not a general dashboard, not an access-control platform. Earlier notes (`project-scope.md`, `ideas.md`) floated a much wider net (access control, automation helpers, technician dashboards). That net has been narrowed. Fall detection is the target for v1. Everything else is parked, not cancelled.

It should be treated as an **experimental detector first**, not a life-safety-certified device. False positives and real-world tuning are expected to dominate the later work, not be an afterthought.

## Approved hardware (locked for v1)

- **ESP32-S3** — controller
- **LD2410C** — radar / presence / motion sensor
- **INMP441** — I2S microphone / audio-event sensor

Hardware for these three has already been ordered. This baseline is considered stable enough to start writing real firmware logic against.

**Not locked yet** (fine to leave open, doesn't block software work): power delivery approach, final pin/wiring layout, enclosure, mounting, and whether additional sensors get added later. These are implementation-polish decisions, not architecture decisions.

## Strategy: software-first, before the physical build is trusted

The plan is to build and exercise the detection logic *before* leaning on real hardware tuning:

1. Define the event model, parser flow, state machine, and threshold logic in code.
2. Exercise that logic against replayable/simulated sensor scenarios (normal motion, sitting down, object drop, possible fall, recovery vs. non-recovery).
3. Only once logic is validated against synthetic scenarios, move to tuning against real captured logs from the actual ESP32-S3 + LD2410C + INMP441 hardware once it's built.

This lets iteration happen fast (talk through scenarios, adjust logic, rerun) without waiting on hardware access for every change.

## Actual repo progress (verified against the real filesystem, 2026-08-01)

Root:
- `README.md` — project description + folder layout

`notes/`:
- `README.md` — what the notes folder is for
- `session-2026-07-31.md` — first session log (repo setup)
- `tasks.md` — active/backlog/done task list
- `ideas.md` — raw idea dump (pre-narrowing, includes ideas outside fall detection)
- `decisions.md` — decision log (repo structure, GitHub as home base)
- `project-scope.md` — original open-ended scope note (pre-narrowing)
- `first-version.md` — draft framing for "what should v1 do"
- `knowledge-base.md` — this file

`src/detector/` — Python sandbox, **real application code now**, per the software-first plan:
- `detector/events.py` — `RadarFrame` / `AudioFrame` dataclasses mirroring the real LD2410C engineering-mode fields and an INMP441 feature window (peak/RMS, never raw PCM)
- `detector/thresholds.py` — every tunable sensitivity value in one `Thresholds` dataclass
- `detector/parser.py` — `RadarClueParser` / `AudioClueParser`, turning raw frames into simplified clues (motion spike, stillness, presence, audio impulse)
- `detector/fusion.py` — `score_tick`, the weighted-evidence-per-tick logic described below
- `detector/state_machine.py` — `FallStateMachine`, implementing the full `idle → baseline → candidate → verification → confirmed/dismissed → reset` cycle
- `tests/scenarios.py` + `tests/test_fall_scenarios.py` — 5 synthetic scenarios (normal motion, sitting down, object drop, fall/non-recovery, fall/recovery) covering the 6 named test cases, all passing against the logic above

`src/`:
- `client/README.md`, `server/README.md` — still placeholder, no code yet

`config/`:
- `README.md`, `config/hardware/README.md`, `config/app/README.md` — still placeholder, no actual config yet

**Bottom line:** the core detection logic described in this document — state machine, parser, fusion scoring — is implemented and passing a first round of synthetic scenario tests. It has **never seen real sensor data**; every threshold/weight in `thresholds.py` is a plausible starting guess, not a tuned value. `client/`, `server/`, `config/`, and the actual ESP32-S3 firmware port are still untouched.

## Known repo issue: accidental nested clone — resolved

An earlier pass of this doc flagged a `Sentinel-/Sentinel-/` nested-clone folder and a garbled `config/README.md` artifact. Both are gone as of this pass — `git status` is clean except for the new, not-yet-committed `src/detector/` work. No action needed here anymore.

## Fall detection definition (target behavior)

Sentinel v1 should be a local fall detection node that:
1. Uses radar (LD2410C) and audio (INMP441) inputs to identify a likely fall event.
2. Opens a short verification window to check whether recovery happens (person gets back up / normal movement resumes).
3. Raises a local alert or logs the event if the suspicious pattern persists through the verification window.

## Firmware architecture plan

Planned module breakdown, in intended build order:

1. **Sensor drivers** — clean reads from LD2410C and INMP441.
2. **Fall state machine (skeleton)** — states: `idle` → `pre-event baseline` → `candidate event` → `verification window` → `confirmed fall` / `dismissed-recovered` → `reset`.
3. **Signal parser** — converts raw sensor reads into simplified event clues (motion spike, stillness, audio spike, presence change).
4. **Fusion logic** — combines radar + audio evidence so no single noisy input dominates the decision.
5. **Threshold manager** — central, adjustable place for all sensitivity values (not scattered magic numbers).
6. **Alert/output layer** — starts as serial log / LED / buzzer, later extends to network or app output.

## Math and sensor-fusion plan (the part that matters most for "later")

Explicit non-goal: no jump straight to ML or a black-box classifier. First pass is an **interpretable, score-based detector** using measurable features from the two approved sensors. Move to anything fancier only if scoring proves insufficient.

### Sensor roles

- **LD2410C (radar):** presence state, motion/stillness transitions, and possibly distance or gate-energy clues depending on what the module actually exposes in practice.
- **INMP441 (mic):** audio-event features — impulse strength, short transients, possibly coarse spectral/energy characteristics — mainly used to confirm an impact-like event.

### First-pass detection math (conceptual pipeline)

1. Extract simple features from each sensor stream over short time windows.
2. Detect candidate events from thresholds or abrupt changes in those features.
3. On a candidate event, open a verification window.
4. Score whether the pattern after the event looks like non-recovery / abnormal stillness.
5. Escalate to a confirmed alert only if combined evidence stays suspicious long enough — no single spike triggers an alert by itself.

### Candidate features to score (not yet implemented — this is the spec for implementation)

Radar:
- Motion energy immediately before the event
- Sudden transition in motion state (moving → still)
- Presence persists, but normal movement doesn't resume
- Possible distance/posture proxy, if the LD2410C output supports it

Audio:
- Short impulse amplitude
- Energy burst in a narrow time window
- Impact-like transient vs. ongoing ambient room noise
- Optional spectral ratios later, if simple energy/impulse features aren't discriminating enough

### Fusion logic (rough shape, to formalize in code)

- **Candidate event** triggers if: radar shows a sudden change, OR audio shows an impact-like transient, OR both.
- **Confidence increases** if radar shows continued presence with reduced/abnormal movement after the event.
- **Confidence increases further** if the audio transient is time-aligned with the radar motion transition.
- **Confidence decreases** if normal movement resumes quickly.
- **Dismiss** if the pattern matches common false positives: fast sitting, object drop, furniture bump, pet movement, etc.

### State machine as the bridge from logic to math

Each state (`idle`, `pre-event baseline`, `candidate event`, `verification window`, `confirmed fall`, `dismissed/recovered`, `reset`) should accumulate **weighted evidence** from radar and audio over time, rather than making a single binary decision at one instant. This weighted-accumulation-per-state model is the intended bridge between "state machine logic" and "the math" — it's the next concrete thing to formalize in code.

## Testing strategy

- Build parsers around expected/simulated sensor event sequences before hardware is ready.
- Create replayable test cases for: normal motion, sitting down, object drop, possible fall, recovery, non-recovery.
- Use public sensor examples/protocol docs only as rough starting baselines — not ground truth.
- Replace synthetic assumptions with real Sentinel-captured logs as soon as the hardware exists and produces data.

## Known limitations (carry these forward, don't relitigate them)

- Pre-hardware/simulated testing is useful but cannot replace real-world validation — room reflections, sensor quirks, wiring mistakes, and threshold tuning all require the physical device.
- Final detection quality depends heavily on real logs captured from this specific setup, in this specific environment.
- Fall detection is inherently harder to get right than simpler event classes (e.g., glass-break detection) because false positives are more nuanced and "what counts as a fall" is less crisp to define.

## Working preferences for whoever continues this

- Prefers one instruction/step at a time for setup-style work, not a big batch to execute blind.
- When creating repo files, wants the file path *and* full file content together in the same response.
- Notes/docs tone should stay light, human, and slightly informal — not corporate boilerplate. (This file tries to match that; keep doing so in future notes.)
- Technically capable, comfortable mixing hardware and software thinking — no need to over-explain basics, but do surface tradeoffs.

## Open questions / assumptions to confirm

These aren't settled yet — they're gaps in the plan above that should get explicit answers (or explicit "yes, assume this for now") before they get quietly baked into the firmware.

- **Dev/test toolchain — answered.** Python + pytest, living in `src/detector/`. State machine, parser, and fusion logic are prototyped there against synthetic scenarios; validated logic gets ported to firmware later. Firmware language/framework (Arduino, PlatformIO, ESP-IDF) is still undecided.
- **What "privacy-first" means in practice.** The mic is the sensor most likely to raise privacy concerns. Working assumption: audio is processed for features only (impulse/energy) and never recorded or stored as raw audio, with no cloud upload. This is an assumption based on framing so far, not a confirmed requirement — should be confirmed explicitly.
- **Alert destination.** The alert layer plan (serial log → LED/buzzer → later network/app) doesn't say who receives a confirmed-fall alert — you, a caregiver's phone, a monitoring service? This shapes what the alert layer eventually needs to do.
- **Occupant/environment assumptions.** LD2410C radar will pick up pets and can't inherently identify "who" triggered an event. Current working assumption: single adult occupant, single room. Worth stating explicitly rather than discovering it as a limitation later.
- **False positive vs. missed-fall tolerance.** No stated target yet (e.g., "better to over-alert than miss a real fall"). This directly drives how aggressive threshold/scoring logic should be, so it's worth a short explicit philosophy statement once decided.

## Recommended next steps

1. ~~Resolve the nested-clone folder / garbled `config/README.md`~~ — done.
2. ~~Sensor input contract for LD2410C + INMP441~~ — done (`events.py`, mocked data only).
3. ~~Fall-detection state machine skeleton with weighted scoring~~ — done (`state_machine.py`).
4. ~~Signal parser and fusion logic~~ — done (`parser.py`, `fusion.py`).
5. ~~Replayable synthetic test scenarios~~ — done (`tests/scenarios.py`, 5 scenarios, 6 test cases, all passing).
6. **Commit the new `src/detector/` work** — it's currently untracked in git, nothing above is saved to history yet.
7. Add scenarios that stress the edges of the current thresholds (borderline energy values, an impulse just outside the alignment window, back-to-back candidate events) to sanity-check the weights aren't accidentally brittle.
8. Get explicit answers to the remaining open questions below (alert destination, false-positive vs. missed-fall philosophy, occupant assumptions) before they get quietly baked further into scoring.
9. Once satisfied with synthetic coverage, start on real LD2410C/INMP441 byte-level parsing (replacing the mocked `RadarFrame`/`AudioFrame` construction with actual UART/I2S decoding) — this is the bridge from `src/detector/` to real firmware.
10. Keep `config/hardware/` and `config/app/` as the home for threshold values and settings once the firmware port starts, per the structure already defined in their README files.
