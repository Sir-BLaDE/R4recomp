# Multi-core drawing: plan and Codex prompt

Goal (owner clarification, 2026-10-22): integrate threaded rendering with
30 Hz base game simulation on the main thread and independent rendering
and presentation at selectable 60 (default), 90, 100, 120 and 144 FPS.
Schedule each output timestamp against timestamped simulation snapshots,
interpolating the appropriate pair. Arbitrary and noninteger ratios such as
100/30 and 144/30 are part of this design. Worker capacity follows available
cores and measured workload; rates do not imply a fixed number of extra
frames per tick or one core per rate.

A possible 60 Hz simulation mode is a separate, unproven option. It is not
required for this work and must never be coupled to the rendering FPS setting.
The current code defaults to 30 FPS; the owner target is 60 FPS by default.
Performance measurements validate the implementation and expose unfinished
work; they do not change that requested default.

## Where things stand (2026-10-23)

| Stage | Thread today | State |
|---|---|---|
| Game logic (recompiled native code) | main | stays on main; it is one sequential program |
| Real-frame draw (track, cars, HUD) | main | target: draw workers; gated on isolation |
| Timestamped interpolated frames | main, queued passes (#54) | target: bounded shared draw-worker pool |
| Track renderer inside one frame (0x8006F00C) | main | target: decompose ordered track work across workers |
| GPU command parsing (DrawOTag) | main | stays on main: reads state the game keeps changing (docs/HOST_THREADING.md) |
| Seam strips | render thread | already off main; order-dependent, stays serial |
| GL rendering / present | render + present threads | done; GL state cache (#64) cut render thread 95% -> 38% |
| Disc reads | read-ahead worker (#64) | done |
| HD textures | preload pool + background decoder | done |

Historical measurements from the prior build, per 30 Hz tick at 18x (busy PC): game logic + own draw about 21 ms;
each in-between redraw 10-12 ms, the course renderer 0x8006F00C about 8-9 ms
of it. 60 FPS measured 33-41 distinct frames/s on screen, which motivated the current code default of 30 (#61). These numbers are
not measurements of the planned integrated pipeline.

## Work in flight

1. **Threaded contexts + lean draw clones**: fork branch
   `feat/threaded-contexts` (head 27ea6673), `docs/THREADED_CONTEXTS.md` on the
   branch. Per-context RAM/scratchpad/GTE/PGXP, GPU writes captured per
   context, `[threaded_draw]` roots in `game.toml` generate
   `generated/<stem>_draw.c` without cycle/icache/IRQ/debug code (PGXP kept).
   Main code unchanged. Debug command `ctx_draw` runs a call sequence serially
   and on N threads and compares. Works up to the first BIOS call
   (0xA0 from 0x80096620). R4 `game.toml` diff:
   `C:\Users\Shokunin\dev\r4-ctx-work\r4-game-toml.diff`.
2. **Draw-isolation gate**: fork branch `feat/draw-isolation-gate`, R4 draft
   PR #65, `docs/DRAW_ISOLATION.md`. Runs the race draw on a private copy and
   compares state/fingerprints tick by tick against stock. Identical for 130
   ticks, then diverges in sound state `0x8010FFE8/F8` (likely sound-effect
   calls 0x8004F520 / 0x80051B00 inside the objects draw 0x80074AD8).
3. **Host threading follow-ups**: fork `feat/host-threading`,
   `docs/HOST_THREADING.md`: on-screen count not yet run; one ring command per
   triangle instead of about 6; cache `gpu_get_display_info`.

## Integrated workstreams

These pieces share contracts and verification. Develop independent pieces in
parallel, then verify them together; they are not a ladder of unrelated FPS
milestones.

- **Isolation and snapshots:** finish the sound-state reader investigation
  (`0x8010FFE8/F8`) and keep sound/input/device effects on main. Define the
  state at each draw/HUD call point, immutable snapshot lifetimes and ordered
  real-frame handoff. The gate covers full races and every supported mode.
- **Lean contexts:** complete draw BIOS support and indirect-target closure,
  including `0x8006F00C` and the full mode sequences in `src/mods/r4_interp.c`.
  Keep the main execution path intact. Contexts supply private RAM,
  scratchpad, GTE and PGXP; fail closed on unsupported execution.
- **Immutable rendering inputs:** carry mod activation/options, camera pose,
  widescreen and detail settings, packet metadata and PGXP precision with each
  job. Draw hooks must use context memory and private host state. Establish
  serial captured-output equality before using the same path concurrently.
- **Worker pool and render replay:** bounded jobs share immutable snapshots;
  workers return complete command data to the ordered render transaction.
  Keep live GPU parsing on main until its state dependencies are isolated.
  Replace real-frame draw only after isolation and guest-clock accounting
  pass. Extra interpolated draws do not advance authoritative guest time;
  replaced real-frame draw must preserve its guest-cycle effects.
- **Timestamp scheduling and pacing:** choose interpolation phase from output
  timestamps and simulation history for all requested rates, including
  noninteger ratios. Use explicit generation/deadline tokens, bounded queues
  and session epochs. Drop late optional output without waiting or changing
  simulation speed; preserve stock-frame fallback. Rendering, presentation
  and input/logic timing remain independently paced.
- **Track draw decomposition and host throughput:** split independent course
  work while preserving packet/primitive ordering; measure granularity and
  merge cost. Pursue the host-threading ring-record and display-info cache
  improvements alongside the pool and scheduler.

## Shared verification and delivery

Verify Grand Prix, Time Attack, split screen, attract demo and after-goal
replay, both baseline and default mods. Require zero dispatch misses, whole-
race isolation identity, four concurrent contexts equal to serial, emitter
checks, `fp_identity`, and unchanged main-context behavior/performance.
Measure lean/full draw time, snapshot cost, worker latency, render/present
throughput and on-screen distinct frames/cadence under background load at
60/90/100/120/144 FPS. Include late jobs, rate changes, snapshot retirement,
load/reset/rewind and mod changes. Resolution must never fall below 1080p.

Implement the requested 60 FPS default with the selectable rates in the
frame-rate manifest and `tests/test_r4_defaults.py`; report any measured
shortfall openly. There is no separate >=58 FPS gate redefining the owner's
desired default. Keep fork deltas and pin history current, land coherent
verified changes, and rebuild/reinstall at milestones. Release/tag/publish
still needs the owner's go and version.

## Worker integration audit references

- `src/mods/r4_interp.c:r4_pass_point` is the existing VSync capture point;
  its blend points into mutable `R.prev/R.cur`. Copy values into each job and
  replace global memory helpers and `R.in_pass` with context-local execution.
- Context branch `runtime/src/gte.cpp:s_render_pose` and FOV/widescreen
  globals need snapshot ownership. `runtime/include/pgxp_ctx.h` currently
  omits RAM shadows; `psx_ctx_precise_vertex` queries final shadow state.
  Preserve precision for preexisting and reused packet addresses at capture.
- Context-safe hooks must retain behavior from `r4_widescreen_plugin.c`,
  `r4_max_detail_plugin.c`, `r4_camera_look_plugin.c`,
  `r4_hide_rear_view_mirror.c` and `r4_race_hud.cpp` under `src/mods/`.
- Framework `runtime/src/render_pass.c` owns singleton checkpoint/plan state;
  its current API cannot run on workers. `runtime/src/gpu_gl_renderer.c`
  queues `RTH_PASS_BEGIN/END`, but asynchronous results need explicit
  generation/deadline ownership. `PsxCtxGpuWord` alone does not carry all
  parser inputs; `runtime/src/gpu.c` also reads RAM and host packet metadata.

## Rules that bit us

- Never `r4-runtime --help` (it launches the game). No visible intro runs:
  make race savestates headless + turbo; open a window only to load one.
- Several runs share the PC: kill only your own PIDs, one working dir and
  one debug port per run.
- Build in Git Bash with `PATH=/c/msys64/mingw64/bin:/c/msys64/usr/bin:$PATH`;
  `bash -l` strips USERPROFILE/LOCALAPPDATA and ccache fails. Release zips:
  `tools/package_release.sh` from the MSYS2 MINGW64 shell with Git on PATH.
- Windows Python: `C:\Users\Shokunin\AppData\Local\Programs\Python\Python312\python.exe`.
- `git commit -a` in R4 picks up a moved `psxrecomp` gitlink; stage paths.
- Savestates are build-specific when cpu/gte/pgxp sources change.
- Never hand-edit `generated/`; regenerate.

## Prompt for Codex

Self-contained version (setup, rules, full state): `docs/CODEX_PROMPT.md`.

```
You are continuing R4 (Ridge Racer Type 4 static recompilation) multi-core
drawing work on the Windows PC. Read, in order: CLAUDE.md, docs/HANDOFF.md,
docs/CODEX_PLAN.md (this plan), docs/UPSTREAM.md, then
docs/THREADED_CONTEXTS.md and docs/HOST_THREADING.md on their fork branches
and docs/DRAW_ISOLATION.md on R4 PR #65.

Goal: keep base game simulation at 30 Hz on main, and independently render
and present at selectable 60 (default), 90, 100, 120 and 144 FPS. Interpolate
immutable snapshots at output timestamps, including noninteger rate ratios.
Use a bounded worker pool and lean draw clones; integrate isolation, hook/
PGXP ownership, timestamp scheduling, pacing, track decomposition and host
throughput. A possible 60 Hz simulation mode is separate and unproven.
Main-thread behavior must stay byte-identical (fp_identity, zero misses).

Work the integrated workstreams and shared verification in this plan, in
parallel where independent. Framework changes go to
topic branches on the fork tetrisgm/psxrecomp, merged into r4/main only when
verified (fetch first, fast-forward push); R4 changes via PRs you merge
yourself. Record each fork delta in docs/UPSTREAM.md and each pin in
docs/framework_pin_history.md. Measure on screen with screen_frames before
claiming FPS. Follow "Rules that bit us". Do not release; the owner gives the
go and the version.
```
