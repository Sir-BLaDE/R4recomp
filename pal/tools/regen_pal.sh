#!/bin/sh
# PAL (SCES-01706) regeneration chain, run from anywhere inside the repo:
#   NTSC patches (pal/ntsc_patches.toml) -> game_pal.toml -> generated_pal/ (recompiled C).
# It does not build: configure and build with cmake -DR4_REGION=PAL (pal/README.md).
#
# Inputs: generated/ (USA C, committed), disc/SCES_017.06 (your own PAL boot EXE, gitignored),
# the psxrecomp-game generator. Environment overrides:
#   PSXRECOMP_GAME  generator (default psxrecomp/recompiler/build/psxrecomp-game)
#   PAL_EXE         PAL boot executable (default disc/SCES_017.06)
#   PYTHON          Python 3 interpreter (default python3, then python)
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

GEN=${PSXRECOMP_GAME:-psxrecomp/recompiler/build/psxrecomp-game}
PAL_EXE=${PAL_EXE:-disc/SCES_017.06}
if [ -z "${PYTHON:-}" ]; then
    if python3 -c "" >/dev/null 2>&1; then PYTHON=python3; else PYTHON=python; fi
fi
export PYTHONIOENCODING=utf-8

if [ ! -f "$PAL_EXE" ]; then
    echo "regen_pal.sh: $PAL_EXE not found (extract SCES_017.06 from your own disc)" >&2
    exit 1
fi

"$PYTHON" -I pal/tools/make_ntsc_patches.py generated "$PAL_EXE" \
    pal/manual_addresses.txt pal/ntsc_patches.toml
"$PYTHON" -I pal/tools/make_game_pal.py game.toml pal/probe_sces01706.json generated "$PAL_EXE" \
    game_pal.toml pal/ntsc_patches.toml pal/manual_patches.toml
"$GEN" --config game_pal.toml
echo "generated_pal/ is up to date. Re-run cmake on existing PAL build trees if the shard count changed."
