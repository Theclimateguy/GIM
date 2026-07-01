from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
RESULTS_ROOT = REPO_ROOT / "results"
# Single source of truth for the compiled actor state (2023 base year, validated
# against WDI/UN/GCB). All blocks (gim core, gim-lib, GIM2.app) resolve to this via
# runtime.default_state_csv(); do not hardcode dated forward-projection filenames.
OPERATIONAL_STATE_CSV = REPO_ROOT / "data" / "agent_states_operational.csv"
CANONICAL_STATE_CSV = OPERATIONAL_STATE_CSV
# Legacy fallback name kept for back-compat; points at the canonical file.
DEFAULT_STATE_CSV = OPERATIONAL_STATE_CSV
WORLD_GEOJSON = REPO_ROOT / "data" / "world_countries.geojson"
LEAFLET_CSS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.css"
LEAFLET_JS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.js"
MAP_SCRIPT = REPO_ROOT / "scripts" / "credit_map_leaflet.py"
