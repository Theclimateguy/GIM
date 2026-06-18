from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.historical_backtest import DEFAULT_BASELINE_FIXTURE, run_historical_backtest  # noqa: E402


def main() -> None:
    result = run_historical_backtest()
    baseline_path = Path(DEFAULT_BASELINE_FIXTURE)
    baseline_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(baseline_path)


if __name__ == "__main__":
    main()
