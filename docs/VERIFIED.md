# Verified-state ledger

Feature -> last commit whose code touched it -> evidence. A feature whose
code has not moved since its row is not re-tested (CLAUDE.md, Verification
scale). Update the row when its code changes or a new check is run.
Evidence dirs are local (not tracked).

| Feature | Verified at (R4 / psxrecomp) | Evidence |
|---|---|---|
| Modern controls: analog gas/brake/steer, digital fallback, rumble | 12ba3f4 / ab9d181d | `tools/test_modern_controls_runtime.py` 8/8; `C:/Users/Shokunin/dev/r4-vinput/run` |
| Rewind (1P on; VS split screen blocked) | 12ba3f4 / ab9d181d | `splitscreen` test 8/8, same dir |
| Camera look-around | 12ba3f4 / ab9d181d | `r4-vinput/run/abc/ov_*.png` |
| JogCon compat | 12ba3f4 / ab9d181d | `tools/test_jogcon_runtime.py` |
| Widescreen Fit 16:9 / 21:9 (GP, TA, VS) | 12ba3f4 / ab9d181d | `C:/Users/Shokunin/dev/r4-vdisp/analysis/vdisp/vis-default-60b`, `vis-219-force18` |
| 60 FPS races (59/s, max gap 35 ms, loaded PC); 30 steady | 12ba3f4 / ab9d181d | vdisp `vis-fps-clean2`, `vis-rate30` |
| Race frame rate Auto: 60, original 30 from internal scale 18 (8K) | pin PR / e887344e | fork render_pass_motion_test; `tests/test_r4_defaults.py`; activation log line `r4.framerate: auto -> N FPS (internal scale S)` in the smoke; on-screen 18x not run (owner playtest) |
| Max Detail, no pop-in | 12ba3f4 / ab9d181d | vdisp `vis-slot8-maxdetail/burst_*.png` |
| HD HUD | 12ba3f4 / ab9d181d | vdisp `hud_*_1to1.png` |
| PGXP + seam snapping at 18x (strips only where the neighbour is: no kerb / lane-mark bars) | pin PR / 9d93976c | `C:/Users/Shokunin/dev/r4-pgxp/analysis/pgxp/evidence` (tick-exact attract-demo captures, before / after / snapping off), `runs/async-verify2` (prepared seams mismatch 0, 394,170 triangles verified), `runs/smoke2` headless 0 misses |
| Dynamic resolution | off by default since 249b5c3 (owner) | — |
| Dynres climbs at 8K/60 (CPU cost, queued-output cost, cadence guard); worker output-grid lead bound | pin PR / e4efba40 | `C:/Users/Shokunin/dev/r4-glctx/analysis/k8d-*`, `k8g-new45w` (one on-screen run), fixtures `scratchpad/psx-build/fwctest.log`; settle level on a quiet panel unverified |
| Hide rear-view mirror | 12ba3f4 / ab9d181d | vdisp `mirror_compare.png` |
| Projection replay (framework PSXDrawReplay) for R4 extra frames | tried on 243eca3, reverted: 33.4 vs 113.3 distinct/s at 1440p/120, +30% CPU per pass | HANDOFF 2026-10-27 |
| Render-thread CPU per extra frame (HD tracking miss path) and presenter admission wait | pin PR / 0bcc5a49 | `C:/Users/Shokunin/dev/r4-glctx/analysis/rt-*`, `phys-*`; GL fixtures `scratchpad/glfix-final` |
| GL fixtures (18) and present_thread_test on the fork | pin PR / 0bcc5a49 | same |
| Extra Trial widescreen | not verified (3f493ea reverted) | — |
| Windows package | df285a0 | `analysis/release-assets-v021-20261027` |
| macOS packages (arm64, x64) | df285a0 | same |
