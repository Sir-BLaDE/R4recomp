# Handoff

## Current work (2026-10-11)

Released: v0.1.0 only. Next release waits on the open PRs below landing and
the owner's go and version number. Never tag or publish without that ask.

The psxrecomp stack was rebased and force-pushed (#584-#622). Every open R4
PR now pins a pushed head; each PR body lists what it waits on. recomp-ui #86
and recomp-net #36 are merged.

Open R4 PRs and what each waits on:
- #22 v_wait idle skip: psxrecomp #590.
- #23 graphics presets: psxrecomp #591 (recomp-ui already pinned to master).
- #24 Linux zip: psxrecomp #592, #593.
- #25 batched cycle charge: psxrecomp #597.
- #26 recomp-launcher + in-game menu: psxrecomp #598-#603.
- #27 live mod options: #26 first. #28 launcher surface: #27 first.
- #31 Modern rumble: psxrecomp #608, #610.
- #32 wheel force feedback: psxrecomp #609.
Not tied to an R4 PR: psxrecomp #584, #586, #587, #589 (visual), #595, #596,
#605, #611, #618, #621, #622; #620 belongs to the 4P netplay work.

Merge order: land psxrecomp first, then re-pin each R4 PR to psxrecomp master
and merge in this order: #22, #25, #23, #24, #31, #32 (whichever of #31/#32
lands second re-pins to a master holding #608, #609 and #610), then #26, #27,
#28. Every R4 PR edits `docs/framework_pin_history.md` and most edit
`tests/test_r4_defaults.py`; keep both sides when rebasing.

Note: psxrecomp master after `67a21b73` (#614, #617) moves R4 guest timing
from boot frame 8. That is expected with the next re-pin, not a regression of
an open PR.

## Owner decisions

- Display: widescreen Fit, Match display, supersample 1.5, FXAA off, dynres
  floor = display, render + present threads, Smooth motion with reprojection,
  PGXP depth buffer / colour correction / fine seams. All in `game.toml`.
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
- Display defaults and Smooth motion: `README.md` (On by default, Smooth
  motion); `tests/test_r4_defaults.py`, `tools/check_pin_keys.py`.
- HD HUD: `docs/HD_HUD.md`, `tools/r4_hd_hud_pack.py`.
- Internal resolution presets: `README.md` (Internal resolution), `tools/res_matrix.py`.
- Release: `tools/package_release.sh` (gates: OpenBIOS only, HD HUD pack exact, pin keys).
- Verification loop: `tools/run_r4.sh build` + `tools/smoke.py <out-dir>`;
  rollback determinism: `PSX_RB_SELFCHECK=1 PSX_RB_SELFCHECK_MASH=1`.
- A/B guest identity (mod off, warm vs cold shards):
  `psxrecomp/tools/fp_identity.py` with
  `--launch 'tools/run_r4.sh {build} --debug-port {port} {headless}'`.
