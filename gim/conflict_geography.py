"""Geography-aware conflict risk: spatial-contagion exposure + its leverage on the conflict AUC.

The border-geography diagnostic (scripts/diagnose_border_geography.py) showed that real interstate
conflict is strongly local (≈92% of dyads between neighbours, ≈46× chance) while GIM's escalation
targets are not (≈12%, ≈2.7×). This module quantifies whether that geographic signal IMPROVES GIM's
*validated* conflict ranking: does augmenting `conflict_proneness` with a spatial lag of neighbour
conflict risk rank the UCDP/PRIO record better than `conflict_proneness` alone? (Spatial contagion of
conflict: Gleditsch 2007, JCR; Buhaug & Gleditsch 2008, ISQ.)

Pure functions — adjacency is passed in as a set of `frozenset({a, b})` pairs, so everything here is
testable without shapely or the geojson. The live measurement lives in
scripts/run_s5_conflict_geography.py.
"""

from __future__ import annotations

import statistics
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple


def spatial_exposure(
    names: Sequence[str],
    value_by_name: Dict[str, float],
    adjacency: Set[FrozenSet[str]],
    default: Optional[float] = None,
) -> Dict[str, float]:
    """Spatial lag: each node's value replaced by the mean of its neighbours' values.

    Isolated nodes (no neighbour in `names`) get `default`, or the global mean when `default is None`
    (a no-information fallback that does not bias the ranking).
    """
    gmean = statistics.fmean(value_by_name[n] for n in names)
    fill = gmean if default is None else default
    out: Dict[str, float] = {}
    for n in names:
        neigh = [m for m in names if m != n and frozenset((n, m)) in adjacency]
        out[n] = statistics.fmean(value_by_name[m] for m in neigh) if neigh else fill
    return out


def auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Area under the ROC curve (Mann-Whitney), ties counted at 0.5."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def _z(v: Sequence[float]) -> List[float]:
    m = statistics.fmean(v)
    sd = statistics.pstdev(v) or 1e-9
    return [(x - m) / sd for x in v]


def blended_auc_scan(
    base: Sequence[float], extra: Sequence[float], labels: Sequence[int], n_grid: int = 20
) -> Tuple[float, float, float]:
    """Best AUC of score = (1-w)·z(base) + w·z(extra) over w in [0,1]. Returns (best_auc, best_w, base_auc).

    NOTE: the grid search over w introduces optimism bias, so the standalone `extra` AUC and the
    base AUC are the honest, untuned numbers; the blended best is an upper bound on the achievable gain.
    """
    zb, ze = _z(base), _z(extra)
    base_auc = auc(list(base), labels)
    best_auc, best_w = base_auc, 0.0
    for i in range(n_grid + 1):
        w = i / n_grid
        s = [(1 - w) * b + w * e for b, e in zip(zb, ze)]
        a = auc(s, labels)
        if a > best_auc:
            best_auc, best_w = a, w
    return best_auc, best_w, base_auc


__all__ = ["spatial_exposure", "auc", "blended_auc_scan"]
