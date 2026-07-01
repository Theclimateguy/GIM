"""«Карта ответа» — решение-ориентированная сборка детерминированных выходов.

`compute_answer` склеивает уже валидированные куски в один ответ на стратегический
вопрос: вердикт, дельта-вееры (сценарий−база), порог срыва (через дозовый свип),
каскад между доменами и относительную аналитическую записку. **Без новой
математики** — это оркестрация `compute_scenario` + `compute_dose`.
"""

from __future__ import annotations

import shlex
from typing import Any, Dict, List, Optional, Sequence

from . import SCHEMA
from . import archetypes as A
from . import levers as L
from .actors import build_actor_states
from .cascade import build_cascade, run_actor_pair
from .dose_response import compute_dose
from .scenario import Progress, _METRIC_LABEL, compute_scenario

# Метрики, для которых рост = хуже (для вердикта/знака).
_BAD_WHEN_UP = {"mean_social_tension", "n_debt_crises", "conflict_risk", "n_regime_crises", "temperature", "co2"}

# Порог «срыва» по метрике: ("abs", значение) или ("frac", доля |базы|).
_METRIC_THRESHOLD: Dict[str, tuple] = {
    "n_debt_crises": ("abs", 1.0),
    "conflict_risk": ("abs", 0.03),
    "n_regime_crises": ("abs", 1.0),
    "mean_social_tension": ("abs", 0.05),
    "temperature": ("abs", 0.05),
    "world_gdp": ("frac", 0.02),
    "co2": ("frac", 0.02),
}

_CARD_ORDER = ("world_gdp", "n_debt_crises", "mean_social_tension", "co2", "temperature", "conflict_risk")


def _label(metric: str) -> str:
    return _METRIC_LABEL.get(metric, (metric, ""))[0]


def _terminal(seq: Sequence[float]) -> float:
    return float(seq[-1]) if seq else 0.0


def _verdict(metric: str, delta_terminal: float, base_terminal: float) -> str:
    rel = (delta_terminal / abs(base_terminal)) if (metric not in {"n_debt_crises", "n_regime_crises"} and base_terminal) else delta_terminal
    worse = (delta_terminal > 0 and metric in _BAD_WHEN_UP) or (delta_terminal < 0 and metric not in _BAD_WHEN_UP)
    mag = abs(rel)
    name = _label(metric)
    if mag < 1e-6:
        return f"Близко к базовой траектории: {name} почти не сдвигается."
    if not worse:
        return f"Улучшение относительно базы: {name} сдвигается в благоприятную сторону."
    if mag >= 0.10 or (metric in {"n_debt_crises", "n_regime_crises"} and abs(delta_terminal) >= 2):
        return f"Скорее срыв, чем стабилизация: {name} заметно ухудшается относительно базы."
    return f"Умеренный негативный сдвиг: {name} ухудшается, но в пределах управляемого."


def _threshold_crossing(dose_proj: Dict[str, Any], lever: str, metric: str) -> Dict[str, Any]:
    x = [float(v) for v in dose_proj.get("x", [])]
    delta = [float(v) for v in dose_proj.get("delta", [])]
    base = float(dose_proj.get("baseline", 0.0))
    kind, value = _METRIC_THRESHOLD.get(metric, ("frac", 0.05))
    thr = value if kind == "abs" else value * abs(base)

    crossing: Optional[float] = None
    for i in range(1, len(x)):
        if abs(delta[i]) >= thr > abs(delta[i - 1]):
            lo, hi = abs(delta[i - 1]), abs(delta[i])
            frac = (thr - lo) / (hi - lo) if hi > lo else 0.0
            crossing = round(x[i - 1] + frac * (x[i] - x[i - 1]), 3)
            break
        if i == 1 and abs(delta[0]) >= thr:  # already past at zero (rare)
            crossing = x[0]
            break

    if crossing is None:
        note = f"порог не достигается в диапазоне интенсивности [0, {x[-1] if x else 1.25}]"
    elif kind == "abs" and metric in {"n_debt_crises", "n_regime_crises"}:
        note = f"при «{lever}» ≈ {crossing} сценарий даёт ≥{int(thr)} доп. событий ({_label(metric)})"
    else:
        note = f"при «{lever}» ≈ {crossing} Δ {_label(metric)} пересекает порог {round(thr, 3)}"
    return {"lever": lever, "metric": metric, "threshold_value": round(thr, 4),
            "crossing_magnitude": crossing, "note": note}


