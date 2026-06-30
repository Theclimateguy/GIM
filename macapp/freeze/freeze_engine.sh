#!/usr/bin/env bash
# Freeze the GIM17 engine sidecar into a single self-contained binary via PyInstaller.
# Bundles the gim package + shapely/GEOS + runtime data (data/, scenarios/).
# Output: macapp/freeze/dist/gim-engine  → copy into macapp/Resources/gim-engine,
# then build_app.sh embeds it for a fully offline, standalone .app.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$REPO"

echo "[freeze] ensuring pyinstaller…"
python3 -m pip install --quiet --upgrade pyinstaller >/dev/null

rm -rf "$HERE/build" "$HERE/dist" "$HERE/gim-engine.spec" "$HERE/_data_stage"

# Stage a pruned copy of data/ for bundling: ship the validated canon + runtime inputs,
# but NOT data/archive/ (retired forward-2026 artifacts have no place in the shipped app).
echo "[freeze] staging data/ without archive/…"
mkdir -p "$HERE/_data_stage/data"
cp -R "$REPO/data/." "$HERE/_data_stage/data/"
rm -rf "$HERE/_data_stage/data/archive"

echo "[freeze] running PyInstaller (this takes a minute)…"
python3 -m PyInstaller \
  --name gim-engine \
  --onefile \
  --noconfirm \
  --console \
  --distpath "$HERE/dist" \
  --workpath "$HERE/build" \
  --specpath "$HERE" \
  --collect-submodules gim \
  --collect-all shapely \
  --add-data "$HERE/_data_stage/data:data" \
  --add-data "$REPO/scenarios:scenarios" \
  "$HERE/engine_main.py"

rm -rf "$HERE/_data_stage"
echo "[freeze] done → $HERE/dist/gim-engine"
