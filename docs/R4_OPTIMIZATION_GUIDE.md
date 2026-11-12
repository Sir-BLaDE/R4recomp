# R4 on PSXRecomp: removing the PlayStation look and the frame spikes

A practical guide for this title: what causes each "this looks like a PS1"
artifact, how to fix it, how to measure the result, and which parts of the
framework to touch when the game (not the host) is the bottleneck.

Everything here is specific to this repository: the paths, the mod ids and the
numbers come from this tree. Commands are given for a Windows checkout with the
shared toolchain (`cmake-clang-v1`); the same flags apply on Linux/macOS.

- The framework is a submodule: `psxrecomp/` (pinned in `framework_pins.txt`).
  R4-specific framework changes live in `patches/psxrecomp/0001-r4-framework.patch`
  and must be re-applied when the pin moves (`scripts/apply_framework_patches.sh`).
- The build directory used below is `build-release`.

---

## 0. The five artifacts and who owns them

| Artifact | Real cause | Where it is fixed |
|---|---|---|
| Blurry / pixelated image | 320x240 internal framebuffer, nearest filtering | **Internal Resolution** mod + **Image Filtering** mod (texture filtering, LOD, AA, dithering) |
| Geometry popping | The game drops polygons by distance | **Max Detail** mod (`draw_distance = maximum`) plus the 18 `[[draw_distance.clamp]]` sites in `game.toml` |
| 4:3 with black bars | GTE projection is 4:3 | GameShark 16:9 patch, or the framework's native-wide path |
| Frame drops | Emulation cost > 16.7 ms per VBlank | Emulation profile, Max Detail governor, PGO/LTO |
| Hitches (33-88 ms) | A frame that overruns, or a frame that is not emulated at all | See §2.5: tell *guest-side* from *host-side* before touching anything |

Most of the "PS1 look" is therefore **internal resolution + filtering + draw
distance**, and all three are configuration, not hacks.

---

## 1. Native coverage of the streamed code (do this first)

The game's EXE is fully recompiled, but R4 streams more code from the disc into
RAM (menus, loaders, the movie player). Code that is not in the EXE runs on the
**dirty-RAM interpreter**, which is correct but slow - and the interpreter is
also where this build's emulation halts come from (§1.3).

### 1.1 Capture the images the game loads

The runtime writes every executable dirty-RAM image it runs to
`overlay_captures.json` next to the executable, and keeps a per-content history
in `overlay_captures.json.d/`. Play the game once (intro, title, Grand Prix
menu, a race) and the menu/loader/movie regions are captured.

### 1.2 Merge them with the GameShark captures and compile them statically

```bash
# The GameShark 60 FPS / 16:9 code lives in kernel RAM and is written every
# VBlank, so it is captured from the patch's own word list:
python tools/gs_static/make_captures.py \
  --exe disc/SLPS_017.98 \
  --codes src/r4_gameshark_codes.h \
  --ranges generated/SLPS_017.98_full.ranges \
  --observed tools/gs_static/observed_pcs.json \
  --out tools/gs_static/gs_captures.json

# Merge both sources (identical capture schema) into one list:
python tools/gs_static/merge_captures.py \
  --out tools/gs_static/all_captures.json \
  --gs tools/gs_static/gs_captures.json \
  --runtime build-release/overlay_captures.json \
  --runtime-dir build-release/overlay_captures.json.d

# Compile every image into native shards (guard bytes protect each shard):
python psxrecomp/tools/compile_overlays.py --static \
  --captures tools/gs_static/all_captures.json \
  --game-toml game.toml \
  --recompiler psxrecomp/recompiler/build/psxrecomp-game.exe \
  --runtime-include psxrecomp/runtime/include \
  --out-dir generated/gs_overlays --flavor 2
```

`generated/gs_overlays/overlays_static.c` is the dispatcher and
`overlays_static_NNNN.c` the shards; `CMakeLists.txt` links them through
`GAME_OVERLAY_STATIC_C`. A shard is only used when its guard bytes match the
live RAM, so a stale image can never run.

### 1.3 What the interpreter costs, and the two halts it hides

With the menu/movie code interpreted, the intro movie ran at **30 fps with
25-30 ms frames** (17.7 M interpreted instructions per second at
`0x8011493C`), and the emulation **stopped** twice in an unattended session:

