from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_CORE = REPO_ROOT / "legacy" / "GIM_11_1"
if LEGACY_CORE.exists():
    sys.path.insert(0, str(LEGACY_CORE))

from gim_11_1.cli import main


if __name__ == "__main__":
    main()
