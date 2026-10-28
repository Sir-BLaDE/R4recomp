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

## Framework patches

`psxrecomp` is pinned at upstream `a38bf783`; the R4 changes to it (HD
texture matcher caches, per-texel STP for replacements, PGXP store-ring
allocation in debug builds only, borderless window overhang) live in
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
