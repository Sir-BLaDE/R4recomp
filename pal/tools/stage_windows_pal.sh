#!/usr/bin/env bash
# Stage + zip a Windows x64 PAL (SCES-01706) player package from a MinGW cross
# build on Linux (tools/package_release.sh covers native builds only).
#
#   pal/tools/stage_windows_pal.sh <build-win-dir> <version>
#
# Ships: the executable, OpenBIOS, launcher assets, postfx, the player
# game.toml, the build's mod catalog, notices, a Spanish START_HERE.txt and an
# empty disc/ folder. The executable carries the recompiled PAL game code
# (generated_pal, from the player's disc): private builds only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$(cd "$1" && pwd)"
VERSION="$2"
FW="$ROOT/psxrecomp"
NAME="r4-runtime"
STAGE="$ROOT/dist/stage/R4-PAL-v${VERSION}-windows-x64"
ZIP="$ROOT/dist/R4-PAL-v${VERSION}-windows-x64.zip"

rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE/bios" "$STAGE/licenses" "$STAGE/disc"

cp "$BUILD/$NAME.exe" "$STAGE/"
cp "$BUILD/psx_game_version.txt" "$STAGE/"
cp -r "$BUILD/assets" "$STAGE/assets"
# Stock launcher skin (default) instead of the R4 skin.
rm -rf "$STAGE/assets/skins/r4"
cp -r "$ROOT/postfx" "$STAGE/postfx"
cp "$BUILD/bios/openbios.bin" "$BUILD/bios/OpenBIOS.LICENSE" "$STAGE/bios/"
cp "$BUILD/game.toml" "$STAGE/game.toml"
cp "$ROOT/game_options.toml" "$STAGE/"

python3 "$FW/tools/release_stage.py" stage-mods --build-path "$BUILD" \
    --stage "$STAGE" --runtime-target psx-runtime
python3 "$FW/tools/mod_channel_filter.py" "$STAGE/mods/bundled"

for f in "$FW"/runtime/licenses/*; do [ -f "$f" ] && cp "$f" "$STAGE/licenses/"; done
cp "$FW/LICENSE" "$STAGE/licenses/psxrecomp-LICENSE"
[ -f "$FW/THIRD_PARTY_ATTRIBUTION.md" ] && cp "$FW/THIRD_PARTY_ATTRIBUTION.md" "$STAGE/licenses/psxrecomp-THIRD_PARTY_ATTRIBUTION.md"
cp "$ROOT/recomp-ui/LICENSE" "$STAGE/licenses/recomp-ui-LICENSE"
cp "$ROOT/recomp-ui/third_party/imgui/LICENSE.txt" "$STAGE/licenses/dear-imgui-LICENSE.txt"
cp "$FW/lib/recomp-net/LICENSE" "$STAGE/licenses/recomp-net-LICENSE"
cp "$FW/lib/retcomm-rbengine/LICENSE" "$STAGE/licenses/retcomm-rbengine-LICENSE"
cp "$ROOT/recomp-ui/LICENSES/recomp-ui-MIT.txt" "$STAGE/licenses/recomp-ui-upstream-MIT.txt"
cp "$ROOT/LICENSE" "$STAGE/LICENSE"
[ -f /usr/share/doc/mingw-w64-common/copyright ] && cp /usr/share/doc/mingw-w64-common/copyright "$STAGE/licenses/mingw-w64-runtime-COPYING.txt"
[ -f /usr/share/doc/mingw-w64-x86-64-dev/copyright ] && cp /usr/share/doc/mingw-w64-x86-64-dev/copyright "$STAGE/licenses/mingw-w64-x86-64-dev-COPYING.txt"
mkdir -p "$STAGE/THIRD-PARTY-LICENSES" && cp "$ROOT/THIRD-PARTY-LICENSES/README.md" "$STAGE/THIRD-PARTY-LICENSES/"
for sub in fonts img; do
    n="$ROOT/recomp-ui/assets/common/$sub/NOTICE.md"
    [ -f "$n" ] && cp "$n" "$STAGE/assets/$sub/NOTICE.md"
done
sed "s/@VERSION@/${VERSION}/" "$ROOT/pal/START_HERE_ES.txt" | sed 's/$/\r/' > "$STAGE/LEEME.txt"

python3 "$FW/tools/release_stage.py" stage-execution --binary "$STAGE/$NAME.exe" \
    --manifest "$BUILD/$NAME.execution.json" --output "$STAGE/$NAME.execution.json"

bad=$(cd "$STAGE" && find . -type f \( -iname '*.bin' -o -iname '*.cue' -o -iname '*.chd' \
      -o -iname '*.iso' -o -iname '*.mcd' -o -iname '*.mcr' \) ! -path './bios/openbios.bin')
if [ -n "$bad" ]; then echo "refusing: disc/save data staged: $bad" >&2; exit 1; fi
if objdump -p "$STAGE/$NAME.exe" | awk '/DLL Name:/{print $3}' | grep -iE '^(lib|sdl|zlib)'; then
    echo "refusing: non-system DLL imports" >&2; exit 1
fi

(cd "$(dirname "$STAGE")" && zip -qr9 "$ZIP" "$(basename "$STAGE")")
sha256sum "$ZIP" | sed "s#  .*/#  #" > "$ZIP.sha256"
echo "$ZIP"