```
DISPATCH FATAL: misaligned target 0x0EADF9A1
GPU GP0 unknown command 0xFD (word 0xFD09B1F8)
```

The first is the GameShark 60 FPS code cave at `0x8000C210`: it replaces the
game's `jalr $ra,$v0` at `0x8001EC30` (the handler dispatch) with a jump into
the cave, which then calls the handler pointer the game loaded from its handler
table. When that table holds a data value instead of an address, the jump goes
to garbage. The second is a garbage GP0 word.

Both appear while the menu/movie code runs interpreted. Compiling those images
natively (§1.2) is the fix; the same images are the ones the perf log reports
as `interp=`.

### 1.4 If the overlay compiler refuses to run

The compiler refuses a stale recompiler (silent stale shards):

```
FATAL: STALE RECOMPILER BINARY.
```

Regenerate the codegen stamp after rebuilding the emitters:

```bash
cmake -DOUT="psxrecomp/runtime/include/overlay_codegen_hash.h" \
      -DPSXRECOMP_CODEGEN_HASH_ROOT="psxrecomp" \
      -P psxrecomp/runtime/hash_codegen.cmake
```

---

## 2. Performance

### 2.1 Build flags

```bash
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_TOOLCHAIN_FILE=psxrecomp/cmake/toolchain-mingw-w64.cmake \
      -DR4_NATIVE_CPU_SPANS=ON \
      -DPSX_RUNTIME_IPO=ON \
      -DPSX_PGO=<pgo-dir>
cmake --build build-release -j 2
```

| Flag | Effect | Risk |
|---|---|---|
| `R4_NATIVE_CPU_SPANS=ON` | Per-instruction native span timing. Measured **-19 %** emulation per VBlank (45.9 -> 37.0 ms) | Low; the repo default |
| `PSX_NATIVE_CPU_SPANS=OFF` | Cheaper CPU model, but the 60 FPS patch stops flipping 60 times per 60 VBlanks | Breaks 60 fps |
| `PSX_RUNTIME_IPO=ON` | LTO across the runtime | Keep the same toolchain; check the exe still starts |
| `PSX_PGO=<dir>` | Profile-guided optimization (see below) | Needs a reproducible training route |
| `PSX_EXECUTION_PROFILE=ENHANCED` | `REFERENCE` is the LLE oracle (slower) | - |
| `PSX_DEBUG_TOOLS=ON` | Adds `host_profile` (1 kHz IP sampling of the emulation thread) | ~4 % slower: diagnostics only |

PGO:

```bash
python psxrecomp/psxrecomp_cli.py pgo-train \
  --config game.toml --project-root . --build-dir build-release \
  --disc disc/R4.cue --train-secs 120 --train-runs 3
```

### 2.2 Runtime configuration

```toml
# game.toml
[video]
renderer = "opengl"             # the primary (and fastest) path here
internal_resolution = "display" # the launcher offers 1x..32x; 4x is the default
match_display_max_lines = 2160  # cap for "Match display"
dynamic_resolution = false      # no surface reallocation at runtime (a v0.2 hitch source)
render_thread = true            # GL work off the guest thread

[runtime]
idle_skip = true                # skip libetc v_wait's VSync spin
idle_skip_store_counters = true

[timing]
guest_cycle_scale = 3           # the GameShark readme's "CPU 300%"
guest_cycle_scale_gated = true
```

### 2.3 The Max Detail governor (where the spikes were)

Level semantics: `level + 2` = track sections loaded ahead; `level -2` = stock
draw distance (no extra sections).

- The **floor is the expensive state**, not the cheap one: with no sections
  kept, the game loads the course sections itself, and that reload is the most
  expensive frame of the race.
- The governor used to slam the level down whenever a single frame went over
  the budget - often its own level change - and the drop's own frame went over
  budget too, so the reaction cascaded to the floor and back every 10-20 s.
  Each pass through the floor cost a late VBlank.

**Fixed in 0.7.5** (`src/max_detail/r4_max_detail.h`,
`src/max_detail/r4_max_detail_plugin.c`): the floor is now the floor of the
*view*. A normal view can hold the extra sections, so it keeps two sections
ahead (level 0) as its floor, and a change of view width no longer slams the
level down from a high one. A very wide view (about 30:9 on) still falls back to
the stock draw distance, because its extra octants overrun the grid.

