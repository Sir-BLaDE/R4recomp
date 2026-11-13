# R4 Recompiled

<!-- retcomm-readme-metrics -->
[![GitHub downloads (all assets, all releases)](https://img.shields.io/github/downloads/RetroPortingToolKit/R4Recomp/total)](https://github.com/RetroPortingToolKit/R4Recomp/releases)
[![GitHub downloads (latest release)](https://img.shields.io/github/downloads/RetroPortingToolKit/R4Recomp/latest/total)](https://github.com/RetroPortingToolKit/R4Recomp/releases/latest)
[![GitHub release](https://img.shields.io/github/v/release/RetroPortingToolKit/R4Recomp)](https://github.com/RetroPortingToolKit/R4Recomp/releases/latest)
<!-- /retcomm-readme-metrics -->

Static recompilation of **R4** built on
[psxrecomp](https://github.com/mstan/psxrecomp) and
[recomp-ui](https://github.com/RetroPortingToolKit/recomp-ui).

R4 - Ridge Racer Type 4 (SLPS-01798) static recompilation with 60 fps / 16:9 mods

| | |
|---|---|
| Players | 2 |
| Region | NTSC-J |
| Publisher | Namco |
| Year | 1998 |

Scaffolded with the New Project Layout. See
`psxrecomp/docs/GAME_PROJECT_SETUP.md` for the full flow.

<!-- retcomm-readme-launcher -->
## Retro Launcher

You can run this title **standalone** (download the release zip, point it at
your disc, play), or manage installs, updates, and disc/BIOS wiring with
**[Retro Launcher](https://github.com/RetroPortingToolKit/Retro-Launcher)** —
the Retro Compilation Manager hub for self-compiling recomps.

[Downloads](https://github.com/RetroPortingToolKit/Retro-Launcher/releases) ·
[Full README & features](https://github.com/RetroPortingToolKit/Retro-Launcher#readme)

<p align="center">
  <img src="https://raw.githubusercontent.com/RetroPortingToolKit/Retro-Launcher/main/docs/screenshots/hub-and-game-launcher.png" alt="Retro hub with a background build, next to a title’s recomp-ui launcher" width="720">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/RetroPortingToolKit/Retro-Launcher/main/docs/screenshots/queue-and-background-build.png" alt="Background cmake build with titles queued" width="720">
</p>

Retro checks for updates, installs the prebuilt release zips, and automates
BIOS/ROM/save plumbing so you are not stuck repeating each game’s first run by hand.
<!-- /retcomm-readme-launcher -->

## Legal

You must own the original game. Disc images under `disc/` are gitignored and
must never be committed. Retail BIOS dumps are not redistributed and no C
derived from one may be committed; releases run on the bundled MIT OpenBIOS.

`generated/` (the recompiled game C) **is committed**: releases ship the
compiled game, built by CI from that tree. Regenerate and commit it whenever
seeds or the framework pin change.

Default app icon: `assets/psxrecomp.ico` (and `.png` / `.svg`) — Retro-themed controller mark from `psxrecomp/assets/`. Windows builds embed it via `APP_ICON`.

Optional box art under `launcher_assets/img/` may come from
[libretro-thumbnails](https://github.com/libretro-thumbnails/libretro-thumbnails)
(`Named_Boxarts`); see `BOXART_SOURCE.txt` when present.

## Quick start (dev)

```bash
git submodule update --init --recursive
./psxrecomp/tools/ci/build_emitters.sh
python3 psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . --disc disc/<your>.cue
git add generated && git commit -m "Regenerate game C"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

Releases: tag `vX.Y.Z` (or run the *Release builds* workflow). CI builds the
committed `generated/` C on Linux, Windows and macOS and attaches
`r4-<version>-<platform>.zip`, the compiled game. Locally:
`scripts/package_release.sh build-release linux-x64`.

## Symbols

Progressive map: `symbols.toml` → `python3 tools/sync_symbols.py` →
`psx_symbols.h` (`PSX_FN_*`). See `psxrecomp/docs/SYMBOLS.md`.

## Optimization guide

`docs/R4_OPTIMIZATION_GUIDE.md`: what causes each "this looks like a PS1"
artifact (internal resolution, filtering, draw distance, frame drops) and how
to fix it on this title; how to compile the streamed overlays so the menus and
movies run natively; the Max Detail governor and the race spikes; how to
measure a change (the perf log, the debug server's wall-time rings and the
emulation-thread profiler) instead of guessing; and the HD texture-pack
workflow.

## Framework patches

`psxrecomp` is pinned at upstream `a38bf783`; the R4 changes to it (HD
texture matcher caches, per-texel STP for replacements, idle skip under the
guest cycle scale, PGXP store-ring allocation in debug builds only, borderless
window overhang) live in
`patches/psxrecomp/`. After `git submodule update --init --recursive` run
`scripts/apply_framework_patches.sh` before configuring.

## Framework pins

Submodule gitlinks (`psxrecomp`, optional `recomp-ui`, nested `recomp-net`)
are authoritative. `framework_pins.txt` is an optional scaffold snapshot;
release CI logs SHAs with `record_pins.sh` but builds whatever the gitlinks
resolve to. Bump submodules deliberately — do not float on `main`/`master`
in release CI.

<!-- retcomm-readme-raid -->
---

<p align="center">
  <sub><b>R.A.I.D. — Retro AI Development</b> · a Discord for AI-assisted retro reverse-engineering, decomp &amp; recomp</sub>
</p>

<p align="center">
  <a href="https://discord.gg/Ad9BwSzctP"><img src=".github/raid-discord.png" alt="Join the Retro AI Development (R.A.I.D.) Discord" width="200"></a>
</p>
<!-- /retcomm-readme-raid -->

## R4 GameShark 60 FPS / 16:9 patch V2 (this port)

- Codes: `mods/source/R4_60FPS_Widescreen_Patch_V2.cht` (written for SCPS-45356;
  all 2,478 `D001EB86 AE40` guards and every hook trampoline match the
  SLPS-01798 executable byte for byte).
- `tools/cht_to_c.py` turns the .cht into `src/r4_gameshark_codes.h`;
  `src/r4_gameshark.c` applies each list at the EXE entry (0x8007D4B4) and
  again every VBlank (the emulator's EndFrame pass), as four independent mod
  features (`mods/preloaded/packages/r4.gameshark`).
- 60 FPS opens the gated `[timing] guest_cycle_scale = 3` (the "CPU 300%").
- 16:9 selects a fixed 16:9 aspect and keeps the framework's own GTE/GPU
  widescreen squash at identity (plain stretched present, as the patch asks).

Windows x64 build from Linux (MinGW-w64 cross):

    cmake -S . -B build-win -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_TOOLCHAIN_FILE=psxrecomp/cmake/toolchain-mingw-w64.cmake \
      -DPSX_DEBUG_TOOLS=OFF -DPSXRECOMP_BIOS_STEMS=OpenBIOS \
      -DPSX_RELEASE_CHANNEL=public -DPSXRECOMP_REQUIRE_GAME_C=ON
    cmake --build build-win --target psx-runtime
    packaging/stage_windows.sh build-win "$(cat VERSION)"

## Spanish text from the PAL release (`r4.spanish`)

Built from the player's own discs (JP SLPS-01798 + PAL SCES-01706):

    python3 tools/r4_es/build_es.py --jp R4_JP.bin --eu R4_PAL.bin \
        --out mods/preloaded/packages/r4.spanish/1.0.0
    python3 tools/r4_es/make_manifest.py --exe disc/SLPS_017.98 \
        --jp-disc R4_JP.bin --pack mods/preloaded/packages/r4.spanish/1.0.0
    rm mods/preloaded/packages/r4.spanish/1.0.0/overlays.json

- `build_es.py` rewrites the R4.BIN groups 678-744 (the four teams' Grand
  Prix stories) and 755-763 (system messages, team select, GP rules screen)
  with the Spanish sub-blocks of the PAL entries and the PAL Latin-1 font
  (entry 724), repacked inside the original sector spans, plus the archive
  table; the package overlays them on the disc (`disc_user`, sha-guarded).
- The GP rules screen (JP 763: 17 messages in step with its animation) is
  rebuilt from the PAL single-stream screen (728); every header's character
  count is recomputed.
- `make_manifest.py` adds guarded code patches: glyph cells 12x24/21 per row
  -> 8x24/32 per row, sprite width 8, pen advance 7, and the message window's
  glyph-state array 64 -> 200 entries as in the PAL build;
  `src/r4_spanish.c` moves the static window #2 to enhancement memory.
- The payload is derived from disc data: private builds only.

## v0.3: performance, HD pack, reflowed text

- **GameShark code compiled natively** (`tools/gs_static/make_captures.py`):
  the patch's MIPS routines (kernel RAM 0x8000C000-0x8000FD00) and the game
  functions it rewrites are emitted as overlay captures and compiled with
  `psxrecomp/tools/compile_overlays.py --static --flavor 2` into
  `generated/gs_overlays/` (linked via `GAME_OVERLAY_STATIC_C`). They used to
  run on the dirty-RAM interpreter, where every instruction also went through
  the PGXP hooks; in a race the interpreter ran ~150x fewer instructions
  after the change. Regenerate after editing the codes:

      python3 tools/gs_static/make_captures.py --exe disc/SLPS_017.98 \
          --codes src/r4_gameshark_codes.h \
          --ranges generated/SLPS_017.98_full.ranges \
          --observed tools/gs_static/observed_pcs.json \
          --out tools/gs_static/gs_captures.json
      python3 psxrecomp/tools/compile_overlays.py --static \
          --captures tools/gs_static/gs_captures.json --game-toml game.toml \
          --recompiler build-recompiler/psxrecomp-game \
          --runtime-include psxrecomp/runtime/include \
          --out-dir generated/gs_overlays --flavor 2

- **Video defaults**: fixed Match-display resolution, no supersampling, no
  dynamic resolution, render thread on. Pad defaults to analog.
- **Text**: Spanish messages rewrapped to the Japanese 2-row/39-column boxes
  with extra pages; the GP rules screen laid out by hand (`INFO_ES`); the four
  ending letters rebuilt from the PAL pages; race-card kanji cells redrawn in
  Latin letters; PAL billboards in the courses.
- **HD texture pack** (`tools/r4_hd/build_pack.py`): DuckStation `texupload`
  names computed offline from the patched R4.BIN; HD Spanish font (TeX Gyre
  Heros), HD endings, 2D sheets upscaled 4x with a numpy waifu2x upconv_7.
  Shipped in an override of `psx.enhancement.hd-textures` (on by default,
  `pack/`).

## v0.4: frame drops, JogCon steering, PAL text layout, redrawn 2D

- **Frame drops at busy spots** (e.g. the S before the bridge on Helter
  Skelter): guest-side, not host. With PGXP *precise culling* the game keeps
  sub-pixel polygons it would cull and runs out of guest CPU time per frame
  (45-57 fps internally at the GP start, host idle); a higher overclock does
  not help (x4/x6 measured worse). The R4 PGXP override now ships precise
  culling **off** (steady 60). Measured with `R4_PERFLOG_ALL=1`.
- **`r4.diagnostics` / `src/r4_perflog.c`**: `R4_perf_log.txt` next to the
  executable, one line per second with late host VBlanks or a partial drop:
  game fps (display flips), late/worst/avg host frame time, emulation-thread
  busy share and CPU ms per VBlank, interpreted instructions and hottest
  interpreted PCs.
- **`r4.controls` / `src/r4_analog.c`**: R4 only steers analog with a JogCon
  or NeGcon; the gamepad is presented as a JogCon (dial = left stick X with a
  small deadzone; R1 = RT/R1/Cross accelerates, L1 = LT/L1/Square brakes).
  `R4_ANALOG_MODE=negcon` selects the NeGcon (its I/A do not confirm at team
  select).
- **Text layout**: the PAL message boxes are the Japanese ones (the only
  JP/PAL difference in the window code is the memory-card window height). The
  Spanish text now keeps the PAL line breaks (3 rows per page; rare 4-row
  pages split). Patches in `tools/r4_es/make_manifest.py`: glyph rows 4..21 of
  the 8x24 cell (sprite height 18, v+4), row advance 22, pen advance 5. HD font
  redrawn to those metrics (TeX Gyre Heros Bold, `tools/r4_hd/font_es.py`).
- **HD pack** (`tools/r4_hd/build_pack.py`, `redraw.py`, `esrgan.py`):
  grey anti-aliased text sheets redrawn as potrace outlines (filled with the
  ESRGAN colour); colour art via Real-ESRGAN x4plus_anime_6B, pictures and
  course textures via Real-ESRGAN x4plus (spandrel, CPU), all with traced
  binary-alpha silhouettes. `--dumps <dir>` adds the dumped sub-rectangles of
  pages the game partially overwrites (the race HUD sheet). Models are not
  shipped; build with:

      python3 tools/r4_hd/build_pack.py --jp R4_JP.bin --eu R4_PAL.bin \
          --spanish mods/preloaded/packages/r4.spanish/1.0.0 \
          --esrgan-art RealESRGAN_x4plus_anime_6B.pth \
          --esrgan-photo RealESRGAN_x4plus.pth --courses \
          --dumps <DumpTexturePages dump dir> \
          --out mods/preloaded/packages/psx.enhancement.hd-textures/1.0.0/pack/replacements

## v0.5: semi-transparent HD texels, palette variants, race-card fonts

- **Black car / broken reflections** (framework, `gpu_gl_renderer.c`): a
  DuckStation replacement without an `ST` variant was always drawn opaque
  (`stp=0`), so the car reflection map (lights on black, drawn additive) hid
  the body. Replacements now take the blend flag from the native texel's STP
  bit, as the PS1 does (alpha modes 2 and 4). Found by bisecting the pack on
  the Car Data screen (one 128x128 image). The semi-transparent course
  textures excluded in v0.4 are HD again.
- **HD texture lookup** (`duckstation_texture_pack.cpp`): rectangle hashes and
  match results cached and invalidated per 64x64 VRAM tile; page groups in a
  spatial grid (~2.4x less render-thread time in the matcher).
- **Menu label sheets** (`build_pack.py --cluts`, `tools/r4_hd/clutcol.py`):
  R4 draws several sheets with CLUTs other than the TIM's own; the pack
  carries one image per sheet and palette observed in game.
- **Race card / date screen**: grey text drawn as ink over a shifted copy of
  itself is detected (`redraw.shadow_offset`); thick fonts are redrawn per
  layer (xBRZ ink + rebuilt shadow), the 6-texel font with plain xBRZ (keeps
  counters that tracing and ESRGAN closed). Sheets the game partly
  overwrites (another TIM of the same file inside their rectangle) are also
  emitted as 32x16-texel tiles (`build_pack.tiles`).
- **Texts**: pages longer than three PAL rows are rewrapped to wider rows
  (`build_es.py`); no double period at page ends.
- **JogCon dial indicator** removed (`r4.controls`, patch at 0x8002254C).
- HD pack preload cap 512 -> 768 MiB (`gpu_hd_textures.cpp`): the 3704-image
  pack (~544 MiB decoded) now preloads completely instead of decoding the
  last 168 images on first use.
- Pack builder: `--cache <dir>` keeps finished sheets so rebuilds resume.
  `--cluts` takes the CLUT capture written by `tools/r4_hd/clutcol.py`
  (palette words read from VRAM in game; private input like the dumps).
  Extra build dependency: `xbrz.py` (GPL-3, build-time only, not shipped).

## v0.6: performance with full PGXP (CPU mode + precise culling)

Measured from a race savestate with the accelerator held (same frames every
run), guest frame timeline from `gpu_timeline`, host profile with `perf`:

- **Guest-side drops** (the game misses frames with PGXP precise culling):
  the 16:9 patch installs a routine at 0x8000E898 that the hooked DrawOTag
  path calls for every ordering table, rewriting every packet's X. It ran
  ~190,000 guest cycles per frame, a third of a 60 FPS frame at the patch's
  300% CPU; precise culling keeps more packets and the frame no longer fit.
  `r4.gameshark.widescreen` now runs it through a function override inside an
  uncharged span (`psx_cycle_uncharged_begin/end`): all its RAM effects, zero
  guest time (charged in full past one VBlank). Result: one flip per VBlank,
  all right after the VBlank, no drops (25 missed frames before in the
  measured stretch). A higher overclock is **not** the fix: at x4 the flip
  moves to a non-VBlank interrupt callback (0x800933A0) mid-frame and some
  VBlanks get two flips; at x5 the game runs ~67 fps.
- **Emulation thread** (perf, race): guest code itself is ~5% of the thread;
  the rest is per-instruction cycle accounting (~30%), PGXP (~28%), GTE (~6%).
  - `[timing] guest_cycle_scale_batch = true` (framework-verified on R4):
    -7%.
  - `idle_skip` with store counters at the audited JP `v_wait` sites
    (0x8008B090 / 0x8008B0D8; audit in `game.toml`). The framework detector
    required a constant cycle cost per loop pass, which the 300% scale's
    fractional carry breaks (10/11/10...). `psx_cycles.c` now compares passes
    by their unscaled cost W = delta * 65536 + frac_end - frac_start and
    advances k passes by exactly floor((frac + k * W) / 65536), leaving the
    carry the skipped passes would leave. `frame_fingerprint` judge columns
    are identical with the skip on/off over 700+ race frames. -14%.
  - Together: 41.0 -> 36.9 ms per VBlank in the test VM while now producing
    every frame with full PGXP.
- **Render thread**: one rect-cache probe per page group instead of two, and
  a per-page memo of each group's hash and candidate list.
- **PGXP defaults** (R4 override): CPU-mode propagation and precise culling
  on.
- **Perf log**: game fps counts display-start changes from the GPU timeline
  (sampling the display address at VBlank missed two flips inside one VBlank;
  that artefact made x4 look worse than x3 in v0.4).

## v0.6.1: intro / attract movie decoder compiled

The player's perf log showed two long 30 fps stretches (the opening movie and
the attract movie) with the emulation thread at ~100% and ~15M instructions
per second on the dirty-RAM interpreter (hot loop 0x8011493C): R4 loads its
movie decoder into RAM at 0x80114000. The runtime's own overlay capture of
that region (3 pages, 544 executed PCs) is compiled with the GameShark code
into `generated/gs_overlays` (`tools/gs_static/fmv_captures.json`, private:
it carries disc code bytes):

    python3 psxrecomp/tools/compile_overlays.py --static --force \
        --captures <gs_captures.json + fmv_captures.json merged> \
        --game-toml game.toml --recompiler build-recompiler/psxrecomp-game \
        --runtime-include psxrecomp/runtime/include \
        --out-dir generated/gs_overlays --flavor 2

Interpreted instructions during the movie: ~14.5M/s -> ~3K/s.

Race seconds in the same log mostly show exactly one late host frame: 60 fps
on a 280 Hz display has no integer refresh cadence (4.67 refreshes per frame).
START_HERE recommends G-Sync/FreeSync or a 240 Hz (4 x 60) mode.

## v0.7: HD HUD, Max Detail and the R4 launcher (from RidgeRacerType4Recomp)

- **HD HUD** by Kuid0us (github.com/Kuid0us/T4HDHUD) replaces the 2D HD
  pack, in `psx.enhancement.hd-textures` (pack images local only). JP keys
  plus tetrisgm's palette variants and glyph repairs (the JP/PAL km/h atlas
  c41643fd, built with their `pal/tools/hd_hud_pack_pal.py`).
- **Max Detail** (`r4.enhancement.max-detail`, `src/max_detail/`): tetrisgm's
  plugin with every USA address translated to SLPS_017.98 by
  `tools/us_port/translate_mods.py` / `r4map.py` (function matching), each
  hook call site and the car LOD table checked against the JP words; the 18
  `[[draw_distance.clamp]]` guards and 15 entry hooks are in game.toml.
  Adapted to the GameShark 60 FPS pacing (no race-tick hold, one-VBlank
  budget, the patch's VSync call site), the patch's 16:9 view cone, and race
  detection without the USA overlay handler table.
- **Framework / launcher**: psxrecomp pinned to tetrisgm/psxrecomp `r4/main`
  (2b5a3817) with `patches/psxrecomp/0001-r4-framework.patch` (idle-skip GCS,
  cycle batching, HD preload cap); recomp-ui is tetrisgm's recomp-launcher
  (R4 skin) and `launcher/title_r4.cpp` reads the logo (R4.BIN 0x02ECC28C)
  and the bold menu font (0x026A4004, capitals reused for lowercase) from
  the player's disc through the runtime ISO reader (CHD included).
- Verified (Linux, debug build): race at 60 guest flips/s with Max Detail
  Maximum and the HD HUD (127k HD draws in 20 s), Spanish dialogue, menu
  Start Game.

## v0.7.1: latest upstream framework; host-aware Max Detail governor

- The 0.7 race slowdowns (user perf log: 17-28 ms of emulation per 16.7 ms
  VBlank in races, ~9 ms in the attract race) came from Max Detail's governor:
  it adds far sections until the frame uses 86-93 % of its *guest* budget, and
  with `guest_cycle_scale = 3` that budget holds about three native VBlanks of
  work per 60 FPS frame, so Maximum roughly doubled what the host had to
  emulate. The governor now also takes the host time of the frame's busy part
  (frame start to the VSync floor wait, `QueryPerformanceCounter` /
  `CLOCK_MONOTONIC`) as load, with a 10.5 ms target read as its 930 permille
  "drop one level" line (`R4_MD_HOST_MS=<ms>`, 0 = guest cycles only).
- Framework back on upstream: psxrecomp 64dff482 and recomp-ui 29fa3d1
  (RetroPortingToolKit, 2026-11-07, 247 commits past v0.6's base) with
  `patches/psxrecomp/0001-r4-framework.patch` (the DuckStation matcher and
  Windows borderless hunks are dropped: the HD HUD uses the upload-CRC pack
  path and upstream now keeps borderless a desktop-sized window). The
  recomp-launcher R4 title layer (`launcher/title_r4.cpp`) is kept for a later
  port but not built.
- `PSX_NATIVE_CPU_SPANS` is forced OFF (CMakeLists.txt): upstream's approximate
  native-span CPU timing (ENHANCED default) made the race flip every 0.88
  VBlank with the 60 FPS patch, i.e. the game ran ~1.2x fast. Faithful
  per-instruction timing gives 60 flips per 60 VBlanks again.
- The guest_cycle_scale gate now opens at the EXE entry (GameShark 60 FPS) and
  at the first game frame (Max Detail) instead of at plan activation: with the
  overclock on during the BIOS boot the current framework never loaded the
  EXE.
- Verified (Linux debug build, race from a fresh route): 60 guest flips per 60
  VBlanks, HD HUD applied, Max Detail governor active, Spanish text.

## v0.7.2: both HD packs; governor on thread CPU time; reflections Stock

- `psx.enhancement.hd-textures` pack/ holds the HD HUD (Beetle upload-CRC PNGs
  at the root) and the v0.6 2D pack (`replacements/` + `config.yaml`,
  DuckStation keys). The framework patch makes a draw the Beetle pack does not
  cover fall through to the DuckStation entries (upstream uses one or the
  other), and carries the DuckStation matcher memo/probe changes again (they
  now apply with a 3-way merge). Race bench: 987k of 1.0M draws replaced.
- Max Detail governor host input: the emulation thread's CPU time per game
  frame (frame start to frame start: `QueryThreadCycleTime` with a QPC-calibrated
  TSC rate on Windows, `CLOCK_THREAD_CPUTIME_ID` elsewhere), averaged over ~8
  frames, 12 ms target (`R4_MD_HOST_MS`). The v0.7.1 wall-clock measure only
  covered frame start to the VSync wait, so the user's race still ran at
  14-17 ms per VBlank (19 ms on the grid).
- Car reflections default to Stock: on the starting grid every car is in view
  and at a real 60 FPS the reflective bodies are drawn twice as often.

## v0.7.3: review and optimization pass

Profiled with `perf` on the race bench (slot 8, 2400 frames; same 1.37M of
1.38M draws replaced before and after every change below).

- **DuckStation matcher (framework patch).** Its match cache was cleared on
  every VRAM-to-VRAM copy and every upload, and R4 copies VRAM twice per race
  frame, so each of the ~165 distinct lookups of a frame missed once per frame
  and walked about a hundred geometry groups. Cached matches depend on VRAM
  only under their page and CLUT, which the tile generations already cover, so
  the clears are replaced by tile bumps of exactly the records that change, and
  the tiles are 64x16 instead of 64x64 (a 240/480-line framebuffer shares its
  last 64-line tile row with what lies below it). Misses per 2400 frames:
  396,809 -> 281,586 (no clears) -> 5,936 (with 16-line tiles); geometry
  groups visited 38.5M -> 0.57M; `duck_texture_pack_match_parts` 15 % -> 2 %
  of the render thread, which samples 16 % less overall.
- **2D pack as lossless WebP.** `tools/hd_pack_optimize.py` re-encodes
  `replacements/*.png` (exact mode, every file decoded again and compared) and
  turns the 606 images whose pixels equal another one into `Aliases:` of
  `config.yaml`: 3704 PNG / 151 MiB -> 3098 WebP / 91 MiB. Preload on the dev
  box 2.3-3.0 s -> 1.9 s. The PNG pack stays in `backup_private/`.
- **Max Detail governor.** The host input is the 8-frame average, except that
  a last frame over the target counts at once (the average alone lags, so the
  level kept falling for several frames after the frame already fit). A
  save-state load no longer counts as a frame.
- **Native CPU spans, measured again** (`-DR4_NATIVE_CPU_SPANS=ON`): 30 flips
  per 60 VBlanks in the race and more emulation CPU per VBlank, so it stays
  OFF. Upstream's per-instruction timing (`psx_cyc_step`, ~16 % of the
  emulation thread) and the PGXP hooks (~23 %) are where that thread's time
  goes; both are framework design and left as they are.

## v0.7.4: VSync timeout under the overclock; native CPU spans on

Player report on 0.7.3: performance jumps, the anti pop-in not visible, older
builds felt faster. Their log: the race at 13.5-17 ms of emulation per 16.7 ms
VBlank (80-98 % of a core), 60 flips per 60 VBlanks, a few 33-88 ms frames.

- **Same cost as 0.6.1.** Both Windows builds under Wine, native resolution,
  walked from boot into Grand Prix race 1 by the same script
  (`R4_PERFLOG_ALL=1`): 44.0 (0.6.1) vs 43.4 (0.7.3) ms of emulation per VBlank.
  The emulation thread did not get slower; with the thread that close to
  16.7 ms the 12 ms governor target simply kept Max Detail at its floor
  (level -2 = stock draw distance), which is why the pop-in was unchanged.
- **Why native spans made the game run fast** (v0.7.1 note). libetc
  `v_wait(target, timeout)` (0x8008B068) gives up after `timeout << 15` loop
  passes. That is a pass count, so its length in guest time shrinks with the
  overclock: about 0.39 VBlank at x3. The 60 FPS routine calls `VSync(0)` once
  128 hblanks (0.49 VBlank) have passed, so a frame whose work ends early
  returns at 0.88 VBlank. With per-instruction timing at x3 race frames are
  long enough; with a cheaper CPU model (or x4/x5) they are not. Measured on
  the spans build from its own race state: 62-72 flips per 60 VBlanks with the
  stock timeout, exactly 60 with it scaled. `r4.gameshark.60fps` now hooks
  `v_wait` (new `mod_function_entry_funcs` entry, game C regenerated) and
  multiplies the timeout by the live overclock x2 (`R4_VWAIT_STOCK=1` = A/B).
- **`R4_NATIVE_CPU_SPANS` ON by default.** Same race from boot, dev box:
  45.9 -> 37.0 ms of emulation per VBlank (-19 %), 60 flips per 60 VBlanks in
  both. Existing build directories keep their cached OFF: reconfigure with
  `-DR4_NATIVE_CPU_SPANS=ON`.
- **Max Detail `cpu_budget` option**: Balanced 14.5 ms (default), Safe
  12.5 ms, No limit (guest budget only). On the spans build, same race start:
  36.7 ms at the floor, 40.5 ms with no limit while the level climbs from 0 to
  30 (28-41 ms once at 30), 60 flips per 60 VBlanks throughout.
- **Windows builds under Wine, same script as above**: 0.6.1 44.0, 0.7.3 43.4,
  0.7.4 35.9 ms of emulation per VBlank with Max Detail at level 30, 35.4 at
  the floor; 60 flips per 60 VBlanks. Wine has no thread cycle counter
  (`QueryThreadCycleTime` returns 0), so the governor had no host input there;
  it now falls back to `GetThreadTimes` averaged over 32 frames.
- **Perf log**: `md=<level>/<ms>` (governor level and its emulation ms per
  frame), `worst=..ms(busy ..)` (emulation CPU inside the window's worst
  interval, from thread cycle time), and the file is written every 20 lines
  and at exit instead of once a second from the emulation thread.
- The uploaded `overlay_captures.json` (8 regions; summarized by script, not
  read in full) holds menu and loader code that runs on the dirty-RAM
  interpreter (0x8001F000, 0x80032000, 0x8003B000, 0x80115000, ...): up to
  475k instructions a second in the menus, ~10k in races. Not compiled yet.

## v0.7.5: the race spikes are the governor's floor

Measured on Windows (0.7.4 rebuilt with `-DR4_NATIVE_CPU_SPANS=ON`), the game
driven over the TCP debug server and `R4_perf_log.txt` written with
`R4_PERFLOG_ALL=1`. The race measured is the attract demo (the same engine
and the same Max Detail governor); the Grand Prix route could not be walked
here because the course intro movie stalls in this environment (the FMV and
menu overlay captures are missing, so that code runs in the dirty-RAM
interpreter).

- **The race costs 12.0-13.5 ms of emulation per 16.7 ms VBlank** (72-81 % of
  a core) with 60 flips per 60 VBlanks. The frames that overrun the budget
  are exactly the ones where the Max Detail governor sat at its floor:

  | governor level | race windows | worst interval (avg / max) | emulation CPU in it |
  |---|---|---|---|
  | -2 (stock draw distance) | 101 | 21.0 / 29.6 ms | 17.0 ms |
  | -1 .. 30 | 108 | 18.3-19.7 / 21.5 ms | 12-15 ms |

  The floor is the *expensive* state, not the cheap one: at level -2 the game
  loads the course sections itself, and that reload is the most expensive
  frame of the race. The governor got there because one frame over the budget
  (often its own level change, 17-22 ms) drops the level by two, and the
  drop's own frame is over the budget too: the reaction cascaded to the floor
  and back every 10-20 s, and each pass through the floor cost a late VBlank.
- **Fix (this version)**: the floor is now the floor of the *view*. A normal
  view can hold the extra track sections, so it keeps two sections ahead
  (level 0) as its floor, and a change of view width no longer slams the level
  down from a high one. A very wide view (about 30:9 on) still falls back to
  the stock draw distance - its extra octants overrun the grid - and the
  governor still adapts to the frame cost as before. Same race, same build:
  late VBlanks 1.03 % -> 0.38 %, frames over 20 ms 38 % -> 19 %, worst
  interval 29.6 -> 25.2 ms and none over 25 ms. The level now stays where the
  frame fits instead of oscillating between the floor and the top.
- **Confirmed with the sections pinned** (`R4_MD_AHEAD=2 R4_MD_BEHIND=1`, the
  developer A/B switch): late VBlanks 0.27 %, worst interval max 23.4 ms. The
  same picture, which is what pins the cause down: it is the *change* of the
  section count that costs, not the sections themselves - the steady cost is
  the same at level 0 and at level 30 (12.0-12.5 ms of emulation per VBlank).
- **Two emulation halts in the attract loop** (this machine, 0.7.4, without
  the FMV and menu overlay captures): `DISPATCH FATAL: misaligned target
  0x0EADF9A1` and `GPU GP0 unknown command 0xFD`, both 5-8 min into an
  unattended session. The first one is the GameShark 60 FPS code cave at
  0x8000C210, which calls the game's handler pointer through $v0; the pointer
  came from the game's handler table and held a data value (0x0EADF9A1 is a
  table entry, not an address). Both failures appear while the dirty-RAM
  interpreter runs the menu and movie code that the overlay captures cover;
  a build with those captures compiled does not run that code interpreted,
  and that path could not be tested here.

## v0.7.7: LTO by default, and a governor that stops chasing its own cost

- **IPO/LTO is on** (`R4_RUNTIME_IPO`, `CMakeLists.txt`; the framework's
  `PSX_RUNTIME_IPO`). Measured on this title's race: **13.0 -> 10.2 ms of
  emulation per 16.7 ms VBlank (-18 %)**. That is the headroom the Max Detail
  governor needs to keep the extra track sections without overrunning the
  frame - the single biggest win available on a machine whose race sits at
  80-98 % of a core.
- **The governor no longer reacts to its own level change.** A level change
  costs one frame by construction (the new sections are drawn, or the dropped
  ones are reloaded by the game), and that frame is over budget by
  definition: the governor read its own cost as "too expensive", dropped
  again, and the reaction cascaded to the floor and back. The governor now
  ignores the measurement for the 8 frames after a change
  (`R4_MD_GOV_SETTLE`), so it reacts to the *steady* cost. With the faster
  build the level climbs to its maximum once and stays there instead of
  hunting.
- **Measured** (the attract demo's race, one build per row, same machine;
  the courses differ between rows, so read the trend):

  | build | emulation ms per VBlank | late VBlanks | worst interval | frames over 25 ms |
  |---|---|---|---|---|
  | 0.7.4 | 12.5 | 1.03 % | 29.6 ms | 3 |
  | 0.7.5 (view floor) | 12.0 | 0.40 % | 24.4 ms | 0 |
  | 0.7.7 (LTO + settle) | 10.2 | 0.79 % | 24.8 ms | **0** |
  | 0.7.7 + PGO | 9.6 | 0.51 % | **22.0 ms** | **0** |
  | 0.7.7 + PGO + framework patch, HD pack loaded | **8.6** | 0.90 % | 23.7 ms | **0** |

  The last row is the shipped build: the framework patch (the HD matcher
  caches, the per-texel STP for replacements and the 768 MiB preload cap)
  applied with `scripts/apply_framework_patches.sh`, and the HD texture pack
  loaded - the pack is GPU work, so it does not change the emulation cost.
  Against 0.7.4 that is **12.5 -> 8.6 ms per VBlank (-31 %)**, with no frame
  over 25 ms in the whole race.

  The remaining late VBlanks are the one-off cost of the governor's climb
  (one per level step, about two frames each); after it reaches its maximum
  there are no more level changes and no more spikes.
- **PGO on top of it** (`psxrecomp_cli.py rebuild --force-pgo --train-secs 150
  --train-runs 2`, with `PSX_DEBUG_SERVER=1` in the environment so the training
  exits cleanly and flushes the profile): 10.2 -> **9.6 ms** per VBlank. The
  profile is a local build artifact (the shipped executable carries it; a
  fresh build needs the training step again), so it is not in the repository.
- **The HD pack and the Spanish payload are back in the build.** They are the
  player's own data (derived from the PAL disc), so they stay out of the
  repository: `mods/preloaded/packages/psx.enhancement.hd-textures/1.0.0/pack/`
  (3098 WebP + 36 PNG + `config.yaml`) and
  `mods/preloaded/packages/r4.spanish/1.0.0/payload/` are gitignored and
  staged into the build like any other private payload. With them the pack
  preloads completely (3740/3740 images, 578.9 MiB, ~0.5 s) and the Spanish
  text applies.
- **Intro FMV auto-skip** (`game.toml`: `auto_skip_fmv = true`, `fmv_skip_no_xa = 1`):
  the intro opening movie is skipped automatically on startup, so the Grand
  Prix route can now be walked from the very first frame. The FMV is detected
  via MDEC activity (and silently XA-streams when present). Without this config
  the intro hangs in interpreted code (the same mechanism that caused the
  attract-loop halt). With it, the race starts immediately and all subsequent
  performance numbers apply from frame 0.
- The whole series was measured through the TCP debug server
  (`PSX_DEBUG_SERVER=1`) and `R4_PERFLOG_ALL=1`; `docs/R4_OPTIMIZATION_GUIDE.md`
  has the commands.

## v0.7.6: the streamed code is native now, and the default look is modern

- **The menus, the loaders and the movies run as native code.** The game
  streams its overlay code from the disc into RAM, and everything that is not
  in the EXE used to run on the dirty-RAM interpreter: correct, but slow, and
  the only place where this build's emulation halts appeared. The runtime
  captures every executable image it runs (`overlay_captures.json` and its
  per-content history); `tools/gs_static/merge_captures.py` merges those with
  the GameShark patch's own captures and
  `psxrecomp/tools/compile_overlays.py --static` compiles them into guarded
  native shards. Measured on the intro movie, the heaviest interpreted code in
  the game:

  | | before | after |
  |---|---|---|
  | interpreted instructions per second | 17.7 M (`0x8011493C`) | **0** |
  | emulation ms per VBlank in the movie | 13.3-18.2 | **9.1-10.7** |
  | emulation CPU inside the worst interval | 22-30 ms | **13-17 ms** |

  32 shards, 16 712 exact function identities in 51 translation units (the
  GameShark patch alone was 10 shards / 12 171 identities / 18 units). The
  captures hold bytes read from the player's own disc, so they stay local
  (`tools/gs_static/all_captures.json` is gitignored); the recipe is in
  `docs/R4_OPTIMIZATION_GUIDE.md`.
- **The default look is no longer the console's.** The PS1 point-samples every
  texture and dithers every Gouraud-shaded polygon into 5 bits per channel;
  at 4x internal resolution and above both read as "1998" more than the
  resolution does. `game.toml` therefore ships `dithering = "off"` and
  `texture_filtering = "bilinear"` as the title's baseline, and the built-in
  mods keep them as "Game default", so the console look is one click away.
- **Optimization guide** (`docs/R4_OPTIMIZATION_GUIDE.md`): what causes each
  PlayStation artifact and how to fix it on this title, how to compile the
  streamed overlays, the Max Detail governor and the race spikes, how to
  measure a change instead of guessing, and the HD texture-pack workflow.
- **Known issue: an emulation halt in the attract loop.** In an unattended
  session (no input) this build can stop the emulation after 5-13 minutes with
  `DISPATCH FATAL: misaligned target ...` or `GPU GP0 unknown command 0xFD`.
  The mechanism is the GameShark 60 FPS code cave at `0x8000C210`: it replaces
  the game's handler dispatch (`jalr $ra,$v0` at `0x8001EC30`) and calls the
  handler pointer the game loaded from its handler table, and at the halt that
  pointer held a data value (`0x0EADF9A1`, `0x81CB002E`) because the game's
  own index/table lookup was out of range at that moment. The cave is not at
  fault for the pointer: it saves and restores `$ra`/`$s0`-`$s2` and never
  writes `$s3`, the table base. It is reproducible with the streamed code
  native and with the interpreter, so it is not an interpreter artifact; a
  session with the 60 FPS feature off ran 8 minutes without a halt, which
  points at the patch's timing rather than at the recompilation. The halt
  stops the emulation (the debug server stays up for post-mortem queries);
  the game is not playable afterwards.
