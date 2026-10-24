# R4 render-pass local-view receipt (2026-10-24)

This is a short consuming-title check for psxrecomp PR #727. It uses two
hidden Link peers resumed directly into the same saved race. One SDL window is
shown only after the race loads. The saved checkpoint and disc remain local.

The tested R4 source is `ea35cbc` plus the R4 HD HUD manifest's
`netplay = "local_view"` declaration. The framework test integration is
`d231361e` (fork `d108e9a0` plus render-pass, HD netplay classification,
and debug-only SDL window visibility diagnostics); this is **not** the R4
production pin. Host uses 120 Hz own-view redraw, 18x internal resolution
(effective scale 18, 4320 internal lines), and the bundled R4 HD HUD. Guest
uses 30 Hz redraw and disables the HD HUD.

With `PSX_RENDER_PASS_VERIFY=0`, a 5.4-second loaded-race check recorded
50 host local views, six planned and completed temporal render passes,
zero aborts, 6.31 ms average local-pass time, 48 GL captures and 21 swaps.
The host HD texture plugin was active with 36 replacements indexed; the
guest plugin was disabled and made zero temporal passes. Both peers had
16/16 passing shared-digest before/after receipts, four matching common
netplay digests, and zero dispatch or segment misses. This proves pass
admission and shared-state preservation in the title; it does not establish
a sustained output frame rate or that a HUD texture was applied during the
short sample (`applied_draws` was zero).

A same-state 6.0-second diagnostic run with `PSX_RENDER_PASS_VERIFY=1`
recorded 50 verification checks and zero mismatches or VRAM leaks, with
the same 16/16 peer receipts and zero dispatch misses. It made zero
temporal passes: verification selects the serial path, whose 256 MiB
three-generation cap cannot admit the 18x own-view capture. The framework
GL fixture independently verifies CPU VRAM restoration for an admitted HD
pass at smaller resolution. These samples are functional checks, not a
before/after performance comparison against the original framework pin.

Repeat the bounded check with `tools/r4_online_battle_regression.py` using
`--resume-race-dir` and a unique `--work` directory, `--mode delay`,
`--frontend hidden`, `--host-rate 120`, `--guest-rate 30`, `--host-hd`,
`--host-refresh-hz 120`, `--show-loaded-seat 0`, and `--no-pass-verify`.
The checkpoint is saved once using `--save-race-dir`; never reuse a work
directory because the harness provisions its peer directories afresh.
