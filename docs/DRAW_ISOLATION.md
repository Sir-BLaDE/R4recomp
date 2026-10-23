# Draw isolation (threaded race draw): findings and gate

Status: **work in progress, gate not passing yet.** The gate tooling works and
has found its first real dependency (sound state, below). Nobody should move the
real-frame draw off the emulation thread until `tools/draw_iso_gate.py gate`
passes over a whole race.

Goal (owner): run R4's frame draw on worker threads in parallel with the next
tick's logic, plus interpolated in-between frames and split course rendering.
This document records which guest state the race draw path writes, whether
the logic reads any of it, and the gate that has to pass first.

## The gate

Framework (psxrecomp `runtime/include/draw_isolation.h`,
`runtime/src/draw_isolation.c`):

- Spans of guest code run against a **private draw context**: main RAM,
  scratchpad and the GTE register file are swapped in on `psx_draw_iso_enter()`
  and out on `psx_draw_iso_leave()`. Spans run in place on the guest clock, so
  cycles, device timing and interrupts are stock.
- RAM and scratchpad merge **per byte, last writer wins**. Main-context stores
  are seen exactly through the debug server's RAM write hook (CPU and DMA,
  so `PSX_DEBUG_TOOLS=ON` builds only); draw stores are the leave-time diff.
  If the logic never reads a byte the draw wrote, the merged image equals the
  stock machine at every point.
- The **GTE is not merged**: each context keeps its own registers, as each
  thread of a threaded build would.
- Interrupts taken inside a span run on the main context (`psx_check_interrupts`
  edge observer), as they would on the emulation thread.
- Device-register traffic inside spans is counted per class (memory.c MMIO
  observer).
- `psx_draw_iso_handoff()` publishes a range to main (the frame output);
  `psx_draw_iso_set_public()` hands a range to main at every leave (ablation).
- Modes: stale (the main context keeps its own value of a draw-written byte,
  the threaded model) or `PSX_DRAW_ISO_POISON` (main sees it inverted, so every
  read shows, harmless garbage reads included).

Debug-server additions used for exact A/B from one savestate (the frame counter
is host state, not restored by a load): `input_route_start on_load=K` and
`record_frame after_load=K`.

R4 (developer package `r4.debug.draw-isolation`, channel developer, never
ships; plugin `src/mods/r4_draw_isolation.c`):

- Every top-level call of the race-handler draw functions (the r4_interp.c call
  lists: 22 HUD producers, viewport `0x8006F2B0`, view build `0x8006E4D0`,
  cars `0x8002E554`/`0x8002DC00`, course `0x8006F00C`, objects `0x80074AD8`,
  course tail `0x800374F8`, mirror `0x80070A58`) and the main loop's two
  `ClearOTagR` calls runs nested from its entry hook inside a span.
- At `VSync(0)` (ra `0x8001E7E4`) the frame output is handed to main:
  DRAWENV/DISPENV (`buf+0..0x70`) and every word the `DrawOTag` walk of OT1
  (and OT2 when `0x800ACDB0`) will read. One CSV line per race tick logs
  merged-state hashes (`ram_hash` without the dead stack and the kernel's
  interrupted-register save `0x9088-0x9128`; `ram_hash_all` whole RAM),
  scratchpad, the OT walk hash, owned-byte counts and main-loop reads of
  owned bytes.
- Leaving race handlers publishes the whole draw context (a mode-change sync
  point).

Driver: `tools/draw_iso_gate.py` (`prepare` saves a Grand Prix race state
headless+turbo; `run base|nest|iso|poison` loads it, replays a frame-exact
input route, logs ticks and frame fingerprints; `compare`; `gate`). Env knobs:
`R4_DRAW_ISO_PUBLIC`, `R4_DRAW_ISO_SKIP`, `R4_DRAW_ISO_DUMP`, `R4_DRAW_ISO_DEBUG`,
`R4_DRAW_ISO_REGS` (see the plugin header).

## Results so far (GP race, mode 2 handler `0x80114A38`, 1500 frames)

| Run | Result |
|---|---|
| base vs base (A/A) | identical: ticks and frame fingerprints |
| base vs nest (draw calls nested, no isolation) | identical: 761 ticks, 1518 fingerprint frames (cyc, mmio, wc, ws, sp...) |
| base vs iso | **ticks identical for 130 ticks** (OT walk, merged RAM, scratchpad); first divergence at tick 131 in `0x8010FFE8`/`0x8010FFF8`; guest-write fingerprint `ws` differs from frame 3 (garbage, below) |

Per tick: 22 spans, about 1 interrupt taken inside a span, 10 DMA register
writes in spans (the `ClearOTagR` OTC DMA), no GPU, SPU, CD, timer or pad
register traffic inside spans on this course segment.

