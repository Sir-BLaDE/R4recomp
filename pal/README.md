# PAL build: R4 (Europe, SCES-01706)

This directory adds a second target to the project: the European disc
**R4: Ridge Racer Type 4 (Europe) (En,Fr,De,Es,It)**, SCES-01706 (Redump). It is
the same game as SLUS-00797 with five message languages, but its executable was
rebuilt for 50 Hz / 256-line PAL output: the game logic runs at 25 Hz, every
timer is counted in 25 Hz frames, and the frame buffers, viewports and HUD are
laid out for 256 lines.

The PAL build "NTSC-ises" that code: the recompiled PAL executable runs the USA
30 Hz logic on a 240-line display, so it plays like the USA build (60 fps
presentation, same speed, same lap times) while keeping the PAL disc's languages.
Everything is derived automatically from the USA project, plus a short list of
hand-checked sites. No PAL disc data is in the repository: the PAL C code is
generated locally from your own disc.

## Build

You need:

- your own SCES-01706 dump (bin/cue) and its boot executable `SCES_017.06`,
  extracted from it, in `disc/` (both gitignored);
- the recompiler built (`psxrecomp/recompiler/build/psxrecomp-game`; set
  `PSXRECOMP_GAME` to use another one);
- Python 3.

```sh
sh pal/tools/regen_pal.sh            # NTSC patches -> game_pal.toml -> generated_pal/
cmake -S . -B build-pal -G Ninja -DCMAKE_BUILD_TYPE=Release -DR4_REGION=PAL
cmake --build build-pal
```

`regen_pal.sh` only generates; it never builds. Re-run it when `game.toml`,
`generated/` or the files in `pal/` change, then re-run cmake (the number of
generated shards is read at configure time). On Windows the generator needs the
runtime DLLs of the toolchain it was built with on `PATH`.

`game_pal.toml` and `pal/ntsc_patches.toml` (with its report) are generated but
committed, so a change to the USA config shows its PAL effect in review. The PAL
build itself always needs your disc: `generated_pal/` is generated from it, and
configuring reads `disc/SCES_017.06` to translate the mod plugins.

The default build (`-DR4_REGION=USA`, or no option) is unchanged.

## How it works

1. **Address map** (`pal/tools/r4map.py`). The USA generated C carries every
   instruction word in comments. Each USA function is matched to the PAL
   executable by its masked instruction words (relocations ignored): unique
   4-word windows first, then neighbours at the same displacement for short or
   ambiguous functions. Data addresses come from LUI/lo pairs of the functions
   that match 100 %, as intervals with a constant displacement. Overlay entry
   points (R4.BIN, base USA 0x801149A8 / PAL 0x80114878) and the few functions
   PAL rewrote are listed by hand in `pal/manual_addresses.txt`, each with its
   justification. `python pal/tools/r4map.py generated disc/SCES_017.06 0x8002C0F8`
   translates addresses on the command line.
