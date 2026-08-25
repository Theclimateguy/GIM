import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
RESULTS_ROOT = REPO_ROOT / "results"


def _resolve_data_root() -> Path:
    """Single data root for everything the ENGINE reads at run time (state CSVs,
    external grounding files, forcing tables, geojson). Resolution order mirrors
    gim19._data: $GIM_DATA override → repo checkout layout (bit-identical for
    repo scripts and tests) → the data copy packaged inside the wheel."""
    env = os.environ.get("GIM_DATA")
    if env:
        return Path(env)
    repo_data = REPO_ROOT / "data"
    if (repo_data / "agent_states_operational.csv").exists():
        return repo_data
    return PACKAGE_ROOT / "data"


DATA_ROOT = _resolve_data_root()
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
