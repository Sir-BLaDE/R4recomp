# Handoff

## Current work (2026-10-24)

A clean five-second 120 Hz probe at the large default window is
`analysis/gpu-profile-120-20261023`: 409 of 600 requested presents, with
render-thread busy time 5.09 s of 5 s. Window size was the main missing
variable in that result. At a 2560x1440 game window, the *installed*
executable gave 606 presents in five seconds, one timed refusal, zero drops
and dispatch misses (`analysis/installed-1440p120-v2`). A current-build
full-8K 60 Hz hidden-window probe gave 289 of 300 requested presents and zero
dispatch misses (`analysis/current-8k60-v1`). A 3840x2160/60 five-second
probe gave 297 presents, zero late worker frames and dispatch misses
(`analysis/current-4k60-v1`). Windows currently runs the desktop at
7680x4320/60; its listed 2560x1440/120 mode has not yet received
an on-screen check. The short results support 1440p/120 and 8K/60 under the
measured load, not native 8K/120.

A local Windows candidate zip built from code commit `eb319a5` at
`build-candidate-20261024-postfx/dist/r4-0.1.0-windows-x64.zip` (SHA-256
`355dc7df329a33c7b7b6012ad5059518440af1e8090aa3545bb362f008b7f322`).
The packager's checks passed; it contains the display-refresh choice and all
13 files of the optional `postfx/r4_2026` lighting preset, previously omitted.
It is installed locally at `C:/Users/Shokunin/Games/R4` (executable SHA-256
`80FE3D390AB1A58DE732DDD03AAFCD5B02E050619F399AD408281C48489A4AF6`).
The previous full installation is at
`C:/Users/Shokunin/Games/R4-dev-backup-20261024-postfx`; hashes of
settings, input, bindings and disc/BIOS choices match the backup, and all
three save files remain. The installed release executable started headless
for five seconds. No new release, tag or publication is authorized.
The new manifest's Mac check remains pending: `ssh mac` to the saved
192.168.1.216 profile timed out on 2026-10-24. Windows defaults and package
checks passed; no network configuration was changed.

The frame-rate selector now offers Match display refresh while retaining 60
FPS as the default and 30/90/100/120/144 fixed choices. The existing cadence
planner accepts the measured display rate, so this uses the same extra-frame
worker pipeline for standard monitor rates. Defaults check passed, runtime
built, and five-second hidden plus ten-second visible loaded races had zero
dispatch misses. The selector manifest is installed at
`C:/Users/Shokunin/Games/R4/mods/bundled/r4.enhancement.frame-rate/1.0.0`;
its predecessor is backed up in
`C:/Users/Shokunin/Games/R4-dev-backup-20261023-display-refresh`. The 60 FPS
default and installed executable remain unchanged.

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

