from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAM_PATH = REPO_ROOT / "data" / "parameters_gim16.csv"
LOCK_PATH = REPO_ROOT / "data" / "parameters_gim16.lock.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    digest = sha256(PARAM_PATH)
    payload = {
        "parameter_file": str(PARAM_PATH.relative_to(REPO_ROOT)),
        "sha256": digest,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    LOCK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {LOCK_PATH}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
