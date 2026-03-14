from __future__ import annotations

import csv
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from GIM_13.geo_calibration import iter_geo_weight_entries


OUTPUT_PATH = REPO_ROOT / "misc" / "calibration" / "geo_weights_v1.csv"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "key", "subkey", "value", "ci95_lo", "ci95_hi", "source"])
        for category, key, subkey, weight in iter_geo_weight_entries():
            writer.writerow(
                [
                    category,
                    key,
                    subkey,
                    weight.value,
                    weight.ci95[0],
                    weight.ci95[1],
                    weight.source,
                ]
            )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
