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
The development branch offers all requested rates, with 60 FPS by default.
Performance measurements validate the implementation and expose unfinished
work; they do not change that requested default.

## Where things stand (2026-10-23)

The extra-frame worker milestone is locally installed as a development build.
At default 60 FPS, four private draw contexts preserve the working mod's exact
interpolation sequence, with eight bounded presenter slots and dynamic
resolution starting at its 1200-line floor. `analysis/worker-cadence-v42`
measured 902 presents/15.031 s (60.0/s), no interval over 25 ms during the
sample, no timed refusal, and zero worker faults or dispatch misses. The
readback trace `analysis/worker-trace-v39.csv` confirmed 180 changed images
in three seconds with ordered, unique provenance; full-frame equality is in
`analysis/worker-pixels-v13`. PC project tests: 31/31; Mac: 28/28 available
without the disc. Fork `r4/main` is pushed at `688380ef`, game C regeneration
is unchanged. The pinned build passed 900 distinct presents in 15 seconds;
the installed binary passed a five-second check. The Windows render-thread
priority change can be disabled with `PSX_RENDER_THREAD_PRIORITY=0`.
Presenter-owned capture avoids desktop interference. Higher-rate measurements
show 90 Hz near target but 100/120/144 Hz below target; render-thread PGXP seam
snapping is the largest sampled cost at 144 Hz. Details: `docs/HANDOFF.md`.

| Stage | Thread today | State |
|---|---|---|
| Game logic (recompiled native code) | main | stays on main; it is one sequential program |
| Real-frame draw (track, cars, HUD) | main | target: draw workers; gated on isolation |
| Timestamped interpolated frames | four draw workers | 60 Hz milestone installed; 90 Hz near target, 100/120/144 below target |
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

The first integration reuses `r4_interp.c`'s working 60 FPS draw sequence and
interpolation fields unchanged. Private contexts execute that recipe; main
admits its captured output without waiting. The serial implementation remains
the correctness reference. Real-frame offload and track decomposition do not
block proving parallel intermediate frames.

- Contexts: OpenBIOS qualification, immutable GTE/PGXP snapshots, the full
  default draw recipe, four-worker receipts and full-frame pixel equality pass.
- Isolation: stock Grand Prix whole-race comparison passes 18,101 ticks;
  other modes and default enhancements remain. Default base/base restore
  exposes SIO sampling nondeterminism before isolation is enabled; the cause
  is still being investigated.
- Output: rational timestamps, bounded workers, ordered presentation and
  private render transactions pass the short 60 Hz race checks. Measure higher
  requested rates after the fork/pin lands; never alter the 30 Hz logic clock.
- Fork: `r4/main` is verified and pushed; the pinned R4 build passes PC/Mac
  tests and is installed. Optimize render throughput and finish isolation
  before landing draft R4 PR #69.

Current receipts and checkout ownership: `docs/HANDOFF.md`; framework topic
notes: `docs/THREADED_CONTEXTS.md`, `docs/RENDER_PASSES.md`, `docs/HOST_THREADING.md`
in their respective branches.

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

Owner update (2026-10-23): bound performance samples to 15 seconds and automated
runs to 30 seconds. Reuse build-compatible race savestates and skip intros.
Brief visible race checks provide owner feedback. Do not let exhaustive race
comparisons block completing the core worker, threading and overhead work;
report coverage limits explicitly.

Verify Grand Prix, Time Attack, split screen, attract demo and after-goal
replay, both baseline and default mods. Require zero dispatch misses, whole-
race identity where already recorded, bounded isolation checks for remaining
modes, four concurrent contexts equal to serial, emitter
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

## Worker integration references

- `src/mods/r4_interp_workers.h`: owned interpolation values, snapshot lifetime,
  bounded workers, immutable GPU/PGXP receipts and generation retirement.
- `src/mods/r4_draw_mods.c`: private adapters for default enhancement hooks;
  unsupported optional hooks retain serial fallback.
- `src/mods/r4_interp_verify.h`: exact original draw versus private serial/four
  workers; full-resolution GPU replay pixel check remains under verification.
- Framework `docs/THREADED_CONTEXTS.md`: private precision state, geometry-cache
  index and track partition constraints. Real-frame replacement also needs
  faithful cycle/IRQ accounting and ordered main-thread sound/RNG calls.
- Framework `runtime/src/render_pass.c` and `gpu_gl_renderer.c`: main-thread
  command admission, immutable texture sources, timed presentation and drops.

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
