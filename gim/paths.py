from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
RESULTS_ROOT = REPO_ROOT / "results"
DEFAULT_STATE_CSV = REPO_ROOT / "data" / "agent_states.csv"
OPERATIONAL_STATE_CSV = REPO_ROOT / "data" / "agent_states_operational.csv"
WORLD_GEOJSON = REPO_ROOT / "data" / "world_countries.geojson"
LEAFLET_CSS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.css"
LEAFLET_JS = REPO_ROOT / "vendor" / "leaflet" / "leaflet.js"
MAP_SCRIPT = REPO_ROOT / "scripts" / "credit_map_leaflet.py"
