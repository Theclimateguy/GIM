#!/usr/bin/env bash
# Freeze the gim2 deterministic engine into one self-contained binary (PyInstaller).
# Bundles gim + gim2 + shapely/GEOS + runtime data (data/, scenarios/, tests/fixtures/).
# Output: gim2/app/freeze/dist/gim-engine; build_app.sh embeds it for a standalone .app.
#
# EXPLICIT-SOURCE BUILD (2026-06): this repo can be shadowed by a `pip install -e` editable
# install of `gim` pointing at a *different* checkout, and PyInstaller keeps a global bytecode
# cache that survives `rm -rf build/dist`. Either can silently freeze a STALE engine. So we:
#   1. pin a FRESH, build-local PyInstaller config/cache dir (no stale bytecode reuse),
#   2. put THIS repo first on PYTHONPATH and pass it as --paths,
#   3. hard-assert, before building, that the gim we are about to freeze is the expected
#      version with the current engine surface — failing loudly rather than shipping stale code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
cd "$REPO"

EXPECTED_VERSION="$(grep -m1 '__version__' "$REPO/gim/__init__.py" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"

# (1) fresh, isolated PyInstaller cache/config so no prior build's bytecode is reused.
export PYINSTALLER_CONFIG_DIR="$HERE/.pyinstaller-cache"
# (2) make THIS repo the authoritative source for gim/gim2.
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
rm -rf "$PYINSTALLER_CONFIG_DIR" "$HERE/build" "$HERE/dist" "$HERE/gim-engine.spec" "$HERE/_data_stage"

echo "[freeze] ensuring pyinstaller…"
python3 -m pip install --quiet --upgrade pyinstaller >/dev/null

# (3) hard gate: refuse to build a stale engine. Resolve gim the same way PyInstaller will and
# verify version + a current-engine marker (development-dependent decarbonisation, added 17.3.0).
echo "[freeze] verifying engine source…"
PYTHONPATH="$REPO" python3 - "$EXPECTED_VERSION" <<'PY'
import sys, os, gim
from gim.core import calibration_params as cal, core as core_consts
expected = sys.argv[1]
src = os.path.realpath(gim.__file__)
ok_version = gim.__version__ == expected
ok_surface = hasattr(cal, "DECARB_DEVELOPMENT_DEPENDENT") and hasattr(core_consts, "CARBON_POOL_INIT_FRACTIONS_2023")
print(f"[freeze]   gim source : {src}")
print(f"[freeze]   gim version: {gim.__version__} (expected {expected})")
print(f"[freeze]   new surface: {ok_surface}")
if not (ok_version and ok_surface):
    sys.exit("[freeze] ABORT: resolved gim is stale or wrong (version/surface mismatch). "
             "Check for a `pip install -e` editable install shadowing this repo "
             "(pip uninstall it, or update its checkout), then re-run.")
PY

# Ship the validated canon + runtime inputs, but NOT data/archive/ (retired forward-2026 artifacts).
echo "[freeze] staging data/ without archive/…"
mkdir -p "$HERE/_data_stage/data"
cp -R "$REPO/data/." "$HERE/_data_stage/data/"
rm -rf "$HERE/_data_stage/data/archive"

echo "[freeze] running PyInstaller (takes a minute)…"
python3 -m PyInstaller \
  --clean \
  --noconfirm \
  --name gim-engine \
  --onefile \
  --console \
  --distpath "$HERE/dist" \
  --workpath "$HERE/build" \
  --specpath "$HERE" \
  --paths "$REPO" \
  --collect-submodules gim \
  --collect-submodules gim2 \
  --collect-all shapely \
  --add-data "$HERE/_data_stage/data:data" \
  --add-data "$REPO/scenarios:scenarios" \
  --add-data "$REPO/tests/fixtures:tests/fixtures" \
  "$HERE/engine_main.py"

rm -rf "$HERE/_data_stage" "$PYINSTALLER_CONFIG_DIR"

# CRITICAL: publish the freshly frozen binary to Resources/, which is what build_app.sh embeds.
# Without this copy build_app.sh silently re-embeds a STALE Resources/gim-engine from an old build
# (this was the long-standing "app shows the old baseline" bug — the freeze was fine, the copy missing).
cp "$HERE/dist/gim-engine" "$HERE/../Resources/gim-engine"
chmod +x "$HERE/../Resources/gim-engine"
echo "[freeze] done → $HERE/dist/gim-engine → Resources/gim-engine  (gim $EXPECTED_VERSION)"
