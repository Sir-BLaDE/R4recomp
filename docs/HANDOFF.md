# Handoff

## Current work (2026-10-23)

Release-candidate boundary (owner, 2026-10-23): the installed 60 FPS
extra-frame worker path is complete for this milestone. Main runs game logic
at 30 Hz; four private workers prepare additional frames in the working mod's
order. The owner saw the race and reported no shaking or out-of-order frames.
The 60 FPS short race, ordered-frame, bloom, seam-identity, project-test and
zero-dispatch-miss checks below passed. This is a development installation,
not a new release; release, tag and publication still require the owner's go
and version number.

Real-frame draw offload and sustained 90/100/120/144 FPS are follow-up work,
not blockers for this candidate. Those rates are selectable, but short probes
do not establish target throughput above 60. The isolation gate is sufficient
for the installed extra-frame path; whole-race equality for every mode and
default-mod combination remains unverified. The timed real-frame, presenter
composition and HUD handoff branches below are local checkpoints only.

Released: v0.1.0 only. R4 master contains the developer-only isolation gate
(PR #65) and four extra-frame draw workers (PR #69). The fork pin is
`990ffb00` (queued-frame postfx provenance; R4 PR #77). The development build is installed at
`C:\Users\Shokunin\Games\R4` (SHA-256 `FC9009D77707B6D1A4CD04DB7C2DB6BE31F0C6E5BAFB31C2C55B8AFD65F6E822`);
the previous executable is backed up at
`C:\Users\Shokunin\Games\R4-dev-backup-20261023-postfx`. Settings, saves and
bindings were preserved. This is not a release or tag.

The game still simulates at 30 Hz on main. Four private contexts prepare the
working 60 FPS mod's exact in-between draw sequence; 60 is the default and
30/90/100/120/144 remain selectable. A fresh master-build race state was made
headless in bounded stages (`analysis/merged-prep-v99`, slot 2, zero dispatch
misses). The installed master executable then ran visibly for 15 seconds:
`analysis/worker-master-visible-v100` recorded 900 distinct ordered frames,
no gap over 25 ms, refusal, render lateness or dispatch miss. Windows project
tests pass 32/32; Mac tests available without the disc pass 29/29. Full 8K
private-draw pixel identity is in `analysis/worker-pixels-v13`.
After the seam pin, `analysis/seam-master-visible-v6` ran visibly for ten
seconds: each second after startup showed 60 distinct frames, with 302 worker
jobs admitted, zero drops/failures and zero dispatch misses. Required
regeneration added 14 private draw entry hooks; the short exact-draw receipt
`analysis/seam-pin60-v5` passed. Mac built the pin and passed 29/29 tests.

Performance checks must set `PSX_DISPLAY_RING=0`; the debug ring otherwise
reads full VRAM every game frame and understates visible throughput. Corrected
short hidden-window checks reached 90 Hz (271 distinct frames in the last
three seconds), but 100/120/144 fell short (289/330/358). Four workers beat
2/3/6/8 at 144 Hz on this eight-core PC; the render thread is the limit.
The HD invalidation indexing experiment (`perf/hd-invalidation-index`) remains
unmerged because it did not show a reliable end-to-end gain.
The queued-pass seam worker cut render replay from 6.96 to 4.11 ms in a
five-second 144 Hz A/B on the shared PC; distinct output rose from 66.8 to
96.8/s, still below target. A three-second 60 Hz comparison matched 113,120
triangle seam results bitwise, with zero mismatches or dispatch misses. The
owner saw no shaking or frame-order issue in the visible race. The R4 pin
build, 32/32 Windows and 29/29 available Mac project tests, and a
three-second slot-2 probe passed with zero misses. Postfx/driver presentation, live VRAM packing and
texture work dominate the remaining render cost. Earlier post-effect
capability and viewport caching showed no measurable gain and remain local.
Fork `990ffb00` also fixes queued-frame bloom source provenance; previously
the configured effect ran zero times in a short 60 Hz race. The corrected
build ran it 181 times in three seconds (about 0.57 ms/pass) and retained
60 distinct frames/s in steady seconds, with zero worker failures or dispatch
misses. Windows and Mac hidden GL fixtures passed 151 checks each. The fix is
pinned and installed as a development build.

Follow-up: complete real-frame draw offload only after private execution preserves
guest timing, IRQ/device service, mod hooks and call-point effects. The gate's
sound/RNG handoff is already synchronous on main; PRs #71/#72 reject false
passes. The local generic timed-context topic (`C:/Users/Shokunin/dev/psx-real-timing`,
`feat/timed-draw-checkpoint`) and R4 adapter (`C:/Users/Shokunin/dev/r4-timed-adapter`,
`feat/timed-real-draw-adapter`) now run the Grand Prix track call through
private timing, OpenBIOS, IRQ/device and mod-hook handoffs. The latest short
diagnostic reached private scratchpad and then a device deadline; no complete
real-frame call or equality proof exists, so this remains opt-in and unmerged.
The build-compatible headless race state is `analysis/timed-real-fresh-v18`;
short refusal receipts are `analysis/timed-real-trial-v19` onward. A separate
GPU GP0 IRQ1 class fix and callback DMA hold fix are local framework topics,
not installed. The installed development build remains the visually approved
60 FPS extra-frame worker pin `990ffb00`.

For higher rates, local `C:/Users/Shokunin/dev/psx-present-compositor`
(`feat/async-present-composition`) has immutable presenter slots for color,
mask, depth, OSD and source images, plus separate GL resource pools. A short
loaded race had 150/150 worker admissions, zero dispatch misses and zero
ordering mismatches; postfx composition still runs on the render thread.
The companion generic HUD prepare/replay API and R4 packet adapter are in
`C:/Users/Shokunin/dev/psx-hud-handoff` and
`C:/Users/Shokunin/dev/r4-hud-handoff`, with pixel parity still unverified.
The presenter offload checkpoint `6916530a` passed 126 ordered-preparation
checks, but generated pixel parity did not pass; it remains disabled. The HUD
handoff builds, but exact HUD pixel parity is unverified. These local branches
are checkpoints, not installed or merged. Keep
performance samples to 15 seconds and automated checks to 30 seconds. No
release, tag or publish without the owner's go and version.
References and sequence: `docs/CODEX_PLAN.md`.

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

- Gate: the stock Grand Prix passed 18,101 isolated ticks, but Time Attack,
  split-screen tails, after-goal replay and default-mod whole-race equality
  remain unverified. The latest default-mod Time Attack bounded check matched
  252 ticks and 504 input polls. See `docs/DRAW_ISOLATION.md`.
- Threading: real-frame draw still runs on main. The lean contexts used for
  optional frames omit the guest cycle/IRQ model, so they cannot replace it
  until timed private execution and call-point side-effect handoff are proven.
- Throughput: 100/120/144 Hz have ordered outputs but miss target on this
  shared PC at the 1200-line dynamic-resolution floor. Profile render work
  before changing worker count or output timing.
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
