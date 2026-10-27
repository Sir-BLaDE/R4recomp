#!/usr/bin/env bash
# Stage + zip the Windows x64 player package from a MinGW cross build.
#
# Mirrors psxrecomp/tools/package_title_release.py's stage() for the case the
# official packager does not cover (Linux host -> Windows target):
# executable + version stamp, launcher assets, OpenBIOS + notice, player
# game.toml (no machine-specific disc path), game_options.toml, the build's
# own mod catalog (developer-channel features pruned), licenses,
# START_HERE.txt, and the execution contract bound to the staged exe.
# No disc data, BIOS dumps, generated C or sources are staged.
#
# Usage: packaging/stage_windows.sh <build-win-dir> <version>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$(cd "$1" && pwd)"
VERSION="$2"
FW="$ROOT/psxrecomp"
NAME="R4_Recompiled"
STAGE="$ROOT/dist/stage/R4Recompiled-v${VERSION}-windows-x64"
ZIP="$ROOT/dist/R4Recompiled-v${VERSION}-windows-x64.zip"

rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE/bios" "$STAGE/licenses"

cp "$BUILD/$NAME.exe" "$STAGE/"
cp "$BUILD/psx_game_version.txt" "$STAGE/"
cp -r "$BUILD/assets" "$STAGE/assets"
cp "$BUILD/bios/openbios.bin" "$BUILD/bios/OpenBIOS.LICENSE" "$STAGE/bios/"

# Player game.toml: the developer's absolute disc path must not ship; the
# launcher asks for the player's own image on first run.
grep -v '^disc = ' "$ROOT/game.toml" > "$STAGE/game.toml"
cp "$ROOT/game_options.toml" "$STAGE/"

python3 "$FW/tools/release_stage.py" stage-mods --build-path "$BUILD" \
    --stage "$STAGE" --runtime-target psx-runtime
python3 "$FW/tools/mod_channel_filter.py" "$STAGE/mods/bundled"

for f in "$FW"/runtime/licenses/*; do [ -f "$f" ] && cp "$f" "$STAGE/licenses/"; done
cp "$FW/LICENSE" "$STAGE/licenses/psxrecomp-LICENSE"
cp "$FW/THIRD_PARTY_ATTRIBUTION.md" "$STAGE/licenses/psxrecomp-THIRD_PARTY_ATTRIBUTION.md"
cp "$ROOT/recomp-ui/LICENSE" "$STAGE/licenses/recomp-ui-LICENSE"
for sub in fonts img; do
    n="$ROOT/recomp-ui/assets/common/$sub/NOTICE.md"
    [ -f "$n" ] && cp "$n" "$STAGE/assets/$sub/NOTICE.md"
done
sed "s/@VERSION@/${VERSION}/" "$ROOT/packaging/START_HERE.txt" | sed 's/$/\r/' > "$STAGE/START_HERE.txt"

python3 "$FW/tools/release_stage.py" stage-execution --binary "$STAGE/$NAME.exe" \
    --manifest "$BUILD/$NAME.execution.json" --output "$STAGE/$NAME.execution.json"

# Gates: nothing that looks like a disc/BIOS dump other than openbios.bin.
bad=$(cd "$STAGE" && find . -type f \( -iname '*.bin' -o -iname '*.cue' -o -iname '*.chd' \
      -o -iname '*.iso' -o -iname '*.mcd' -o -iname '*.mcr' \) ! -path './bios/openbios.bin')
if [ -n "$bad" ]; then echo "refusing: disc/save data staged: $bad" >&2; exit 1; fi

(cd "$(dirname "$STAGE")" && zip -qr9 "$ZIP" "$(basename "$STAGE")")
sha256sum "$ZIP" | sed "s#  .*/#  #" > "$ZIP.sha256"
echo "$ZIP"
