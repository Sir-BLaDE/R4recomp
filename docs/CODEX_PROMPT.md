# Codex prompt: R4 multi-core drawing (self-contained)

Paste everything inside the fence into Codex.

````
You are taking over performance work on R4, a static recompilation of
"R4: Ridge Racer Type 4" (PS1, USA, SLUS-00797) into native code. The game's
MIPS code is translated to C by the psxrecomp framework and compiled; nothing
is emulated instruction by instruction. You work on the owner's Windows 11
PC (DESKTOP-BAKIEMJ, RTX GPU, 8K display). The owner is "Shokunin" (GitHub
tetrisgm). Be concise, work in parallel where pieces are independent, and
keep going until the work below is done or you hit a real decision for the
owner.

## 1. Repos and setup

- R4 game repo: https://github.com/tetrisgm/RidgeRacerType4Recomp (branch
  master). An existing checkout is at C:\Users\Shokunin\dev\ridgeracertype4;
  pull it, or clone fresh to C:\Users\Shokunin\dev\r4-codex with
  `git clone --recursive`.
- Framework: submodule `psxrecomp/` = our fork
  https://github.com/tetrisgm/psxrecomp, branch r4/main (upstream is
  https://github.com/RetroPortingToolKit/psxrecomp, maintainer "mstan" /
  Gamemaster). Launcher: submodule `recomp-ui/` =
  https://github.com/tetrisgm/recomp-launcher, branch r4/main.
  Run `git submodule update --init --recursive`.
- Disc (local only, never commit): copy or junction
  C:\Users\Shokunin\dev\ridgeracertype4\disc into the new checkout as disc\
  (it holds "R4 - Ridge Racer Type 4 (USA).cue/.bin", SLUS_007.97,
  SYSTEM.CNF). In Git Bash `ln -s` copies directories; use
  `cmd /c mklink /J disc C:\Users\Shokunin\dev\ridgeracertype4\disc`.
  Disc identity: DISC.md.
- Toolchain: MSYS2 MinGW64 at C:\msys64 (gcc, cmake, ninja, ccache).
  Build from Git Bash with
  `export PATH="/c/msys64/mingw64/bin:/c/msys64/usr/bin:$PATH"`.
  Never use `bash -l` (it strips USERPROFILE/LOCALAPPDATA and ccache fails).
  If CMake reports "detected version of Ninja ()", just retry.
- Python: always C:\Users\Shokunin\AppData\Local\Programs\Python\Python312\python.exe
  (MSYS python breaks tools/regen.sh because of HOME).
- Configure a dev build:
  `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=ON -DR4_BUILD_TESTS=ON`
  then `cmake --build build` and `cd build && ctest` (21+ tests pass).
  PSX_DEBUG_TOOLS=ON gives the TCP debug server (`--debug-port N`); release
  zips have none.
- Run headless: `build/r4-runtime.exe --headless --no-launcher --disc "<path>.cue" --debug-port 51xx`
  from its own working directory (the runtime writes reports there).
  `python tools/smoke.py OUT_DIR --port 51xx` drives to a race with turbo
  and prints dispatch misses (must be 0).
- Regenerate game C after seed/annotation/[recompiler]/codegen changes:
  build emitters, then
  `python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . --no-toolchain-download`.
  Never hand-edit generated/. BIOS: `psxrecomp/tools/regen_bios.sh --config bios/OpenBIOS.toml`,
  commit generated/OpenBIOS.emitter.sha (check: psxrecomp/tools/ci/check_bios_stamps.sh OpenBIOS).
- Release zip: `tools/package_release.sh HEAD` from the MSYS2 MINGW64 shell
  (`MSYSTEM=MINGW64 CHERE_INVOKING=1 /c/msys64/usr/bin/bash -lc '...'` with
  "/c/Program Files/Git/cmd" on PATH); output under build-release-clone/dist.
  The owner plays C:\Users\Shokunin\Games\R4 (desktop shortcut "R4");
  reinstall by unzipping over it (keep settings.toml, saves, *.ini).

## 2. Process rules (owner decisions)

- Fork model: framework work lands on the fork's r4/main first; R4 pins it.
  Every change is its own topic branch (fix/<name>, feat/<name>) based on the
  upstream master commit r4/main last synced, generic for any PS1 game (no
  R4-only hacks), so it can go upstream unchanged. Merge into r4/main only
  when verified; fetch first; fast-forward push only, to the fork only.
  Never push branches to RetroPortingToolKit/psxrecomp except heads of our
  own open PRs; never ask the maintainer for quick reviews.
