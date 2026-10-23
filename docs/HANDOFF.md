# Handoff

## Current work (2026-10-23)

Released: v0.1.0 only. R4 master contains the developer-only isolation gate
(PR #65) and four extra-frame draw workers (PR #69). The fork pin is
`688380ef`. The development build from master is installed at
`C:\Users\Shokunin\Games\R4`; replaced program files are backed up at
`C:\Users\Shokunin\Games\R4-dev-backup-20261023-1255`. Settings, saves and
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

Performance checks must set `PSX_DISPLAY_RING=0`; the debug ring otherwise
reads full VRAM every game frame and understates visible throughput. Corrected
short hidden-window checks reached 90 Hz (271 distinct frames in the last
three seconds), but 100/120/144 fell short (289/330/358). Four workers beat
2/3/6/8 at 144 Hz on this eight-core PC; the render thread is the limit.
The HD invalidation indexing experiment (`perf/hd-invalidation-index`) remains
unmerged because it did not show a reliable end-to-end gain.

Next: move real-frame draw off main only after the isolation gate preserves
call-point state, sound/RNG and exact guest timing; improve renderer throughput
for 100/120/144. Keep performance samples to 15 seconds and automated checks
to 30 seconds. No release, tag or publish without the owner's go and version.
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
