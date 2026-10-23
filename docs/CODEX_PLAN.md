# Multi-core drawing: plan and Codex prompt

Goal (owner, 2026-10-22): every separable stage of a frame on its own
threads, scaling with the cores the machine has (PC, Mac, Steam Deck, Steam
Frame), so 60 FPS holds under background load and 120/144 Hz and stereo VR
become possible. Combined with lean draw-only code, so each draw is cheaper
as well as parallel.

## Where things stand (2026-10-23)

| Stage | Thread today | State |
|---|---|---|
| Game logic (recompiled native code) | main | stays on main; it is one sequential program |
| Real-frame draw (track, cars, HUD) | main | target: draw workers; gated on isolation |
| In-between frames (60/120/144 Hz) | main, queued passes (#54) | target: one worker each |
| Track renderer inside one frame (0x8006F00C) | main | target: split across workers, later |
| GPU command parsing (DrawOTag) | main | stays on main: reads state the game keeps changing (docs/HOST_THREADING.md) |
| Seam strips | render thread | already off main; order-dependent, stays serial |
| GL rendering / present | render + present threads | done; GL state cache (#64) cut render thread 95% -> 38% |
| Disc reads | read-ahead worker (#64) | done |
| HD textures | preload pool + background decoder | done |

Costs per 30 Hz tick at 18x (busy PC): game logic + own draw about 21 ms;
each in-between redraw 10-12 ms, the course renderer 0x8006F00C about 8-9 ms
of it. 60 FPS currently measures 33-41 distinct frames/s on screen, so 30 is
the default (#61).

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

## Remaining body of work, in order

1. Gate: find the reader of `0x8010FFE8/F8`, keep the objects draw's sound
   calls on main, rerun until isolated == stock over a whole race; then Time
   Attack, split screen, attract demo, after-goal replay; then with default
   mods on (widescreen, Max Detail, PGXP).
2. Contexts: handle BIOS calls from draw code (clone the few BIOS functions
   or give memcpy/memset context versions); run 0x8006F00C, then the full
   Grand Prix draw sequence from `r4_interp.c`, adding roots for each
   indirect target the failure trail names.
3. Tests: 4 parallel contexts == serial on one snapshot; emitter tests;
   main-context speed vs baseline; fp_identity; lean vs full draw ms.
4. Worker pool: N draw workers fed a per-tick snapshot; in-between frames
   first (one worker each), command lists replayed by the render thread inside
   the queued-pass transaction (docs/RENDER_PASSES.md); a late worker drops an
   in-between frame, never stalls. Charge draw cycles to the guest clock.
5. 60 FPS default: on-screen >= 58 distinct frames/s average with no 30
   stretches while other jobs load the PC, resolution never below 1080p; then
   flip `r4.enhancement.frame-rate` back to 60 with numbers in the PR.
6. Real-frame draw on a worker, once the gate passes (main runs logic only).
7. 120/144 Hz: more in-between frames per tick, worker count from core count.
8. Split the track draw across workers to cut per-frame latency.
9. Stereo/VR: one worker per eye (psxrecomp docs/STEREO_RENDERING.md).
10. Upstream: open batched PRs from the topic branches; update
    `docs/UPSTREAM.md`.

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

```
You are continuing R4 (Ridge Racer Type 4 static recompilation) multi-core
drawing work on the Windows PC. Read, in order: CLAUDE.md, docs/HANDOFF.md,
docs/CODEX_PLAN.md (this plan), docs/UPSTREAM.md, then
docs/THREADED_CONTEXTS.md and docs/HOST_THREADING.md on their fork branches
and docs/DRAW_ISOLATION.md on R4 PR #65.

Goal: game logic stays on the main thread; the real-frame draw, every
in-between frame (60/120/144 Hz) and later split track rendering and stereo
views run on worker threads using lean draw-only clones (no cycle/icache/
IRQ/debug code, PGXP kept), scaling with the machine's cores. Main-thread
behaviour must stay byte-identical (fp_identity, headless smoke 0 dispatch
misses).

Work the "Remaining body of work" list in docs/CODEX_PLAN.md in order. Steps
1 and 2 are independent and can run in parallel. Framework changes go to
topic branches on the fork tetrisgm/psxrecomp, merged into r4/main only when
verified (fetch first, fast-forward push); R4 changes via PRs you merge
yourself. Record each fork delta in docs/UPSTREAM.md and each pin in
docs/framework_pin_history.md. Measure on screen with screen_frames before
claiming FPS. Follow "Rules that bit us". Do not release; the owner gives the
go and the version.
```
