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

In progress: multi-core drawing, so 60/120/144 Hz and VR hold under load.
Plan and Codex prompt: `docs/CODEX_PLAN.md`. Branches:
- `feat/threaded-contexts` (fork): per-thread draw contexts + lean draw
  clones; stops at the first BIOS call. Its `docs/THREADED_CONTEXTS.md`.
- `feat/draw-isolation-gate` (fork) + R4 draft PR #65: which draw writes feed
  logic; first finding: sound state `0x8010FFE8/F8`. R4 `docs/DRAW_ISOLATION.md` (PR #65).
- `feat/host-threading` next steps: its `docs/HOST_THREADING.md`.

## Owner decisions

- Display: widescreen Fit, Match display, supersample 1.5, FXAA off, dynres
  floor = display, render + present threads, Smooth motion off (removed,
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
