#!/usr/bin/env bash
# Package GIM18.app into a drag-to-Applications installer DMG (ad-hoc signed, no
# Apple Developer account needed). First launch needs right-click → Open once
# (Gatekeeper quarantine on an unnotarized app, but only once the DMG has left
# this machine — a locally built DMG carries no quarantine flag).
#
# Classic drag layout: the GIM18 app on the left, an Applications shortcut on the
# right, drag one onto the other. (An earlier one-click "installer app" variant
# was dropped — it showed a generic script icon and added no real value over the
# universally-understood drag gesture.)
#
# Needs `create-dmg` (brew install create-dmg) for the background/icon layout;
# falls back to a plain hdiutil DMG (still installs fine, just no artwork) if
# it isn't on PATH.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

APP="GIM18.app"
[[ -d "$APP" ]] || { echo "[dmg] $APP not found — run build_app.sh first" >&2; exit 1; }

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
VOLNAME="GIM18"
OUT="GIM18-${VERSION}.dmg"
VOLICON="$HERE/../../macapp/Resources/GIM18.icns"   # same cool-gray brand icon as the app
BACKGROUND="$HERE/dmg_assets/background.tiff"        # HiDPI (1x+2x) — see dmg_assets note
[[ -f "$BACKGROUND" ]] || BACKGROUND="$HERE/dmg_assets/background.png"

rm -f "$OUT"

if command -v create-dmg >/dev/null 2>&1; then
  echo "[dmg] building $OUT (create-dmg)…"
  create-dmg \
    --volname "$VOLNAME" \
    --volicon "$VOLICON" \
    --background "$BACKGROUND" \
    --window-pos 200 120 \
    --window-size 640 400 \
    --icon-size 112 \
    --text-size 12 \
    --icon "$APP" 180 200 \
    --hide-extension "$APP" \
    --app-drop-link 460 200 \
    --no-internet-enable \
    "$OUT" \
    "$APP" >/dev/null
else
  echo "[dmg] create-dmg not found (brew install create-dmg) — plain DMG, no artwork…"
  STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
  cp -Rc "$APP" "$STAGE/$APP"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO "$OUT" >/dev/null
fi

echo "[dmg] setting the DMG file's own Finder icon…"
ICON_TMP="$(mktemp).icns"
cp "$VOLICON" "$ICON_TMP"
sips -i "$ICON_TMP" >/dev/null           # embeds the image as the icns file's OWN custom-icon resource
RSRC="$(mktemp)"
DeRez -only icns "$ICON_TMP" > "$RSRC"
Rez -append "$RSRC" -o "$OUT"
SetFile -a C "$OUT"
rm -f "$RSRC" "$ICON_TMP"

echo "[dmg] done → $HERE/$OUT"