Measured on the same race, same build:

| | 0.7.4 | 0.7.5 |
|---|---|---|
| late VBlanks | 1.03 % | **0.40 %** |
| frames over 20 ms | 38 % | 19 % |
| worst interval | 29.6 ms | **24.4 ms** (none over 25 ms) |
| windows at level -2 | 101 | **0** |

Developer A/B switches (see the plugin source): `R4_MD_HOST_MS=<ms>`,
`R4_MD_SECTIONS=<n>`, `R4_MD_AHEAD` / `R4_MD_BEHIND`, `R4_MD_TRACE=2`,
`R4_MD_BIG_HEAP=0`, `R4_MD_FAR_CARS=<n>`. Pinning the sections
(`R4_MD_AHEAD=2 R4_MD_BEHIND=1`) is the quickest way to tell "the sections
cost" from "changing the section count costs".

### 2.4 Mods that change what the guest has to draw

| Mod | Option | Effect on cost |
|---|---|---|
| Max Detail | `draw_distance` | Maximum keeps 2-32 sections ahead (more guest work, no popping) |
| Max Detail | `course` / `cars` = always full | Full-resolution textures and full car models |
| Max Detail | `reflections` | Stock in wide views: a reflective car body is drawn many times slower there |
| Max Detail | `mirror` = stock | Full draws all the scenery behind you (the most expensive part of the package) |
| Max Detail | `cpu_budget` | 14.5 ms (balanced) / 12.5 ms (safe) / no limit |
| PGXP Precision | precise culling | **Off**: it keeps sub-pixel polygons the PS1 dropped, the guest runs out of CPU and the game drops frames at 45-57 fps |
| 8 MB RAM | - | More RAM for the guest |
| CD speed / fast loading | - | Load times, not frame time |

### 2.5 Measuring instead of guessing

**The game's own log** (`R4_PERFLOG_ALL=1` writes `R4_perf_log.txt` next to the
executable, one line per second):

```
21:44:17 frame=12120 late=3/60 worst=29.6ms(busy 12.5) avg=16.7ms fps=60 emu=81% emu_ms=13.02 md=-2/12.5 interp=2340
```

- `worst=..ms(busy ..)`: the longest VBlank interval and the **emulation CPU
  inside it**. `busy << worst` means the thread was not emulating (host, GPU,
  OS); `busy ~ worst` means the guest overran its budget.
- `md=<level>/<ms>`: the Max Detail governor's level and its cost per frame.
- `interp=`: interpreted instructions per window. 0 means everything is native.

**The debug server** (`PSX_DEBUG_SERVER=1`, TCP 4370, `psxrecomp/docs/TCP_COMMANDS.md`):

```bash
python psxrecomp/tools/debug_client.py --port 4370 frame
python psxrecomp/tools/debug_client.py --port 4370 host_profile frame_lo=12000 frame_hi=13600
python psxrecomp/tools/debug_client.py --port 4370 frame_wall_ring from=0 n=6000
python psxrecomp/tools/debug_client.py --port 4370 host_span_ring from=0 n=65536
python psxrecomp/tools/debug_client.py --port 4370 render_thread
```

`host_profile` (needs `PSX_DEBUG_TOOLS=ON`) resolves the emulation thread's
samples to symbols. On this title it showed ~84 % inside the executable, ~11 %
in `ntdll` (the frame pacer waiting) and ~7 % in PGXP
(`psx_pgxp_load` / `psx_pgxp_alu` / `psx_pgxp_store`).

**Scripting the route** makes A/B runs comparable: `press`, `set_input`,
`input_route_append` / `input_route_start`, `screenshot`, `run_to_frame`,
`turbo`, `pause`, `quit` are the commands that matter.

### 2.6 If the host is the bottleneck

- `render_thread = true` and `dynamic_resolution = false`: the guest thread
  never waits for a surface reallocation.
- `render_thread`'s `backpressure_waits` / `ring_full_waits` (TCP) grow when the
  guest waits for the renderer: lower the internal resolution.
- Windows timer resolution: the pacer waits on a high-resolution waitable
  timer; if the system timer is coarse (`NtQueryTimerResolution`), the wake-up
  jitters.

---

## 3. HD art

### 3.1 The format

