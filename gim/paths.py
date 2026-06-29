from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
# Runtime data ships *inside* the package (gim/data) so a plain `pip install` works
# out of the box with no source checkout. The non-data roots below stay repo-relative
# (results/vendor/scripts are dev-only and are not shipped in the wheel).
DATA_ROOT = PACKAGE_ROOT / "data"
RESULTS_ROOT = REPO_ROOT / "results"
DEFAULT_STATE_CSV = DATA_ROOT / "agent_states.csv"
OPERATIONAL_STATE_CSV = DATA_ROOT / "agent_states_operational.csv"
CALIBRATED_STATE_CSV = DATA_ROOT / "agent_states_operational_2026_calibrated.csv"
WORLD_GEOJSON = DATA_ROOT / "world_countries.geojson"
LEAFLET_CSS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.css"
LEAFLET_JS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.js"
MAP_SCRIPT = REPO_ROOT / "scripts" / "credit_map_leaflet.py"
