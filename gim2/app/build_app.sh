#!/usr/bin/env bash
# Assemble the unsigned GIM18.app bundle from the SwiftPM executable (no Xcode).
# If a frozen engine exists (freeze/dist/gim-engine), embed it for a self-contained
# offline app; otherwise the app runs `python3 -m gim2 engine` from the repo (dev).
# (Bundle is named GIM18.app — the user-facing brand — even though the SwiftPM
# product is still GIM2App internally.)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
APP="GIM18.app"
BRAND="$HERE/../../macapp/Resources"   # reuse v1 brand assets

echo "[build] swift build -c release…"
swift build -c release

echo "[build] assembling $APP…"
rm -rf "$APP" GIM2.app   # GIM2.app: remove the pre-rename bundle name if left over
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp ".build/release/GIM2App" "$APP/Contents/MacOS/GIM18"   # CFBundleExecutable=GIM18
cp "Resources/Info.plist" "$APP/Contents/Info.plist"

# Brand: reuse the v1 icon/glyph/logo; GIM18.icns is the app icon (CFBundleIconFile=GIM18).
[[ -f "$BRAND/GIM18.icns" ]] && cp "$BRAND/GIM18.icns" "$APP/Contents/Resources/GIM18.icns"
for img in glyph.png logo.png AppIcon.png; do
  [[ -f "$BRAND/$img" ]] && cp "$BRAND/$img" "$APP/Contents/Resources/$img"
done

# Web assets for the Leaflet choropleth (vendored leaflet + world geojson + map.html).
[[ -d "Resources/web" ]] && cp -R "Resources/web" "$APP/Contents/Resources/web" && echo "[build] embedded web/ map assets"

# Embed the frozen engine if present (self-contained), else dev fallback.
if [[ -x "Resources/gim-engine" ]]; then
  cp "Resources/gim-engine" "$APP/Contents/Resources/gim-engine"
  echo "[build] embedded frozen engine (self-contained)"
elif [[ -x "freeze/dist/gim-engine" ]]; then
  cp "freeze/dist/gim-engine" "$APP/Contents/Resources/gim-engine"
  echo "[build] embedded frozen engine from freeze/dist (self-contained)"
else
  echo "[build] dev mode — app launches 'python3 -m gim2 engine' from the repo"
fi

codesign --force --deep --sign - "$APP" >/dev/null 2>&1 && echo "[build] ad-hoc signed" || echo "[build] codesign skipped"
echo "[build] done → $HERE/$APP"