- R4 changes: branch, PR, merge yourself (`gh pr merge --merge`). Each pin
  bump adds a row to docs/framework_pin_history.md; each fork delta a row in
  docs/UPSTREAM.md. Stage paths explicitly: `git commit -a` picks up a moved
  psxrecomp gitlink by accident.
- Merge upstream master into r4/main at least weekly and before releases.
- No release, tag or publish without the owner's go and version number.
- psxrecomp default behaviour stays faithful; elective unfaithful features
  are opt-in. Correctness and pure-performance fixes with identical output
  are default-on with an off switch.
- Owner display decisions: 18x internal resolution (Match display up to 8K,
  supersample 1.5 below 4K), dynamic resolution never below 1080p, PGXP on
  (with depth buffer, colour correction, fine seams + seam snapping),
  widescreen on, 30 FPS default until 60 holds steadily.
- Credit "Shokunin", never a legal name. Commit trailer:
  `Co-Authored-By: <your model> <noreply@...>` as your harness requires.

## 3. Safety rules for runs (these bit us)

- Never run `r4-runtime --help`: it launches the game visibly.
- No visible intro runs. Make race savestates headless + turbo; open a
  window only to load such a savestate directly, briefly.
- Other jobs share the PC (the owner's MediaMedia work). Never
  `taskkill /IM r4-runtime.exe`; kill only PIDs you started. One working
  dir and one debug port per run.
- Savestates are build-specific when cpu/gte/pgxp sources change; make
  fresh ones per build.
- After every run, resolve dispatch misses before any other debugging.

## 4. State as of 2026-10-23

Landed on R4 master: PAL support (#49), race HUD / car effects / lighting
preset, opt-in (#50, on-screen fixes #62), 1080p dynres floor (#57), fork
model (#58), upstream review fixes (#59), upstream sync (#60), 60 FPS as a
setting with 30 the default (#54, #61), PGXP seam snapping (#63), host
threading (#64), handoff docs (#66).

Upstream psxrecomp PRs still open (ours): #723 Windows GL pacing, #736 HD
preload, #737 live resolution (review fixes pushed, awaiting re-review),
#727 render passes (needs re-scoping to feat/render-pass-hd plus a
digest-equality test). Contributor PRs #710, #716 are in r4/main.

Thread map today:
| Stage | Thread | Next |
|---|---|---|
| Game logic (recompiled code) | main | stays: one sequential program |
| Real-frame draw (track, cars, HUD) | main | draw workers, gated on isolation |
| In-between frames (60/120/144 Hz) | main, queued render passes | one worker each |
| Course renderer inside a frame (0x8006F00C, ~8-9 ms) | main | split across workers later |
| GPU command parsing (DrawOTag, ~0.6 ms) | main | stays: reads live game state |
| Seam strips (~1.3 ms) | render thread | stays serial (order-dependent) |
| GL render / present | render + present threads | done; GL state cache cut render thread 95% -> 38% at 18x |
| Disc reads, HD textures | workers | done |

Costs per 30 Hz tick at 18x on the loaded PC: logic + own draw ~21 ms
(race game thread now ~7 ms + draw); each in-between redraw 10-12 ms. 60 FPS
measured 33-41 distinct frames/s on screen (60/30 stretches), hence the 30
default. Recompiled functions carry overhead per guest instruction: PGXP
~30%, cycle/icache model 13-15%, GTE ~10%, memory calls; draw-only work
doesn't need the cycle model or debug hooks.

## 5. Work in flight (branches)

A. fork `feat/threaded-contexts` (head 27ea6673; doc
   docs/THREADED_CONTEXTS.md on the branch). CPUState gains `ctx` (NULL on
   main). `[threaded_draw]` roots in game.toml generate generated/<stem>_draw.c:
   lean clones of the roots and everything reachable (follow return links
   too), without cycle/icache/IRQ/debug/cosim code; PGXP kept. Each draw
   context: RAM + scratchpad copy from a snapshot (0.3 ms), own GTE and PGXP
   engine, GPU writes/DMA captured per context with source addresses; fails
   safe (stops with a reason) on unknown targets, device reads, BIOS calls,
   wait loops (block budget). Debug command `ctx_draw` runs a call sequence
   serially and on N threads and compares; `full=1` times the full code.
   Works up to the first BIOS call (0xA0 from 0x80096620): 4 threads ==
   serial. R4 game.toml roots diff:
   C:\Users\Shokunin\dev\r4-ctx-work\r4-game-toml.diff; merge resolution
   with r4/main (gte.cpp) on local branch int/ctx-r4 in
   C:\Users\Shokunin\dev\psx-ctx. The main build skips savestate loads if
   the interrupt check is removed (loads, debug server, netplay, rewind are
   serviced there), so only the draw file drops it. VSync(-1) polls Timer 1:
   contexts advance it every 64 reads.
B. fork `feat/draw-isolation-gate` (6f8b4621) + R4 draft PR #65
   (docs/DRAW_ISOLATION.md, src/mods/r4_draw_isolation.c, package
   r4.debug.draw-isolation off by default, tools/draw_iso_gate.py). Runs
   race draw calls on a private RAM/scratchpad/GTE copy, merges back, hands
   frame output to main at VSync(0), logs per-tick state and frame hashes.
   Results (Grand Prix, 1,500 frames): stock vs stock identical; nested
   without isolation identical over 761 ticks; isolated identical for 130
   ticks, then diverges in sound state 0x8010FFE8/0x8010FFF8 (likely sound
   calls 0x8004F520 / 0x80051B00 inside the objects draw 0x80074AD8).
   Classification: OTs, packet heap, HUD prims, DRAWENV/DISPENV, scratch
   1F800000/1F800004 double-buffered (handoff); other scratchpad, GTE,
   view temporaries draw-private; dead stack garbage only; sound state feeds
   logic. Main must keep input, sound tick, CD polling, DrawSync/VSync/
   PutDispEnv/PutDrawEnv/DrawOTag, logic, and the draw's sound calls; a
   threaded build must charge draw cycles to the guest clock and give HUD
   calls the logic state of their call point.
C. fork `feat/host-threading` (merged in r4/main; doc docs/HOST_THREADING.md).
   Open items: on-screen distinct-frame count before/after; one ring command
   per triangle instead of ~6; cache gpu_get_display_info. Profiling:
   PSX_HOST_SAMPLER_THREAD=render, PSX_HOST_SAMPLER_CALLERS=1|2,
   host_profile "phase":4; tools/host_profile.py needs
   `--nm C:/msys64/mingw64/bin/nm.exe`.

Measuring on screen: C:\Users\Shokunin\dev\r4-60fps\analysis\screen has
tools/screen_frames.c (DXGI distinct-frame counter, built as
tools/screen_frames.exe there), py/mksaves.py and py/racestart.py (race
savestates), and an in-game test autodriver (src/mods/r4_autodrive.h,
R4_AUTODRIVE=1, local only). psxrecomp/tools/fp_identity.py compares frame
fingerprints between builds.

## 6. Remaining work, in order (1 and 2 can run in parallel)

1. Gate (B): find the reader of 0x8010FFE8/F8, keep the objects draw's
   sound calls on main, rerun until isolated == stock over a whole race;
   then Time Attack, split screen, attract demo, after-goal replay; then
   with default mods on. Merge PR #65 when it passes.
2. Contexts (A): handle BIOS calls from draw code (clone the few BIOS
   functions involved or give memcpy/memset context versions); run
   0x8006F00C, then the full Grand Prix draw sequence from r4_interp.c,
   adding roots for each indirect target the failure trail names.
3. Tests: 4 parallel contexts == serial; emitter tests; main-context speed
   vs baseline; fp_identity; lean vs full per-draw ms. Then merge A into
   r4/main and pin R4 (commit the [threaded_draw] roots and _draw.c).
4. Worker pool: N draw workers fed a per-tick snapshot; in-between frames
   first (one worker each); command lists replayed on the render thread
   inside the queued-pass transaction (psxrecomp docs/RENDER_PASSES.md); a
   late worker drops an in-between frame, never stalls; charge draw cycles
   to the guest clock.
5. 60 FPS default: >= 58 distinct frames/s average on screen, no 30
   stretches, with the owner's other jobs running, resolution never below
   1080p; then set r4.enhancement.frame-rate option `rate` default "60" in
   mods/preloaded/packages/r4.enhancement.frame-rate/1.0.0/manifest.toml and
   tests/test_r4_defaults.py, with numbers in the PR.
6. Real-frame draw on a worker once the gate passes (main runs logic only).
7. 120/144 Hz: more in-between frames per tick; worker count from cores.
8. Split the track draw across workers to cut per-frame latency.
9. Stereo/VR: one worker per eye (psxrecomp docs/STEREO_RENDERING.md),
   for the Steam Frame.
10. Host-threading open items (C).
11. Upstream: batched PRs from the topic branches; keep docs/UPSTREAM.md
    current. Rebuild and reinstall the owner's R4 after each milestone.

Keep docs/HANDOFF.md (current work, blockers, references) and
docs/CODEX_PLAN.md current as you go. Report to the owner in plain
language: what changed, measured numbers, what's unverified.
````