`psxrecomp` implements a bounded subset of the DuckStation texture-pack
format (`psxrecomp/docs/DUCKSTATION_TEXTURE_FORMAT.md`). A pack is a folder
with `replacements/` and `dumps/`:

```
<pack>/
├── replacements/   # PNG / JPEG / static WebP, named like the original texture
└── dumps/          # what the game captures if "Dump textures" is enabled
```

Paletted filename stems follow:

```
<kind>-<mode>-<sourceHash>-<paletteHash>-<sourceWords>x<sourceHeight>-<offsetX>-<offsetY>-<width>x<height>-P<min>-<max>
kind = texupload | texpage
mode = P4 | P8 | STP4 | STP8
```

For R4 the names are computed offline from the patched R4.BIN
(`tools/r4_hd/build_pack.py`), because the `texupload` keys depend on the 16:9
patch.

### 3.2 Installing a pack

1. **Mods -> Visual -> HD Texture Packs**, enable it.
2. **Texture pack folder -> Open folder**: the launcher creates
   `mods/texture-packs/<game-id>` with empty `replacements/` and `dumps/`.
3. Copy the replacement images into `replacements/`, names preserved.
4. **Load replacements** on, **Dump textures** off, renderer **OpenGL**
   (software and Vulkan collect dumps but show the original artwork).
5. Play.

Running the executable without the launcher needs the package to carry its
`pack/` folder (an empty one with a README is enough); otherwise the launch
fails with *"required resource not selected: pack"*.

### 3.3 Where packs come from

| Source | What it gives |
|---|---|
| `github.com/Kuid0us/T4HDHUD` | The HD HUD: rank/record/lap digits, speedometer, RPM gauge, course maps |
| This repository's `mods/preloaded/packages/psx.enhancement.hd-textures/1.0.0/pack/` | Menu sheets, PAL billboards, endings, the HD Spanish font, 2D sheets at 4x, course textures |
| DuckStation community packs | Same format; rename to R4's `texupload` keys with `build_pack.py` |
| `mstan/TombaRecomp/examples/hd-texture-pack` | Minimal template to start from |

Artwork carries its own rights: no pack with original game art may be
redistributed. The pipeline is in this repository, the artwork is not.

### 3.4 Building your own pack

```bash
python3 tools/r4_hd/build_pack.py \
  --jp R4_JP.bin --eu R4_PAL.bin \
  --spanish mods/preloaded/packages/r4.spanish/1.0.0 \
  --esrgan-art RealESRGAN_x4plus_anime_6B.pth \
  --esrgan-photo RealESRGAN_x4plus.pth --courses \
  --dumps <DumpTexturePages dump dir> \
  --out mods/preloaded/packages/psx.enhancement.hd-textures/1.0.0/pack/replacements
```

`--cache <dir>` resumes finished sheets, `--cluts <capture>` adds sheets with
their own CLUT. Build-time-only dependencies: `xbrz.py` (GPL-3), Real-ESRGAN,
waifu2x. Ship smaller packs with `tools/hd_pack_optimize.py` (lossless WebP:
3704 PNG / 151 MiB -> 3098 WebP / 91 MiB). The runtime's preload cap lives in
`gpu_hd_textures.cpp` (512 -> 768 MiB).

### 3.5 There are no "HD models"

PS1 3D is polygons: the equivalent upgrades are PGXP (perspective texturing and
geometry correction), Max Detail's full car models and course detail, and the
draw distance. Texture upscale (Real-ESRGAN) covers the course art.

---

## 4. The wider ecosystem

