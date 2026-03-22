#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="${1:-$(date +%F)}"
RUN_LLM="${RUN_LLM:-0}"

OUT_DIR="results/validation/non_llm/${STAMP}"
mkdir -p "$OUT_DIR"

echo "[validation] writing non-LLM package to: ${OUT_DIR}"

python3 -m unittest \
  tests.test_core_modules \
  tests.test_crisis_persistence \
  tests.test_gim_13_mvp \
  tests.test_geo_calibration \
  tests.test_calibration \
  tests.test_sensitivity_sweep -v | tee "${OUT_DIR}/unittest.log"

python3 -m gim calibrate \
  --suite operational_v2 \
  --background-policy simple \
  --runs 3 \
  --horizon 2 \
  --json > "${OUT_DIR}/calibrate_simple.json"

python3 -m gim calibrate \
  --suite operational_v2 \
  --background-policy growth \
  --runs 3 \
  --horizon 2 \
  --json > "${OUT_DIR}/calibrate_growth.json"

STAMP="$STAMP" python3 - <<'PY'
import json
import os
from pathlib import Path

stamp = os.environ["STAMP"]
out_dir = Path("results/validation/non_llm") / Path(stamp)
rows = []
for mode in ("simple", "growth"):
    payload = json.loads((out_dir / f"calibrate_{mode}.json").read_text())
    rows.append(
        {
            "mode": mode,
            "pass_count": payload["pass_count"],
            "case_count": payload["case_count"],
            "average_score": payload["average_score"],
            "average_calibration_score": payload["average_calibration_score"],
            "average_physical_consistency_score": payload["average_physical_consistency_score"],
            "average_criticality_score": payload["average_criticality_score"],
            "results": payload["results"],
        }
    )

lines = [
    f"# GIM16 Validation Package ({stamp})",
    "",
    "Suite: `operational_v2`, runs=3, horizon=2",
    "",
    "| Mode | Passed | Avg total | Avg calibration | Avg physical | Avg criticality |",
    "|---|---:|---:|---:|---:|---:|",
]
for row in rows:
    lines.append(
        f"| {row['mode']} | {row['pass_count']}/{row['case_count']} | "
        f"{row['average_score']:.3f} | {row['average_calibration_score']:.3f} | "
        f"{row['average_physical_consistency_score']:.3f} | {row['average_criticality_score']:.3f} |"
    )

lines.append("")
lines.append("## Case outcomes (dominant outcome trio)")
lines.append("")
for row in rows:
    lines.append(f"### {row['mode']}")
    for case in row["results"]:
        trio = ", ".join(case["snapshot"]["dominant_outcomes"][:3])
        lines.append(f"- `{case['case_id']}`: {trio}")
    lines.append("")

(out_dir / "summary.md").write_text("\n".join(lines) + "\n")
print(f"[validation] wrote {(out_dir / 'summary.md')}")
PY

if [[ "$RUN_LLM" == "1" ]]; then
  if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "[validation] RUN_LLM=1 but DEEPSEEK_API_KEY is not set. Skipping LLM package."
  else
    LLM_OUT_DIR="results/validation/llm/${STAMP}"
    mkdir -p "$LLM_OUT_DIR"
    echo "[validation] writing LLM package to: ${LLM_OUT_DIR}"

    python3 -m gim calibrate \
      --suite operational_v2 \
      --background-policy compiled-llm \
      --runs 2 \
      --horizon 2 \
      --json > "${LLM_OUT_DIR}/calibrate_compiled_llm.json"
  fi
fi

echo "[validation] completed"
