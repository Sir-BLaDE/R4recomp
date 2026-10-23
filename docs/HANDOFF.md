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
The worker milestone passed 31 PC and 28 Mac project tests available without
the disc. After merging the developer-only isolation gate (R4 PR #65), the
integrated branch builds and passes 32/32 PC and 29/29 Mac tests. A fresh
boot-to-race state for that merged executable is still needed; the 28-second
headless turbo attempt reached Grand Prix selection but not the race, so no
merged-build race result is claimed. The installed 60 Hz build predates that
developer-only merge.
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

The visible installed build passed `analysis/worker-visible-noring-v87` with
901 distinct, ordered frames in its last 15 seconds (60.1/s), no >25 ms gap
or dispatch miss. Performance probes must set `PSX_DISPLAY_RING=0`: the debug
server otherwise downloads all 1024x512 VRAM each game frame, depressing the
visible result to 52/s (`worker-visible-installed-v86`). Normal non-debug
builds have no such ring.

Corrected higher-rate five-second checks with the ring off: 90 Hz delivered
271 distinct frames in its last three seconds; 100 delivered 289, 120
delivered 330, and 144 delivered 358. All retained deadline order and zero
dispatch misses, but the upper rates had late or dropped optional frames.
At 144 Hz, four workers are best among 2/3/4/6/8 on this eight-core PC;
more workers reduce worker drops but saturate rendering and reduce presented
frames. Receipts: `analysis/worker-noring{90-v88,100-v89,120-v90,144-v91}`
and worker-count checks `worker-noring144-{2-v95,3-v94,6-v92,8-v93}`. The
earlier rate/profile receipts include the debug readback and are not
throughput results.

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

- Delivery: the installed worker milestone is verified; the newer merged
  gate/worker branch passes PC/Mac tests but lacks a fresh race fixture. R4
  PR #69 remains draft while real-frame isolation and higher-rate throughput
  are unfinished. No release
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
