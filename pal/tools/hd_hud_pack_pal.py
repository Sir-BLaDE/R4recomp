#!/usr/bin/env python3
"""PAL (SCES-01706) HD HUD text atlas.

The PAL game uploads the Japanese km/h text atlas (upload c41643fd), not the US
mph one (32203df6) the bundled pack carries; every other HUD upload and CLUT is
byte-identical to the US game, so those pack files apply unchanged. This builds
c41643fd-{bf9158c6,3cba29b4,db4fb359}.png from the upstream T4HDHUD art with the
same repair rules as tools/r4_hd_hud_pack.py (glyphs a palette's art leaves
empty come from another palette, recoloured; glyphs no art covers are 8x
Scale2x upscales of the native glyph), using native references of the PAL
upload decoded with each CLUT (c41643fd-<clut>.png, native size).

  pal/tools/hd_hud_pack_pal.py --upstream T4HDHUD/RidgeRacerType4-texture-replacements \
      --native DIR_OF_PAL_NATIVE_REFS --out OUT_DIR
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
import r4_hd_hud_pack as base  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", type=pathlib.Path, required=True)
    ap.add_argument("--native", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    base.ATLAS = ("c41643fd", "c41643fd", ["bf9158c6", "3cba29b4", "db4fb359"], [])
    log = []
    base.build_atlas(a.upstream, a.native, a.out, log)
    print(json.dumps({"notes": log}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
