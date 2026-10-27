# Japanese 60 FPS / widescreen cheat comparison

Source: [AEONG_AEONG's GBAtemp post](https://gbatemp.net/threads/i-created-60-fps-widescreen-cheat-codes-for-ridge-racer-type-4.684958/) and its [linked V2 GameShark file](https://drive.google.com/file/d/1p3aJaVrNNJwRS2hOVIran1BSXO1lZxod/view). Read on 2026-10-26. The 99,085-byte file's SHA-256 is `687e619cfd619addcc26d4639ccc82e5905576f7a95c47156fe19d34c4c4340f`. It targets Japanese `SCPS-45356`; R4 recompiles US `SLUS-00797`. The cheat file is a reference, not a build input.

## What the 60 FPS code does

The first section contains 2,086 halfword writes. Most inject MIPS code at `0x8000C000..0x8000CE62`; five small hooks at `0x8001EB88..0x8001ECAA` enter that code. The entry checks the race pacing word against `0x180`, recognizes handlers, and uses a state flag for an extra draw. One helper changes `0x180` to `0x80` at the pacing call. Other hooks skip normal work during the extra draw. The injected mode paths repeat the game's draw-function calls. The author requires emulator CPU speed 300%.

Our `src/mods/r4_interp.c` already redraws between stock 30 Hz ticks, interpolates car/camera state, and has native worker preparation and render-pass isolation. Its draw lists were separately derived from dogewow2048's earlier Japanese patch, then mapped to US code. The new cheat is another example of this approach. Its injected single-threaded MIPS and altered guest pacing do not provide a transferable throughput improvement for the native worker pipeline.

The **control-flow placement** is valuable: the cheat makes an extra image a separate game-loop iteration. Its hooks at `0x8001EB88`, `0x8001EBFC`, `0x8001EC30`, `0x8001EC40`, and `0x8001ECA8` select the draw path and suppress work that belongs only to a logic tick. In contrast, our pass is called at the `VSync(0)` boundary (`r4_interp.c`'s `R4_RA_PASS_POINT`) and captures an isolated draw for the presenter. Thus the cheat is a concrete reference for frame ordering, buffer selection and which per-tick calls must not repeat. If a release-visible ordering defect is found, compare the native pass timeline against this sequence before rewriting the scheduler. Porting the *control-flow idea* would mean a native game-loop draw phase; the injected JP instructions cannot be copied into statically recompiled US C.

## Coverage difference

The V2 entry recognizes six handlers: three overlay race handlers, two EXE handlers, and `0x801165A8`, with a distinct sixth draw path at `0x8000CAB8`. The first three overlay handlers are consistently `0x2B8` below our mapped US Time Attack, Grand Prix, and VS addresses. The sixth maps to US `0x80116860`: R4.BIN entry 666 identifies itself as `job_ex_crs_info`, has handler opening words `27BDFFD0 3C03800F`, and the US EXE's row 1[82] points to that address. The US draw path calls the shared camera, cars, course, objects, and rear-view functions. Widescreen now recognizes this handler with a resident-code guard. The frame-rate classifier still has five modes; Extra Trial extra-frame redraw needs its own verified mode/call list before activation.

## Other sections

- The 16:9 section changes game UI/FOV. R4's native-wide renderer already exposes real side scenery and repositions HUD without patching guest instructions; it supports 16:9, 21:9, 32:9 and fit-to-window.
- The `CPU Marker` section adds opponent minimap markers in Grand Prix/Extra Trial. This is an optional gameplay display feature, not a frame-rate fix. R4's stock map and car dots remain available.
- The `16:9 FMV` section resizes the opening movie. R4 intentionally presents 4:3 movies with side bars, preserving their original composition. The cheat's movie resize should not become a default.

Decision: keep the current frame pipeline and release behavior because no ordering defect is currently demonstrated. Use the cheat's loop sequence as a reference if that changes. The US Extra Trial handler identity is now verified and used for widescreen scene recognition; extra-frame redraw remains separate. No Japanese GameShark writes belong in the US build.
