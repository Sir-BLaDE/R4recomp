# Handoff

## Current work (2026-10-23)

Released: v0.1.0 only. A release still needs the owner's go and version.
The pinned development build is installed at `C:\Users\Shokunin\Games\R4`.
Its replaced executable and execution contract are backed up at
`C:\Users\Shokunin\Games\R4-dev-backup-20261023-1235`; the earlier backup is
`R4-dev-backup-20261023-1135`. Saves, settings and bindings were preserved.
This is not a release or tag.

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
changed no generated files. `analysis/worker-pinned-v78` measured 900 distinct
presented frames in its last 15 seconds (60.0/s), no >25 ms gap, reversed
deadline, dropped worker job or dispatch miss. The installed binary passed
`analysis/worker-installed-v79` (301 distinct frames in five seconds, no gap,
reversal or miss). A presenter-owned race capture is
`analysis/worker-present-v77/presenter.gif`; desktop capture showed the
owner's other apps and is no longer used. The optional capture code is on
framework topic `feat/presenter-frame-capture`, outside the installed binary.
An earlier loaded run fell to 43.7/s, so all-load stability is unproven.

Higher-rate five-second checks: 90 Hz delivered 271 distinct frames in its
last three seconds; 100 delivered 273, 120 delivered 291, and 144 delivered
233. All kept deadline order and zero dispatch misses. At 144 Hz the render
thread was busy for 5.25 s of a 5.09 s sample, with 190 late render jobs and
95 optional worker drops. Its host profile attributes 25.6% of render-thread
samples to `pgxp_snap_triangle`; these are measured bottlenecks, not a completed
144 Hz target. Receipts: `analysis/worker-rate{90-v80,100-v81,120-v82,144-v83}`
and `analysis/worker-rate144-profile-v84`.

Next: optimize the render-thread bottleneck, finish the real-frame isolation
gate and cycle accounting, then remeasure the higher requested rates. Short checks
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

- Delivery: development install is current; R4 PR #69 remains draft while
  real-frame isolation and higher-rate throughput are unfinished. No release
  or tag without owner approval/version.
- Gate: stock Grand Prix isolation passed 18,101 ticks, but Time Attack,
  split screen, attract/replay and default mods remain unverified. The
  default-mod base/base restore differs at its first SIO sample; see
  `docs/DRAW_ISOLATION.md` on the gate branch and the local isolation receipts.
  A newer default-mod Time Attack short check matched 252 shared ticks and
  504 input polls with zero misses (`r4-iso-runs/ta-default-v8-short-20261023`);
  the finish remains unverified.
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
