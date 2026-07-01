#!/usr/bin/env python3
"""Statistical inference for the conflict-backtest AUC (significance + robustness).

Closes the rigor gap behind the headline claim "AUC = 0.736": reports a bootstrap
confidence interval and a label-permutation significance test, as a reproducible
artifact. Reuses the exact scoring set (probs/labels over the 57 GIM countries) built
by ``conflict_backtest.py`` — GIM's ``conflict_proneness`` input vs. UCDP/PRIO realized
involvement, 1990-2023.

  * Bootstrap CI: case (pair) resampling of (score, label) with replacement; resamples
    that lose a class are discarded; the 2.5/97.5 percentiles of the AUC distribution.
  * Permutation test: labels shuffled against fixed scores; one-sided
    p = (1 + #{AUC_perm >= AUC_obs}) / (1 + n_perm)  (the conservative add-one estimator).
    The default budget is large (50000) because the exceedance count is small: at only
    2000 permutations the estimate is unstable (a single seed can hit 0 exceedances and
    report the 1/2001 ~ 5e-4 floor); at 50000 it converges to p ~ 1.3e-3 (seed-robust).

    BOOT_N (default 20000), PERM_N (default 50000), AUC_SEED (default 2026).

    python3 scripts/conflict_auc_inference.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from scripts.conflict_backtest import (  # reuse the exact scoring pipeline
    auc,
    load_gim_conflict_proneness,
    load_ucdp_labels,
)


def _auc_np(scores: np.ndarray, labels: np.ndarray) -> float:
    """Vectorized Mann-Whitney AUC (ties counted as 0.5); NaN if a class is empty."""
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    # rank-based: wins = #{pos > neg} + 0.5 #{pos == neg}
    diff = pos[:, None] - neg[None, :]
    wins = np.sum(diff > 0) + 0.5 * np.sum(diff == 0)
    return float(wins / (pos.size * neg.size))


def main() -> int:
    boot_n = int(os.getenv("BOOT_N", "20000"))
    perm_n = int(os.getenv("PERM_N", "50000"))
    seed = int(os.getenv("AUC_SEED", "2026"))
    window = (1990, 2023)

    gim = load_gim_conflict_proneness()
    labels_map = load_ucdp_labels(window)
    if labels_map is None:
        print("UCDP file not found; cannot run inference.")
        return 1

    names = [n for n in gim if n in labels_map] + [n for n in gim if n not in labels_map]
    scores = np.array([gim[n] for n in names], dtype=float)
    labels = np.array([labels_map.get(n, 0) for n in names], dtype=int)
    n = len(names)
    n_pos = int(labels.sum())

    auc_obs = auc(list(scores), list(labels))  # identical to the backtest's value

    rng = np.random.default_rng(seed)

    # --- Bootstrap CI (case resampling) ---
    boot_aucs = []
    discarded = 0
    for _ in range(boot_n):
        idx = rng.integers(0, n, size=n)
        a = _auc_np(scores[idx], labels[idx])
        if np.isnan(a):
            discarded += 1
            continue
        boot_aucs.append(a)
    boot_aucs = np.array(boot_aucs)
    ci_lo, ci_hi = (float(np.percentile(boot_aucs, 2.5)),
                    float(np.percentile(boot_aucs, 97.5)))
    boot_mean = float(boot_aucs.mean())
    boot_se = float(boot_aucs.std(ddof=1))

    # --- Permutation test (shuffle labels) ---
    ge = 0
    for _ in range(perm_n):
        perm = rng.permutation(labels)
        a = _auc_np(scores, perm)
        if not np.isnan(a) and a >= auc_obs:
            ge += 1
    p_perm = (1 + ge) / (1 + perm_n)

    result = {
        "experiment": "Conflict-AUC inference: bootstrap CI + label-permutation test",
        "source": "GIM conflict_proneness vs UCDP/PRIO ACD involvement, 1990-2023",
        "n_countries": n,
        "n_positive": n_pos,
        "n_negative": n - n_pos,
        "auc_observed": round(auc_obs, 4),
        "bootstrap": {
            "n_resamples": boot_n,
            "n_used": int(boot_aucs.size),
            "n_discarded_empty_class": discarded,
            "ci95": [round(ci_lo, 3), round(ci_hi, 3)],
            "mean": round(boot_mean, 4),
            "se": round(boot_se, 4),
            "method": "case (pair) resampling with replacement; 2.5/97.5 percentiles",
        },
        "permutation": {
            "n_permutations": perm_n,
            "n_ge_observed": ge,
            "p_value": round(p_perm, 5),
            "method": "labels shuffled; one-sided p=(1+#{AUC_perm>=AUC_obs})/(1+n_perm)",
        },
        "seed": seed,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    out = os.path.join(REPO, "results", "calibration", "conflict_auc_inference.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")

    print(f"AUC = {auc_obs:.4f}  (n={n}, pos={n_pos}, neg={n - n_pos})")
    print(f"Bootstrap 95% CI = [{ci_lo:.3f}, {ci_hi:.3f}]  "
          f"(mean={boot_mean:.4f}, SE={boot_se:.4f}, {boot_aucs.size}/{boot_n} used)")
    print(f"Permutation p = {p_perm:.5f}  ({ge}/{perm_n} permutations >= observed)")
    print(f"ledger -> {os.path.relpath(out, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
