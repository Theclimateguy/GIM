from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
RESULTS_ROOT = REPO_ROOT / "results"
# Single data root for everything the ENGINE reads at run time (state CSVs, external
# grounding files, forcing tables, geojson). gim-lib relocates this to PACKAGE_ROOT/"data"
# so a plain `pip install` works with no source checkout — keep all engine data paths
# derived from DATA_ROOT so the relocation stays a one-line patch.
# gim-lib: runtime data ships INSIDE the package (gim/data) so a plain `pip install`
# works with no source checkout (see MANIFEST.in). This is the one-line relocation.
DATA_ROOT = PACKAGE_ROOT / "data"
# Single source of truth for the compiled actor state (2023 base year, validated
# against WDI/UN/GCB). All blocks (gim core, gim-lib, GIM2.app) resolve to this via
# runtime.default_state_csv(); do not hardcode dated forward-projection filenames.
OPERATIONAL_STATE_CSV = DATA_ROOT / "agent_states_operational.csv"
CANONICAL_STATE_CSV = OPERATIONAL_STATE_CSV
# Legacy fallback name kept for back-compat; points at the canonical file.
DEFAULT_STATE_CSV = OPERATIONAL_STATE_CSV
WORLD_GEOJSON = DATA_ROOT / "world_countries.geojson"
LEAFLET_CSS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.css"
LEAFLET_JS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.js"
MAP_SCRIPT = REPO_ROOT / "scripts" / "credit_map_leaflet.py"
