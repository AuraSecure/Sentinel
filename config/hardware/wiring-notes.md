# Wiring Notes

Status: **provisional** — worked out from the Amazon/AliExpress listings, not yet confirmed against the physical boards. Check this against the actual silkscreen labels before powering anything on, then flip the status line above once verified.

## Boards on hand

- **Controller:** DORHEA ESP32-S3-DevKit, N16R8 — 16MB flash + **8MB octal PSRAM**. Dual USB-C (one is the USB-serial console, one may be native USB-OTG).
- **Radar:** AEDIKO LD2410C (HLK-LD2410C) breakout, 2-pack.
- **Mic:** EGSCST INMP441 breakout, 5-pack.

## Why N16R8 matters

Octal PSRAM eats GPIOs. On this variant, **GPIO26–37 are internally wired to the flash/PSRAM bus** and aren't safe to use for anything else, even if they're broken out on the header. That's the main constraint driving the pin choices below — a plain N8 (no PSRAM) or N16R2 (quad PSRAM) board would free some of that range back up, but this isn't one of those.

Also avoided: GPIO0/45/46 (boot/strapping pins — pulling these the wrong way at boot changes how the chip boots), GPIO19/20 (native USB D-/D+), GPIO43/44 (the board's own USB-serial console — reusing these will break flashing/serial monitor).

## Power — do not mix these up

| Sensor | Supply voltage | Notes |
|---|---|---|
| LD2410C | **5V** | Confirmed via Hi-Link datasheet: 5V–12V wide input, ~79mA draw. Will not run on 3.3V. UART logic level is 3.3V-compatible even though the supply isn't. |
| INMP441 | **3.3V** | Standard MEMS mic part. Do not feed it 5V. |

## Proposed pinout

| Signal | ESP32-S3 GPIO | Notes |
|---|---|---|
| LD2410C VCC | 5V pin | not 3.3V |
| LD2410C GND | GND | |
| LD2410C TX → ESP32 RX | GPIO18 | UART1 RX |
| ESP32 TX → LD2410C RX | GPIO17 | UART1 TX |
| INMP441 VDD | 3.3V pin | not 5V |
| INMP441 GND | GND | |
| INMP441 SCK | GPIO4 | I2S bit clock |
| INMP441 WS | GPIO5 | I2S word select (L/R clock) |
| INMP441 SD | GPIO6 | I2S data out |
| INMP441 L/R | tie to GND | selects left channel |

## To do before trusting this

- [ ] Confirm GPIO17/18 and GPIO4/5/6 actually exist and aren't pre-assigned to anything else on the physical board (check silkscreen).
- [ ] Confirm which USB-C port is the serial console vs. (if present) native USB, so GPIO19/20/43/44 assumptions hold.
- [ ] Once wired, this is exactly the point where `src/detector/detector/radar_protocol.py`'s checksum-algorithm gap and `audio_pcm.py`'s bit-shift gap (both flagged unconfirmed in `notes/knowledge-base.md`) get settled against real captured bytes.