Current local investigation (2026-10-23 evening): the same OpenGL backend stays.
The opt-in presenter/HUD series was rebuilt from fork `35b3849e` in
`C:/Users/Shokunin/dev/psx-presenter-min` (`c1df89e4`, 24 selected commits).
Its layered OpenGL fixture passed 58/58 and two async final frames matched
direct RGBA bytes exactly. A five-second 144 Hz loaded race admitted 371 full
outputs with zero fallback or dispatch misses, but displayed 374 frames and
had large shared-load gaps; sustained 144 Hz is unproven. It remains local,
opt-in and uninstalled. A follow-up FBO ownership commit `7fa65fbc` deferred
slot reattachment; its fixture passed 60/60 and six display frames matched
byte-for-byte. A five-second 144 Hz probe displayed 370 versus 341 earlier,
with fewer refusals/gaps, but shared GPU load prevents a stable-rate claim.
An isolated flush-order commit `f6375184` passes GL fixtures but its short R4
race fell back on every full-offload attempt, so it has no integrated speed
evidence and is not promoted.
Timed real-frame drawing now commits under a diagnostic
with idle skipping disabled, but differs from stock by 1–7 guest cycles per
draw; the first live pad/SIO Timer1 sample is ten counts early. This is a
correctness stop, not a value to mask. Trace receipts are in
`C:/Users/Shokunin/dev/r4-timed-audit/analysis/timed-audit-v4`. The isolated
serial-cycle guard `13ece33` refuses promotion on the first -1 draw. A
deadline-only IRQ prototype then failed owner DMA-state reconciliation at
`0x80066654`. A narrow isolated fix recognized device-raised `I_STAT` while
still checking DMA registers; two course draws then committed, but the next
draw reached the cycle guard 25 cycles early. The prototype is not pinned or
installed.
The combined presenter/resource and GL batching prototypes are isolated in
`C:/Users/Shokunin/dev/r4-hud-handoff` (framework submodule `93218aed`), not
pinned or installed. Five-second 144 Hz A/B/A results varied with shared GPU
load (281/301/306 displayed), so they establish no throughput gain; a 60 Hz
loaded race stayed near 60 with zero dispatch misses or late worker frames.
Focused hidden GL fixtures found exact color/stencil parity for opaque bloom
fusion, depth-state query removal, and skipped implicit source staging. The
last also matched final pixels for normal, fallback and leased async presents.
The full-width wide-batch shortcut failed raw-wide pixel equality and was
abandoned. Existing reprojection stays off: it changes timing and previously
showed visible race artifacts. An early-expiry replay rollback passed its GL
fixture and skipped 13–25 expired replays per five-second run; fast/legacy/fast
display counts (352/311/315) are too noisy for an FPS claim. A refreshed
timed real-draw probe passed its old device deadline; generic scratchpad
`LWC2` support (`493998b3`) then advanced it to an IRQ handoff refusal before
any GPU packets. The generic two-checkpoint fixture and rejection diagnostics
(`7580e02b`, R4 adapter `e45715d`) pass; they did not reproduce the R4 IRQ
refusal, whose exact invariant needs one fresh diagnostic probe. See
`analysis/hud-ab-*` in the local integration checkout and
`C:/Users/Shokunin/dev/r4-timed-audit/analysis/timed-audit-v3/probe/runtime.log`.

Released: v0.1.0 only. R4 master contains the developer-only isolation gate
(PR #65) and four extra-frame draw workers (PR #69). The source fork pin is
`35b3849e` (expired async replay rollback); the development build installed at
`C:\Users\Shokunin\Games\R4` has SHA-256
`173E18CC49D98DDBF34BD5C99858BE0FFFA70F20DB11F4581DAAE86D2B19D7A4`.
The prior executable is backed up at
`C:\Users\Shokunin\Games\R4-dev-backup-20261023-async-expiry`. Settings,
saves and bindings were preserved. This is not a release or tag. The new pin's
visible 10-second race check is `analysis/async-expiry-visible-v2`: 302 worker
jobs admitted, 601 extra-frame presentations queued, zero late workers and
dispatch misses; 599 present-thread displays with six timed drops under shared
load. Windows R4 tests pass 32/32 and the Windows/Mac GL rollback fixture
matched color and stencil pixels.

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
60 FPS extra-frame worker path, now pinned to `35b3849e`.

For higher rates, local `C:/Users/Shokunin/dev/psx-present-compositor`
(`feat/async-present-composition`) has immutable presenter slots for color,
mask, depth, OSD and source images, plus separate GL resource pools. A short
loaded race had 150/150 worker admissions, zero dispatch misses and zero
ordering mismatches; postfx composition still runs on the render thread.
The companion generic HUD prepare/replay API and R4 packet adapter are in
`C:/Users/Shokunin/dev/psx-hud-handoff` and
`C:/Users/Shokunin/dev/r4-hud-handoff`, with pixel parity still unverified.
Presenter assessment: local checkpoint `cfb53ddf` fixes borrowed mask/depth
texture reinitialization. A 6-real/15-output bloom fixture passed ordering and
effect-job checks; equal source pixels produced equal final pixels. Generated
sources varied even between baseline runs, so whole-game parity is unproven.
R4's host HUD currently disables this opt-in offload, and it moves only the
roughly 0.57 ms bloom pass, so it cannot yet close the 144 Hz throughput gap.
The HUD handoff builds, but renderer slots do not carry HUD packets and exact
HUD pixel parity is unverified. These local branches remain disabled,
uninstalled and unmerged; see the branch's
`docs/ASYNC_PRESENT_COMPOSITION.md`. Keep
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
