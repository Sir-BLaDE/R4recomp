#!/usr/bin/env python3
"""Write the r4.spanish package manifest from build_es.py output.

    python3 tools/r4_es/make_manifest.py --exe disc/SLPS_017.98 --jp-disc R4_JP.bin \
        --pack mods/preloaded/packages/r4.spanish/1.0.0

Code patches (Japanese executable, all guarded by their exact stock words):
  * glyph cell geometry 12x24 / 21 per row -> PAL 8x24 / 32 per row
    (and the second-page threshold 210 -> 320),
  * glyph sprite width 12 -> 8, pen advance 11 -> 7 (both renderer sites),
  * message-window glyph-state array 64 -> 200 entries, as the PAL build:
    struct size 0x128 -> 0x348 (init clear and the bump allocator of window #1),
    both per-page clear loops (count 63 -> 199, base +0xfc -> +0x31c).
Window #2 is a static object followed by other data, so the trusted plugin
r4.spanish (src/r4_spanish.c) moves it to enhancement memory at runtime.
"""
import argparse
import hashlib
import json
import struct

BASE = 0x80010000


def nop_block(start, n):
    return [(start + 4 * i, 0) for i in range(n)]


PATCHES = (
    # glyph geometry: 0x8001fcdc..0x8001fd14 (bnez/move/addiu after stay)
    nop_block(0x8001FCDC, 8) + [
        (0x8001FCFC, 0x00061943),   # sra   v1, a2, 5        row
        (0x8001FD00, 0x30C2001F),   # andi  v0, a2, 31       column
        (0x8001FD04, 0x0002F0C0),   # sll   fp, v0, 3        u = col*8
        (0x8001FD08, 0x00031040),   # sll   v0, v1, 1
        (0x8001FD0C, 0x00431021),   # addu  v0, v0, v1
        (0x8001FD10, 0x000210C0),   # sll   v0, v0, 3        v = row*24
        (0x8001FD14, 0x28C60140),   # slti  a2, a2, 0x140    second page >= 320
        (0x8001FD1C, 0x24560004),   # addiu s6, v0, 4        v + 4 (rows 4..21)
        (0x8001FD20, 0x24560014),   # addiu s6, v0, 0x14     second page v + 4
    ],
    [(0x8001FE48, 0x24020012)],     # glyph sprite height 18 (cell rows 4..21)
    [(0x8001FF90, 0x26940016),      # row advance 22 (newline)
     (0x80020080, 0x26940016)],     # row advance 22 (glyph + newline)
    [(0x8001FE40, 0x24020008)],     # glyph sprite width 8
    [(0x80020034, 0x26520005),      # pen advance 5 (space)
     (0x80020078, 0x26520005)],     # pen advance 5 (glyph)
    [(0x80032ED0, 0x24050348)],     # window init clears 0x348 bytes
    [(0x80033084, 0x240500C7),      # page clear loop: 200 entries
     (0x800330DC, 0x2604031C),      #   from s0+0x31c
     (0x80033270, 0x240500C7),      # next-page clear loop: 200 entries
     (0x80033274, 0x2606031C)],     #   from s0+0x31c
    [(0x8003BBD0, 0x24420348)],     # window #1 bump allocation 0x348
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--jp-disc", required=True)
    ap.add_argument("--pack", required=True)
    a = ap.parse_args()

    exe = open(a.exe, "rb").read()

    def word(addr):
        o = addr - BASE + 0x800
        return struct.unpack("<I", exe[o:o + 4])[0]

    h = hashlib.sha256()
    with open(a.jp_disc, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    disc_sha = h.hexdigest()
    ov = json.load(open(f"{a.pack}/overlays.json"))

    L = []
    w = L.append
    w('format_version = 5')
    w('id = "r4.spanish"')
    w('version = "1.0.0"')
    w('name = "R4 en español (textos de la versión PAL)"')
    w('author = "R4Recomp; Spanish text and font from the player\'s own PAL disc (SCES-01706)"')
    w('description = "Grand Prix dialogues and system messages in Spanish, taken from the PAL release and drawn with its Latin-1 font by the Japanese engine."')
    w('resolver = "declarative"')
    w('save_compatibility = "shared"')
    w('')
    w('[[target]]')
    w('game_id = "SLPS-01798"')
    w(f'disc_sha256 = "{disc_sha}"')
    w('')
    w('[[feature]]')
    w('id = "spanish"')
    w('name = "Textos en español"')
    w('description = "Diálogos del Gran Premio y mensajes del sistema en español (traducción oficial de la versión PAL)."')
    w('group = "Localization"')
    w('default_enabled = true')
    w('')
    w('[[plugin]]')
    w('feature = "spanish"')
    w('id = "r4.spanish"')
    for group in PATCHES:
        for addr, new in group:
            old = word(addr)
            w('')
            w('[[patch]]')
            w('feature = "spanish"')
            w('target = "main_exe"')
            w(f'address = 0x{addr:08X}')
            w(f'expected = "{struct.pack("<I", old).hex(" ")}"')
            w(f'replace = "{struct.pack("<I", new).hex(" ")}"')
    for o in ov["overlays"]:
        w('')
        w('[[overlay]]')
        w('feature = "spanish"')
        w('target = "disc_user"')
        w(f'offset = {o["offset"]}')
        w(f'file = "{o["file"]}"')
        w(f'sha256 = "{o["sha256"]}"')
        w(f'expected_sha256 = "{o["expected_sha256"]}"')
    open(f"{a.pack}/manifest.toml", "w").write("\n".join(L) + "\n")
    print(f"{a.pack}/manifest.toml written; disc {disc_sha}")


if __name__ == "__main__":
    main()