| Project | Use |
|---|---|
| `RetroPortingToolKit/psxrecomp` | The framework (this repo's `psxrecomp/` submodule) |
| `mstan/TombaRecomp` | Another title with the reference `psx.hd-textures` package and an example pack |
| `tetrisgm/RidgeRacerType4Recomp` | The **USA** R4 recomp; source of the address-translation tooling (`tools/us_port/translate_mods.py`) and of several R4 patches |
| The R4 **matching decomp** (PAL) | Splat project whose main EXE builds byte-identical to retail: the best reference for symbols, layouts and exact disassembly |
| `stenzek/duckstation` | Texture-pack format, aggressive widescreen, and a way to dump source artwork |
| `libretro/beetle-psx-libretro` | The framework's **oracle** (dynarec); the framework patches it for tracing. Use it to judge correctness, not as a substitute |
| `RetroPortingToolKit/Retro-Launcher` | The launcher that installs the player, the BIOS and the save plumbing |
| `recomp.fyi`, `unbaked.games` | Live status of every recomp/decomp project |

The framework is LLE-first: the recompiled BIOS (OpenBIOS or retail) is the
kernel and the oracle. A patch that looks right but changes timing or IRQ
order is not acceptable - check it with `PSX_EXECUTION_PROFILE=REFERENCE` and
`psxrecomp/docs/PARITY_CAMPAIGN.md`.

---

## 5. The rest of the "modern" look

- **Presentation**: internal resolution 4x/8x, supersampling, `fxaa_hq` via
  `antialiasing_mode`, bloom and a custom `post_shader` (`*.pfx`) through
  `psxrecomp/docs/POST_EFFECTS.md`, dithering off, bilinear texture filtering,
  anisotropic filtering 16x, `texture_lod`.
- **CRT filter**: turn it *off* for a modern look (the mod keeps the tube and
  scanline options for nostalgia).
- **Widescreen**: the GameShark patch gives a fixed 16:9 (stretched). The
  framework's native-wide path needs a per-title view setup
  (`psxrecomp/docs/NATIVE-WIDE-PROJECTION.md`, `WIDESCREEN.md`).
- **Frame generation**: `psx_mod_set_frame_interpolation(120|240)` presents
  between guest VBlanks without touching the game's logic
  (`psxrecomp/docs/FRAME_RATE.md`); the feature must declare `vsync = "off"`.
- **Movies**: `fmv_chroma_smoothing` plus the FMV filter in *Image Filtering*;
  the runtime's FMV HD path is documented in `FMV_HD_TIMELINE.md`.
- **Audio**: *Enhanced Audio* -> `spu_hq`.
- **Controls**: `r4.controls` presents the pad as a JogCon (R4 only steers
  analog with one): dial = left stick X, R1/RT/Cross accelerates,
  L1/LT/Square brakes, `R4_ANALOG_MODE=negcon` for the NeGcon.
- **Comfort**: *Rewind* (`psx.feature.rewind`), save states, 8 MB RAM,
  `warm_cd_route` for a near-instant boot.

---

## 6. Do not

- Apply the GameShark codes without the `D001EB86 AE40` guard: it would write
  into kernel RAM before the EXE is loaded.
- Edit the `expected` words of the `[[draw_distance.clamp]]` sites: they are
  byte guards, and a mismatch silently reverts the draw distance.
- Enable PGXP precise culling on this title: the guest runs out of CPU and the
  game drops frames by itself.
- Enable reflections in a wide view: the renderer draws those parts many times
  slower (measured 10x at 4K on an M4).
- Raise `guest_cycle_scale` to x4/x6: with the 60 FPS patch the frame ends
  before the VBlank and `VSync(0)` returns early, so the game runs ~1.2x fast
  and its timers desynchronize. x3 is the patch's own setting.
- Commit disc images, BIOS dumps or original game art. `generated/` is code
  and belongs in the repository; packs and captures stay local.

---

## 7. Release checklist

```bash
# 1. regenerate the game C and the static overlays from the player's disc
python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . --disc disc/R4.cue

# 2. merge and compile the captured overlays (menus, loaders, movies)
python tools/gs_static/merge_captures.py --out tools/gs_static/all_captures.json \
    --gs tools/gs_static/gs_captures.json \
    --runtime build-release/overlay_captures.json \
    --runtime-dir build-release/overlay_captures.json.d
python psxrecomp/tools/compile_overlays.py --static \
    --captures tools/gs_static/all_captures.json --game-toml game.toml \
    --recompiler psxrecomp/recompiler/build/psxrecomp-game.exe \
    --runtime-include psxrecomp/runtime/include \
    --out-dir generated/gs_overlays --flavor 2

# 3. build and stage the player package
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE=psxrecomp/cmake/toolchain-mingw-w64.cmake \
    -DR4_NATIVE_CPU_SPANS=ON
cmake --build build-release -j 2
packaging/stage_windows.sh build-release "$(cat VERSION)"
```

The package stages the executable, the launcher assets, OpenBIOS with its
licence, a player `game.toml` without a machine-specific disc path, the mod
catalog, the licences and `START_HERE.txt`. No disc image, BIOS dump or
original artwork is shipped.
