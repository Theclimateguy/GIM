#!/usr/bin/env bash
# Freeze the gim2 deterministic engine into one self-contained binary (PyInstaller).
# Bundles gim + gim2 + shapely/GEOS + runtime data (data/, scenarios/).
# Output: gim2/app/freeze/dist/gim-engine → copy to gim2/app/Resources/gim-engine,
# then build_app.sh embeds it for a fully offline, standalone .app.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
cd "$REPO"

echo "[freeze] ensuring pyinstaller…"
python3 -m pip install --quiet --upgrade pyinstaller >/dev/null

rm -rf "$HERE/build" "$HERE/dist" "$HERE/gim-engine.spec"
echo "[freeze] running PyInstaller (takes a minute)…"
python3 -m PyInstaller \
  --name gim-engine \
  --onefile \
  --noconfirm \
  --console \
  --distpath "$HERE/dist" \
  --workpath "$HERE/build" \
  --specpath "$HERE" \
  --collect-submodules gim \
  --collect-submodules gim2 \
  --collect-all shapely \
  --add-data "$REPO/data:data" \
  --add-data "$REPO/scenarios:scenarios" \
  --add-data "$REPO/tests/fixtures:tests/fixtures" \
  "$HERE/engine_main.py"

echo "[freeze] done → $HERE/dist/gim-engine"
