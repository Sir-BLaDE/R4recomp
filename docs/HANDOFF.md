# Handoff

## Current work (2026-10-23)

Released: v0.1.0 only. A release still needs the owner's go and version.
The local development build is installed at `C:\Users\Shokunin\Games\R4`;
its previous program files and bundled mods are backed up at
`C:\Users\Shokunin\Games\R4-dev-backup-20261023-1135`. Saves, settings and
input bindings were preserved. This is not a release or tag.

Extra-frame workers are enabled by default (four contexts, `R4_DRAW_WORKERS=0`
for the serial reference). The game still simulates at 30 Hz; workers prepare
interpolated draws for the existing 60 FPS mod's exact frame order and timing.
The development build offers 60 (default), 90, 100, 120 and 144 FPS. R4 now
configures eight bounded presenter slots and starts dynamic resolution at its
1200-line floor, with its 18x ceiling still available when headroom permits.

Acceptance receipts: `analysis/worker-cadence-v42` measured 902 presents in
15.031 s (60.0/s), zero gaps over 25 ms during the sample, zero timed
refusals, worker faults and dispatch misses. The separate
`analysis/worker-trace-v39.csv` measured 180 consecutive changed images over
its last three seconds, no reversed deadlines or duplicate provenance,
16.67 ms median gap and no gap over 25 ms. Full-resolution pixels matched
exactly in `analysis/worker-pixels-v13` (7668x4320, 19,669 command receipts,
four contexts). The per-frame GPU-readback trace is diagnostic only: its long
15-second run slowed the game, so it is not a throughput benchmark.
All 31 PC project tests and 28/28 Mac tests available without the disc pass.
Framework fork `r4/main` is pushed at `688380ef`; its OpenBIOS emitter stamp
passes on both machines. R4 now points at that fork commit; game regeneration
changed no generated files. Fresh pinned-build race checks on this shared PC
vary with host load: `worker-prio-on-v49` delivered 905/15.031 s (60.2/s),
zero >25 ms sample gaps, worker lateness, refusals and dispatch misses;
`worker-prio-on-v50` delivered 905/15.063 s (60.1/s) with two gaps. An earlier
run fell to 43.7/s while the render/GPU path was delayed. The 60 Hz cadence
therefore still needs a reliable loaded-host check before refreshing the dev
install. Runtime screenshots show the moving race, but automated desktop
capture records the visible SDL window as black even with the previously
installed build; owner visual confirmation is pending.

Next: close the loaded-host output gaps, update the dev install, land the R4
PR, then tackle real-frame draw offload behind the isolation gate. Short checks
(15-second samples, <=30-second automated runs) remain the owner's budget.
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

- Pin: obtain a stable build-matched race check and refresh the dev install;
  then land the R4 PR. No release or tag without owner approval/version.
- Visible check: desktop capture of both the current and previously installed
  SDL window is black while the runtime's own screenshots contain the race.
  Confirm what the owner saw before treating on-screen cadence as proven.
- Gate: stock Grand Prix isolation passed 18,101 ticks, but Time Attack,
  split screen, attract/replay and default mods remain unverified. The
  default-mod base/base restore differs at its first SIO sample; see
  `docs/DRAW_ISOLATION.md` on the gate branch and the local isolation receipts.
- Further threading: real-frame draw still runs on main. Offload it only after
  isolation proves logic/sound state handoff; then measure 90/100/120/144 Hz
  and split track draw when frame latency demands it.
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
