#!/usr/bin/env bash
# Assemble the unsigned GIM17.app bundle from the Swift Package executable.
# No Xcode required (Command Line Tools + SPM). Distribution: unsigned personal build.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
APP="GIM17.app"

echo "[build] swift build -c release…"
swift build -c release

echo "[build] assembling $APP…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp ".build/release/GIM17App" "$APP/Contents/MacOS/GIM17"
cp "Resources/Info.plist" "$APP/Contents/Info.plist"
cp "Resources/GIM17.icns" "$APP/Contents/Resources/GIM17.icns"
for img in glyph.png logo.png AppIcon.png; do
  [[ -f "Resources/$img" ]] && cp "Resources/$img" "$APP/Contents/Resources/$img"
done

# Stage 7 freeze: if a frozen engine exists, embed it so the app is fully offline
# and self-contained. Otherwise the app runs `python3 -m gim engine` from the repo (dev).
if [[ -x "Resources/gim-engine" ]]; then
  cp "Resources/gim-engine" "$APP/Contents/Resources/gim-engine"
  echo "[build] embedded frozen engine (self-contained)"
else
  echo "[build] dev mode — app launches 'python3 -m gim engine' from the repo"
fi

# Ad-hoc sign so local Gatekeeper permits launch on this machine.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 && echo "[build] ad-hoc signed" || echo "[build] codesign skipped"
echo "[build] done → $HERE/$APP"