2. **NTSC patches** (`pal/tools/make_ntsc_patches.py` -> `pal/ntsc_patches.toml`).
   For every matched function, each instruction word that differs from the USA
   one is classified: a relocation (the PAL address is the translation of the
   USA address: ignored), a constant (same instruction and registers, another
   immediate: patched back to the USA value) or anything else (listed in the
   report, `pal/ntsc_patches.report.txt`). This gives 230 recompiler patches:
   SetVideoMode(NTSC), the 25 -> 30 Hz timer constants and the 256 -> 240 line
   layout. `pal/ntsc_exclusions.txt` lists the few PAL-only differences that must
   stay; `pal/manual_patches.toml` holds 27 hand-written patches for functions
   PAL rewrote (timer text, countdown, a 120 s cap, the display height and a race
   layer's draw area).
3. **Game config** (`pal/tools/make_game_pal.py` -> `game_pal.toml`). `game.toml` is
   rewritten for the PAL disc: identity, digests and netplay gate from
   `pal/probe_sces01706.json`, seeds `seeds/pal_funcs.txt` (the PAL boot EXE's
   JAL targets plus the translated USA function starts), output
   `generated_pal/`, every address translated by the map. A list element that
   cannot be translated is commented out (reported in
   `game_pal.toml.report.txt`, not committed); an untranslatable scalar is an
   error. The NTSC patches and the manual patches are appended.
4. **Mods** (`pal/tools/translate_mods.py`). At configure time `src/mods` is
   copied into the build directory (`build-pal/mods_pal/`) with every address
   literal translated; an untranslatable one becomes an impossible address, so
   that hook stays inert, and is listed in `mods_pal/translation.txt`. The
   packages of `mods/preloaded` are retargeted to SCES-01706 in the build
   directory, with the Max Detail car-table addresses moved to their PAL
   location. PAL builds define `R4_REGION_PAL`, so a mod can use PAL-only code
   such as `r4_pal_message_language()` (`pal/mods/r4_pal_ntsc.h`).
5. **PAL module** (`pal/mods/r4_pal_ntsc.c`, package `r4.pal.ntsc`). Always on
   in the PAL build, it handles the functions PAL rewrote for 25 Hz / 256 lines
   that no constant patch can fix:
   - race frames -> milliseconds of the lap timer (USA 30 Hz formula);
   - display init: frame buffer heights 256 -> 240 and the DISPENV y offset;
   - per-primitive draw areas of the second buffer (n * 256 -> n * 240);
   - race viewports, split-screen windows and HUD sprite templates, rewritten
     for 240-line buffers before the first race;
   - split-screen lap counter and race messages (n - 1) * 128 -> (n - 1) * 120;
   - the default message language (option, see below).
   `pal/instruction_sites_pal.txt` and `pal/mod_entries_pal.txt` declare its hook
   sites to the recompiler.
6. **Launcher** (`launcher/title_r4.cpp`). The same title layer serves both
   discs; with `R4_REGION_PAL` it names SCES-01706 and skips the disc-sourced
   menu art (see Known differences).

## Options

- **Message language** (Mods page, R4 PAL > Message language > Language:
  English, French, German, Spanish or Italian; default English, the game's own
  default): the language the game starts in before a saved setting is loaded.
  It is written at boot only while the game's language is still unset. The PAL
  game also has its own selector; a memory card setting always wins.

The launcher itself can be shown in French in any build: `launcher/i18n/fr.json`
is staged next to recomp-ui's translations; select it with
`-DR4L_UI_LANGUAGE=fr` or the `R4L_LANGUAGE=fr` environment variable.

## Status

Tested on Windows 11 (i5-12400F, RTX 3060, OpenGL): intro, menus (Grand Prix,
Time Attack, Garage, Records, Options), Time Attack races on Helter Skelter
(complete laps, 60 fps), VS battle in split screen with two pads, and the attract
demo over long sessions (day and night tracks). The lap timer runs at the USA
33.3 ms per frame and the time limit in real time. Not verified yet: a full
Grand Prix season and the ending movie, memory card save/load. One attract-demo
crash was seen once in two long runs (an invalid sub-mode at 0x800F3A26, under
investigation).

Known differences:
- A few PAL-rewritten functions still count durations in 25 Hz frames (about
  20 % faster): the start camera (0x80045868), two fades (0x80059E40,
  0x800483D8) and a random modulo of the timer (0x8003C278). Cosmetic.
- Link Battle (cable / online) overlay hooks are not translated yet (R4.BIN
  overlay addresses have no automatic USA -> PAL map).
- The HD HUD package is off by default in the PAL build: its texture lookups
  saturated the render thread in races (27 fps measured). It can be turned on
  in the Mods page.
- The launcher art (logo and font read from R4.BIN) is not located on the PAL
  disc; the launcher keeps its default skin.
- The first-run setup wizard prepares the USA disc only, so it is off in the
  PAL build: put the PAL files in `disc/` yourself.
