# Handoff

## Current work (2026-10-23)

Released: v0.1.0 only. A release needs the owner's go and version number.

Framework: R4 pins the fork `tetrisgm/psxrecomp` `r4/main` (CLAUDE.md fork
model). `docs/UPSTREAM.md` lists every fork delta and its upstream PR;
`docs/framework_pin_history.md` every pin. Owner's install:
`C:\Users\Shokunin\Games\R4` (desktop shortcut "R4"), built from `dea73b5`.

Landed 2026-10-22: PAL (#49), race HUD/effects/lighting (#50, fixes #62),
1080p dynres floor (#57), fork model (#58), review fixes (#59), upstream sync
(#60), 60 FPS as a setting with 30 the default (#54, #61), PGXP seam
snapping (#63), host threading (#64; render thread 95% -> 38% busy at 18x).

In progress: integrated threaded rendering. Main runs the base 30 Hz game
simulation; rendering/presentation target selectable 60 (default), 90, 100,
120 and 144 FPS through timestamped snapshot interpolation. The development branch now offers all requested rates and defaults to 60 FPS. A possible 60 Hz simulation option is separate,
unproven and not required. Isolation, contexts, immutable mod/PGXP inputs,
worker pool, scheduling/pacing, track decomposition and host throughput
share the verification plan.
First integration target: execute the working 60 FPS mod's existing draw
sequence on private workers, then schedule the same sequence at 60/90/100/120/144
output timestamps. Keep its serial path as the reference and fallback.
Original-frame offload and track decomposition follow this proof in parallel.
Plan: `docs/CODEX_PLAN.md`.
Owner verification budget: 15-second performance samples, 30-second automated
runs, build-compatible race savestates and intro skipping. Stop long race
comparisons; prioritize core implementation and brief visible race feedback.
Pixel correctness now passes with default seam snapping: v13 full/full and
full/private compare all 7668x4320 pixels exactly, 19,669 command receipts
and four parallel contexts match. Receipt: `analysis/worker-pixels-v13`.
The cause was seam-snap history leaking across discarded passes; depth
checkpointing also fixes an independently proven transaction defect.
OpenBIOS A0/2F private execution is fixed (`8f931e66`); moving-race v10 runs
15 seconds with zero main dispatch misses and worker failures. The prior
visible v7 sample measured 29.1 distinct frames/s, not accepted for installation.
Output-grid lookahead and generation lifetime fixes are integrated locally.
No worker milestone installation has occurred.
Temporal display ownership and timestamp sorting fixed two ordering defects;
actual presenter-pixel tests found and fixed inherited GL raster state. The
current 4-slot hidden 15-second probe (`analysis/worker-grid-v25`) presents
401 images (26.7/s), zero worker faults/misses, and only four expired main
deadlines after exact-grid skipping. HD resource invalidations reached zero;
the remaining generated-copy guard rejects valid work (932 GPU commands) and
render-thread deadlines still miss. It does not meet the 60 FPS target.
Desktop/GDI capture sampled the wrong
surface and its distinct-frame numbers are invalid for recent probes.

Active checkouts (no new worktrees): root R4 `feat/threaded-rendering`, framework
local `int/threaded-rendering` (never a landing source); `r4-ctx`/`psx-ctx` for
contexts and private mod hooks; `r4-iso` for isolation; `psx-hostthr` for output
scheduling/replay. Topic commits remain separate from local integration.

Verified checkpoints:
- Baseline A/A: 12,000 frame fingerprints exactly equal, zero misses;
  local receipts `analysis/perf-baseline/base-{a,b}.json`.
- Integrated main-context path also matches those 12,000 frames exactly,
  zero misses: `analysis/perf-baseline/context-main.json`.
- First async integration builds pass all 31 project tests on PC and Mac.
  This does not yet verify actual worker output or screen cadence.
- Exact existing Grand Prix interpolation recipe: 2,343 command/precision
  receipts match full versus private serial and four workers. Zero dispatch
  misses and worker failures. Receipt: `analysis/worker-exact-20261023-b`.
  Full-resolution pixel comparison and cadence remain pending.
- Stock Grand Prix isolation: 18,101 ticks through TIMEOVER match base/nested/
  isolated; zero misses. Nested also matches 32,767 shared frame fingerprints.
  Receipt: `C:/Users/Shokunin/dev/r4-iso-runs/sound-rng-v4-20261023`.
- Private BIOS memcpy/memset versus recompiled OpenBIOS, four-context GTE/PGXP,
  worker ownership/expiry and R4 private access fixtures pass PC and Mac.
- Timestamp planner, nonblocking render transactions and exact-deadline hidden
  GL presentation pass PC and Mac. These are component checks, not measured
  game FPS. Framework topics document their receipts.


## Owner decisions

- Display: widescreen Fit, Match display, supersample 1.5, FXAA off, dynres
  floor = 1080p, render + present threads, Smooth motion off (removed,
  owner 2026-10-20), PGXP depth buffer / colour correction / fine seams. All in `game.toml`.
- `guest_cycle_scale = 2` (races, Max Detail gate).
- HD HUD bundled, on by default, credited to Kuid0us.
- Online: 2-4 players, each on their own full-screen view.
- Rewind off in split screen and in every online session.
- Release model: bundled compiled zips (#18). Version: TBD.
- Graphics presets: low-end machines start Low (extras off); others Ultra
  with dynamic resolution, frame rate and aspect.
- Modern controls: NeGcon analog gas/brake/steering, forgiving curves.
- New launcher: tetrisgm/recomp-launcher replaces recomp-ui, minimal R4 menus.

## Blockers

- Integration: full draw target closure, default enhancement hook snapshots,
  ordered GPU/PGXP metadata, and worker result admission are still being wired.
  The existing mod recipe now feeds a bounded worker pool; exact serial versus
  four-worker receipt verification is next. No integrated distinct-frame or
  visual acceptance yet.
- Gate: remaining modes unverified. Default-mod base/base restore is not yet
  deterministic at the first SIO sample; disabling batching did not resolve it.
  The isolated difference at tick 118 was traced to packet-heap handoff used
  by the detail governor; its fix is undergoing the extended mode checks.
- Release: owner picks the version and gives the go.
- Online battle keeps its experimental switch until psxrecomp reserves link memory per netplay session.

## References

- Disc identity: `DISC.md` (Redump 11608).
- Framework/UI pins: `docs/framework_pin_history.md`.
- Widescreen: `docs/WIDESCREEN.md`; cull lists `tools/r4_ws_scan.py`.
- Display defaults: `README.md` (On by default); `tests/test_r4_defaults.py`,
  `tools/check_pin_keys.py`.
- HD HUD: `docs/HD_HUD.md`, `tools/r4_hd_hud_pack.py`.
- Internal resolution presets: `README.md` (Internal resolution), `tools/res_matrix.py`.
- Release: `tools/package_release.sh` (gates: OpenBIOS only, HD HUD pack exact, pin keys).
- Verification loop: `tools/run_r4.sh build` + `tools/smoke.py <out-dir>`;
  rollback determinism: `PSX_RB_SELFCHECK=1 PSX_RB_SELFCHECK_MASH=1`.
- A/B guest identity (mod off, warm vs cold shards):
  `psxrecomp/tools/fp_identity.py` with
  `--launch 'tools/run_r4.sh {build} --debug-port {port} {headless}'`.
