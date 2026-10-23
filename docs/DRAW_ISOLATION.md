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

### Sound dependency follow-up (2026-10-23, in verification)

The voice volume table starts at `0x8010FF68`, with 16 bytes per voice.
`0x8010FFE8` and `0x8010FFF8` are voices 8 and 9. The writer is
`0x80086D44` (recorded caller `0x800501CC`). The updater `0x80087240`
sets the table base at `0x800874A8`, reads the volume halfword at
`0x800874EC`, and advances to the next voice at `0x800875E4`. This is a
sound-state dependency, not dead drawing storage.

The gate now suspends the private context around original recompiled calls
to `0x8004F520`, `0x80051840`, and `0x80051B00`. All take scalar register arguments;
their only stack loads restore registers they saved themselves. Calls run
synchronously on main at their original guest call point, then resume the
draw context. The third call, `0x80051840`, writes pending volumes at
`0x800F6924/28`. Leaving it isolated still diverged at tick 154 of the fresh
countdown state: voice 8/9 volumes were `0x1B36` instead of stock `0x1AB5`.
`0x8004F5E0` queues HUD voice cues from `0x8003C4B4`/`0x80039C04`; the
static audit identifies it as another main-side call to cover before the
broader mode gate. The three-hook GP run matches through tick 2798, then
diverged in frame output, RAM and scratchpad at tick 2799. The exact tick dump identified
the BIOS random seed at `0x80008548` (OpenBIOS `0xBFC060E4`, load at
`0xBFC060E8`), particle counter `0x800F4E30`, and particle `0x8010B800`.
The current test routes `rand()` stub `0x80096640` and the HUD cue through main.
Commit `6000b17` passes the stock Grand Prix whole-race gate: all 18,101
tick rows match across base, nested and isolated runs through TIME OVER
(phase 5), with zero dispatch misses. Base/nested also match all 32,767
shared retained fingerprint frames. Wall times under shared load were
356.6 / 343.8 / 1071.7 seconds respectively; isolation's full-memory
diagnostic copies are not a worker performance measurement. Local receipts:
`C:/Users/Shokunin/dev/r4-iso-runs/sound-rng-v4-20261023`, executable SHA-256
`aa46cd52d2588ab2df2139f12d174c9cac59933fb6e0432596e3df2eccbe5f25`.
The framework suspend/resume test checks separate RAM/GTE,
main writes visible on resume, and an IRQ inside the main call staying main.
Broader-mode and default-mod verification remain pending; this does not yet
authorize real-frame worker execution.

Time Attack has 3,258 matching stock/isolated ticks (6,500-frame bounded
runs, zero misses), but has not reached the goal. Its route needs a finishing
driver because this mode has no GP time-limit exit. Receipts:
`C:/Users/Shokunin/dev/r4-iso-runs/ta-v4-20261023`.

Commit `e1322e6` also hands scratchpad heap/OT pointers `0x1F800000/4` to
main at the pass point. Max Detail's DrawOTag hook consumes the heap end
for its next-frame budget; withholding it changed the course visibility
list at default-mod tick 118. A public-range ablation restored that tick's
exact frame hash. Demo/replay producers now have entry hooks. The stock
attract-demo gate passes through the handler exit: base/nested/isolated
match 1,401 tick rows, base/nested match 3,492 shared fingerprints, and all
three have zero dispatch misses. Receipts:
`C:/Users/Shokunin/dev/r4-iso-runs/demo-v5-20261023` (runtime SHA-256
`cb4dea71939d8b26aef2a0c6bbb67ce3e588f6f330ae970f2548cc0b28dc6d75`).

Default-mod A/A runs already differ before testing isolation: the first
tick differs at SDK pad/SIO timeout sample `0x801147E8` (writers
`0x8009A9EC`, `0x80098858`), with alternating subsequent frame hashes.
Three short A/A runs with `PSX_GCS_BATCH=0` matched 51 ticks each, but later
runs also diverged with batching disabled. The two first-tick hash values
occur under both settings; batching is not isolated as the cause. This is
not a passing default gate or permission to ignore differences. Receipts are under
`C:/Users/Shokunin/dev/r4-iso-runs/defaults-v4-20261023`.

First-frame access recordings locate the earlier cause: Max Detail's
`0x80014A90` entry hook conditionally writes reflection page `0x8009E288`
according to the widescreen margin. Loading immediately after boot can run
this hook before widescreen engagement. Booting to the title before loading
made two 600-frame baseline runs agree through their shared deterministic
input interval (305 ticks / 610 fingerprints). Longer warm-start baseline
runs match 2,871 shared ticks before the owner stopped long verification;
no hash fields have been relaxed. Receipts are under `defaults-v5-20261023`.
The driver now keeps its input route running until process exit, avoiding
host-timed neutral-input ticks during shutdown.

The driver refuses existing run directories, supports `--defaults`, requires
both runs to reach the race end, and compares isolated merged tick state
without treating dead-stack write fingerprints as failures. Nested stock
runs still require full fingerprint equality. The owner subsequently bounded
automated runs to 30 seconds (performance samples to 15 seconds); the driver
now defaults to `--seconds 30`. Partial coverage remains labelled incomplete
by the whole-race comparator and no longer blocks implementation. Split-screen
matched 10,810 shared ticks before that stop, with zero dispatch misses on
both sides (`split-v5-20261023`). Time Attack and after-goal replay tails
remain unverified. `--autodrive` enables a test-only centreline driver; its
per-player input logs must match as well as the guest state. Demo/replay-only
hooks are inactive in the three race modes.

The 30-second Time Attack check with the finishing driver matches all 588
shared ticks and 1,175 shared input polls, with zero dispatch misses
(`ta-v7-short-20261023`). Neither run reached the goal; the comparator reports
incomplete whole-race coverage. The test input uses the post-sampling frame
hook because ordinary controller transforms intentionally skip headless and
TCP-injected input. Windows build and three relevant CTests passed.

### Worker side-effect contract

The gate models **real-frame** drawing: sound and RNG calls occur on main
at their original guest call points, with the scalar arguments/results from
that point. A worker must preserve that order and the shared RNG advancement;
an end-of-tick snapshot alone cannot replace the HUD's earlier logic state.
Dependency handling must be explicit before allowing main logic to read it.

An **in-between** redraw must keep RNG private and discard its seed changes,
as the existing render-pass transaction does by restoring RAM. It must not
replay sound or advance main RNG. The synchronous gate hooks are not an API
for a worker to mutate the main machine concurrently.

1. Resolve default-mod A/A restore reproducibility.
2. Finish Time Attack (mode 1), split screen (mode 3), attract demo and
   after-goal replay verification with the expanded hooks.
3. Repeat with default mods (widescreen, max detail, PGXP) and verify hook
   composition with both nested and isolated runs.
4. Specify the worker handoff: per-call-point state, frame output, main-side
   dependencies and cycle charge, then wire local gate verification.
