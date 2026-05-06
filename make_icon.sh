#!/bin/bash
# Bouw een macOS-app-icoon (.icns) uit app/icons/app_icon.svg.
#
# Vereist: macOS met sips en iconutil (standaard aanwezig).
# Gebruik:
#   ./make_icon.sh
# Resultaat: app/icons/app_icon.icns

set -e
cd "$(dirname "$0")"

SRC="app/icons/app_icon.svg"
ICONSET="AppIcon.iconset"
OUT="app/icons/app_icon.icns"

if [ ! -f "$SRC" ]; then
    echo "Bron-SVG ontbreekt: $SRC" >&2
    exit 1
fi
if ! command -v sips >/dev/null || ! command -v iconutil >/dev/null; then
    echo "sips of iconutil ontbreekt — alleen op macOS beschikbaar." >&2
    exit 1
fi

mkdir -p "$ICONSET"
for SIZE in 16 32 64 128 256 512 1024; do
    sips -s format png "$SRC" --resampleHeightWidth "$SIZE" "$SIZE" \
         --out "$ICONSET/icon_${SIZE}x${SIZE}.png" >/dev/null
done
# @2x retina-varianten
cp "$ICONSET/icon_32x32.png"   "$ICONSET/icon_16x16@2x.png"
cp "$ICONSET/icon_64x64.png"   "$ICONSET/icon_32x32@2x.png"
cp "$ICONSET/icon_256x256.png" "$ICONSET/icon_128x128@2x.png"
cp "$ICONSET/icon_512x512.png" "$ICONSET/icon_256x256@2x.png"
cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"

iconutil -c icns "$ICONSET" -o "$OUT"
rm -rf "$ICONSET"

echo "→ $OUT klaar."
