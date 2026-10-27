# Projection replay: the second race frame-rate method

The Race frame rate mod draws its extra race frames with one of two
recipes, chosen by the feature's `method` option (default `fields`):

- **fields** (`src/mods/r4_interp.c`): the car and camera values the draw
  code reads (`tools/data/r4_interp_fields.json`) are blended between the
  last two 30 Hz ticks and the handler's draw-only call list is re-run; the
  draw runs on worker contexts (`r4_interp_workers.h`) when available.
- **projection** (`src/mods/r4_projection_replay.cpp`): psxrecomp's shared
  draw replay (`render_pass_replay.hpp`). The main loop's RAM is snapshotted
  at the loop head (ClearOTagR entry, ra 0x8001E764) and every RTPS/RTPT the
  handler performs is recorded with its final rotation/translation. A pass
  puts that RAM back, selects and clears the dead buffer as the field recipe
  does, re-runs the loop's handler span `[0x8001E784, 0x8001E7B8)` (the
  state-table lookup plus the handler's logic and draw) with each matched
  projection's matrix swapped for its interpolation at the GTE bridge, and
  submits the OT it built. No per-title field list, no per-mode call list;
  unmatched vertices keep the current frame's placement. The pad poll and
  sound tick before the handler are skipped; the sandbox drops device stores.
  The field recipe's netplay local view stays off under this method.

## Comparison (2026-10-27, R4 feat/projection-replay on psxrecomp ab9d181d)

Same race savestate (Grand Prix heat 1 from the grid, cross held), debug
tools build, this PC. Per-pass emulation-thread time is `render_pass_stats`
`avg_guest_ms`; on-screen frames are `tools/screen_frames.exe` (DXGI
Desktop Duplication, 15 s) at 2560x1440/120 with rate 120.

| Run | Guest draw ms / pass | Passes | Distinct frames on screen |
|---|---|---|---|
| fields, workers (shipped) | 4.51 on workers + 1.29 capture on main | 1638 worker draws / 15 s | **113.3/s** |
| fields, serial (`R4_DRAW_WORKERS=0`) | 5.84 | 319 / 15 s | 48/s (30 then 60) |
| projection, serial | 7.59 | 80 / 15 s (465 budget-shed) | 33.4/s |
| hidden window, display-matched 8K: fields serial | 11.91 | 71 / 8 s | — |
| hidden window, display-matched 8K: projection serial | 15.31 | 13 / 8 s (211 shed) | — |

Projection replay re-runs the handler's logic as well as its draw (the
span cannot start inside the handler without a native instruction site),
restores 2 MiB of RAM per pass and snapshots it per frame, and matches
about 4,600 projections per frame (3,700 interpolated per pass). It costs
about 30 % more emulation-thread time per pass than the field recipe and,
with no worker path, is shed by the host budget most of the time. The field
recipe with workers remains the default.

Verification of the prototype: `PSX_RENDER_PASS_VERIFY=1` 14 checks,
`verify_mismatch` 0, no span failures, device reads or watchdog aborts;
`render_pass_dump` in-between images sit between their neighbours (road
markings, walls, cars) with no cracks; per-frame fingerprints (judge
columns, `reset_on_load`) of a projection run equal a no-pass run over 337
frames, as the field recipe's do; zero dispatch misses. Evidence (local):
`C:/Users/Shokunin/AppData/Local/Temp/claude/.../scratchpad/bench/` runs
`proj1`, `projv`, `proj2`, `fields0`, `fields0b`, `rate30b`, `scr_*`.

A worker path for projection replay (private contexts own the GTE bridge
history) or a native instruction site at the handler's draw start would be
the next steps if this method is ever to compete.