Bytes written per call over 754 ticks (all frame output except where noted):
course `0x8006F00C` 16.2 MB, mirror `0x80070A58` 6.6 MB, course tail
`0x800374F8` 1.2 MB, ClearOTagR 0.6 MB, cars `0x8002E554` 475 KB, objects
`0x80074AD8` 111 KB, view build 85 KB, HUD calls 1.5-63 KB each.

## Classification so far

What stays draw-owned after the frame handoff (union over the run), and what we
know about logic reads:

| Region | Owned bytes | Class | Evidence |
|---|---|---|---|
| Frame buffers `0x800ADCA0-0x800F2B90` (DRAWENV/DISPENV, OT1, OT2, primitive heap, per-buffer HUD prims) | all handed off | **double-buffered**: output of frame n, consumed by the main loop's `DrawOTag` | OT walk hash identical every tick |
| Primitive heap pointer `1F800000`, OT pointer `1F800004` | scratch | **double-buffered/handoff**: main loop resets them each tick; no logic read found (an early failure here was a gate bug, fixed) | ticks 0-130 identical |
| Other scratchpad `1F800005..`, `1F800028..`, `1F800040..` (camera/clip/matrix scratch) | ~700 B | draw-private so far | no divergence |
| GTE registers | 198 B (rotation, translation, OFX/OFY/H, colour) | **draw-private so far** with separate per-context GTE | no divergence in 130 ticks; mode 1 relies on GTE OFX/OFY/H carrying over from the handler end (static audit), still to be confirmed over a full race |
| Dead stack `0x801F0000-0x80200000` | ~550 B | **garbage only**: logic reads uninitialised stack words the draw left (e.g. store at `0x80046804`, caller `0x80046CA4`, frame 3) and the kernel saves dead registers on interrupts | causes `ws` fingerprint differences only; excluded from `ram_hash` |
| EXE globals `0x800AC088..`, `0x800AC790`, `0x800AD748..`, `0x800ADC80`, `0x8009F1F3`, `0x800F3B58..`, `0x800FF840..` | ~130 B | draw-private so far (view/viewport temporaries, digit colours: the static audit's idempotent temporaries) | no divergence |
| `0x8010B5D4..`, `0x8011A9A8..` (object/particle and overlay tables) | ~500 B | unknown: no divergence in 130 ticks | |
| **Sound state `0x8010FFE8`, `0x8010FFF8`** (libsnd voice/SE area; the objects draw `0x80074AD8` calls `0x8004F520`/`0x80051B00` → libsnd) | | **feeds logic** (first confirmed dependency): main's sound code reads what the objects draw wrote | first divergence, tick 131 |

## Draw boundary (so far)

- Movable (worker): the race handler's draw call list above with the handler
  glue between the calls, ClearOTagR of the tick's buffer, on a context made
  from the main state at each call point. The merged per-call model is what the
  gate checks; a real worker needs the logic state as of each call point (HUD
  calls run before car/camera logic `0x800382AC`, `0x800738C4`, `0x80033974`,
  `0x800340EC` in the GP handler, so one snapshot at the end of the tick would
  show a newer HUD than stock).
- Main must keep: input, sound tick, CD poll, DrawSync/VSync/PutDispEnv/
  PutDrawEnv/DrawOTag (consuming the handed-off buffer), all logic calls, and
  (so far) the **sound side effects of the objects draw** (`0x8004F520` key-on
  and `0x80051B00` positional SE inside `0x80074AD8`): either split them out
  and run them on main, or replay them on main from a record the worker makes.
- Guest cycles: spans run in place here. A threaded build must still charge the
  draw's guest cycles to the guest clock before the VSync wait, or lag frames
  and IRQ timing change.

## Remaining steps

1. Find the reader of `0x8010FFE8/F8` (wtrace on `0x10FFE0-0x110000` in base and
   iso, then `R4_DRAW_ISO_SKIP`/`PUBLIC` ablation) and confirm it is the
   objects draw's SE calls; classify, then make those calls a main-side replay
   and rerun.
2. Repeat until `iso` matches `base` over a whole race: route to the time-limit
   end (`route_steps`: 24 drive cycles then let go), `--frames 40000`, plus the
   goal/replay modes; then mode 1 (Time Attack), split screen (mode 3), the
   attract demo and the after-goal replay (needs entry hooks for
   `0x800914B0`, `0x80014A84`, `0x800558E8`, `0x80020074`, the demo text calls).
3. Rerun with the default mods (widescreen, max detail, PGXP) on: their hooks
   on the same functions run twice under `nest`/`iso` unless ordered first.
4. Teach `compare` to accept unequal run lengths once both cover the race end,
   and judge fingerprints only for `nest` (they carry stack garbage under `iso`).
5. Then specify the worker handoff (per-call-point state, frame output, sound
   replay, cycle charge) and wire `gate` into CI-free local verification.
