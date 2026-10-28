#!/usr/bin/env bash
# Compile overlay captures (from a debug run: overlay_capture_dump) into
# generated_pal/overlays_static/ for a private PAL build. The captures hold
# code bytes read from the disc: they and the output stay local
# (pal/private/, generated_pal/ are ignored).
#
#   pal/tools/build_static_overlays.sh pal/private/overlay_captures_pal.json <flavor>
# <flavor>: the build's psxrecomp_overlay_flavor-psx-runtime.txt (2 = PGXP hooks).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CAP="$(realpath "$1")"; FLAVOR="${2:-2}"
cd "$ROOT"
python3 psxrecomp/tools/compile_overlays.py --static --force \
    --captures "$CAP" --game-toml game_pal.toml \
    --recompiler psxrecomp/recompiler/build/psxrecomp-game \
    --runtime-include psxrecomp/runtime/include \
    --out-dir generated_pal/overlays_static --flavor "$FLAVOR"