def _cards(delta_metrics: Dict[str, Any], headline: str) -> List[Dict[str, Any]]:
    order = [headline] + [m for m in _CARD_ORDER if m != headline]
    cards: List[Dict[str, Any]] = []
    for metric in order:
        block = delta_metrics.get(metric)
        if not block:
            continue
        fan = block.get("delta", {})
        cards.append({
            "metric": metric,
            "label": _label(metric),
            "delta_p50": round(_terminal(fan.get("p50", [])), 4),
            "p5": round(_terminal(fan.get("p5", [])), 4),
            "p95": round(_terminal(fan.get("p95", [])), 4),
            "lead": metric == headline,
        })
        if len(cards) >= 4:
            break
    return cards


def compute_answer(
    *, state_csv=None, archetype: Optional[str] = None, levers: Sequence[Any] = (), magnitude=None,
    actors=None, members=160, years=10, max_agents=100, seed=2026, jobs=0,
    threshold_lever: Optional[str] = None, threshold_metric: Optional[str] = None,
    threshold_members=100, cascade_members=24, progress: Progress = None, cancel=None,
) -> Dict[str, Any]:
    arch: Optional[A.Archetype] = None
    if archetype:
        arch = A.get(archetype)
        items: Sequence[Any] = arch.selection_items()
        actors = actors or list(arch.actors)
        headline = arch.headline_metric
        threshold_lever = threshold_lever or arch.dominant_lever()
        threshold_metric = threshold_metric or arch.threshold_metric or headline
    else:
        items = list(levers)
        headline = "world_gdp"

    selection = L.make_selection(items, default_magnitude=magnitude, actors=actors)
    if not selection.magnitudes:
        raise ValueError("answer requires at least one lever or an archetype")
    if threshold_lever is None:
        threshold_lever = max(selection.magnitudes, key=lambda k: selection.magnitudes[k])
    threshold_metric = threshold_metric or headline

    scenario = compute_scenario(
        state_csv=state_csv, levers=items, magnitude=magnitude, actors=actors, members=members,
        years=years, max_agents=max_agents, seed=seed, jobs=jobs, progress=progress, cancel=cancel,
    )
    delta_metrics = {m["metric"]: m for m in scenario["projection"]["metrics"]}

    threshold: Optional[Dict[str, Any]] = None
    if threshold_lever in L.GROUNDED_LEVERS:
        dose = compute_dose(
            state_csv=state_csv, lever=threshold_lever, metric=threshold_metric, actors=actors,
            members=threshold_members, years=years, max_agents=max_agents, seed=seed, cancel=cancel,
        )
        threshold = _threshold_crossing(dose["projection"], threshold_lever, threshold_metric)
        threshold["curve"] = dose["projection"]

    # One per-agent base+scenario pair feeds BOTH the cascade and the actor states.
    actor_run = run_actor_pair(state_csv=state_csv, selection=selection, years=years,
                               max_agents=max_agents, seed=seed, members=cascade_members)

    head_block = delta_metrics.get(headline, {})
    head_delta = _terminal(head_block.get("delta", {}).get("p50", []))
    head_base = _terminal(head_block.get("baseline_p50", []))

    return {
        "schema": SCHEMA,
        "mode": "answer",
        "archetype": arch.to_dict() if arch else None,
        "selection": selection.to_dict(),
        "config": scenario["config"],
        "verdict": _verdict(headline, head_delta, head_base),
        "headline_metric": headline,
        "cards": _cards(delta_metrics, headline),
        "projection": scenario["projection"],
        "threshold": threshold,
        "cascade": build_cascade(actor_run),
        "actors": build_actor_states(actor_run),
        "brief": scenario["brief"],
    }


def run_answer_cli(args) -> Dict[str, Any]:
    out = compute_answer(
        state_csv=args.state_csv, archetype=args.archetype, levers=args.lever, magnitude=args.magnitude,
        actors=args.actors, members=args.members, years=args.years, max_agents=args.max_agents,
        seed=args.seed, threshold_lever=args.threshold_lever, threshold_metric=args.threshold_metric,
    )
    cli = ["python3", "-m", "gim2", "answer"]
    if args.archetype:
        cli += ["--archetype", args.archetype]
    for lid in args.lever:
        cli += ["--lever", lid]
    if args.magnitude is not None:
        cli += ["--magnitude", str(args.magnitude)]
    if args.actors:
        cli += ["--actors", *args.actors]
    cli += ["--members", str(args.members), "--years", str(args.years),
            "--max-agents", str(args.max_agents), "--seed", str(args.seed)]
    out["equiv_cli"] = " ".join(shlex.quote(str(p)) for p in cli)
    return out


__all__ = ["compute_answer", "run_answer_cli"]
