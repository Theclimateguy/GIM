from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .core import calibration_params as cal
from .core.policy import simple_rule_based_policy
from .core.simulation import step_world
from .runtime import REPO_ROOT, load_world


@dataclass
class CaseResult:
    case_id: str
    directional_validity: bool
    ordering_validity: str
    magnitude_validity: str
    label: str
    notes: str
    metric_deltas: Dict[str, float]
    ablations: List[Dict[str, Any]]


def _resolve_output_path(output_arg: str) -> Path:
    if output_arg:
        return Path(output_arg)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / "results" / "crisis_validation" / f"crisis_validation_{stamp}.json"


def _load_cases(case_dir: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(case_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        payload["_path"] = str(path)
        cases.append(payload)
    return cases


def _get_attr_path(obj: Any, path: str) -> float:
    cursor = obj
    for part in path.split("."):
        if cursor is None:
            return 0.0
        if not hasattr(cursor, part):
            return 0.0
        cursor = getattr(cursor, part)
    try:
        return float(cursor)
    except Exception:
        return 0.0


def _set_attr_path(obj: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = obj
    for part in parts[:-1]:
        cursor = getattr(cursor, part)
    setattr(cursor, parts[-1], value)


def _resolve_actor_id(world: Any, token: str | None) -> str | None:
    if not token:
        return None
    if token in world.agents:
        return str(token)
    lowered = str(token).strip().lower()
    for agent_id, agent in world.agents.items():
        if agent.name.lower() == lowered:
            return str(agent_id)
    return None


def _apply_initial_overrides(world: Any, case: Dict[str, Any]) -> str:
    overrides = case.get("initial_overrides", {})
    target_id = _resolve_actor_id(world, overrides.get("target_id"))
    if not target_id:
        return "target_missing"

    target = world.agents[target_id]

    for key, value in overrides.items():
        if key in {"target_id", "sanctioning_actors", "sanction_type"}:
            continue
        if key.endswith("_multiplier"):
            base_path = key[: -len("_multiplier")]
            base_value = _get_attr_path(target, base_path)
            _set_attr_path(target, base_path, float(base_value) * float(value))
            continue
        _set_attr_path(target, key, value)

    sanctioning_actors = overrides.get("sanctioning_actors", [])
    sanction_type = str(overrides.get("sanction_type", "none"))
    if sanction_type in {"mild", "strong"}:
        for actor_token in sanctioning_actors:
            actor_id = _resolve_actor_id(world, actor_token)
            actor = world.agents.get(actor_id) if actor_id else None
            if actor is None or actor_id == target_id:
                continue
            actor.active_sanctions[target_id] = sanction_type
            actor.sanction_years[target_id] = 2

    return str(target_id)


def _sign_check(delta: float, expected: str) -> bool:
    if expected == "up":
        return delta > 0.0
    if expected == "down":
        return delta < 0.0
    if expected == "down_or_flat":
        return delta <= 0.0
    if expected == "flat_zero":
        return abs(delta) < 1e-9
    if expected == "up_small":
        return 0.0 < delta <= 0.2
    if expected == "flat_or_down_small":
        return -0.1 <= delta <= 0.03
    return True


def _extract_target_metric(world: Any, target_id: str, metric_path: str) -> float:
    target = world.agents[target_id]
    path = metric_path.removeprefix("target.")
    if path == "gdp":
        return float(target.economy.gdp)
    if path == "trade_intensity":
        rels = list(world.relations.get(target_id, {}).values())
        if not rels:
            return 0.0
        return float(sum(rel.trade_intensity for rel in rels) / len(rels))
    if path == "debt_ratio":
        return float(target.economy.public_debt / max(target.economy.gdp, 1e-6))
    if path == "credit_risk_score":
        return float(target.credit_risk_score)
    if "." not in path:
        for prefix in ("economy", "society", "risk", "climate", "technology", "political"):
            candidate = f"{prefix}.{path}"
            try:
                return _get_attr_path(target, candidate)
            except Exception:
                continue
    return _get_attr_path(target, path)


def _event_time(token: str, series: Dict[str, List[float]]) -> int | None:
    def _first(values: List[bool]) -> int | None:
        for idx, flag in enumerate(values):
            if flag:
                return idx
        return None

    gdp = series.get("gdp", [])
    trade = series.get("trade_intensity", [])
    trust = series.get("society.trust_gov", [])
    tension = series.get("society.social_tension", [])
    debt_ratio = series.get("debt_ratio", [])
    debt_active = series.get("risk.debt_crisis_active_years", [])
    credit = series.get("credit_risk_score", [])

    if token == "trade_intensity_drop" and trade:
        return _first([v < trade[0] * 0.98 for v in trade])
    if token == "gdp_drop" and gdp:
        return _first([v < gdp[0] for v in gdp])
    if token == "trust_drop" and trust:
        return _first([v < trust[0] - 0.01 for v in trust])
    if token == "social_tension_rise" and tension:
        return _first([v > tension[0] + 0.02 for v in tension])
    if token == "debt_stress_rise" and debt_ratio:
        return _first([v > cal.DEBT_STRESS_THRESHOLD for v in debt_ratio])
    if token == "debt_crisis_activation" and debt_active:
        return _first([v > 0.0 for v in debt_active])
    if token == "credit_risk_rise" and credit:
        return _first([v > credit[0] + 0.01 for v in credit])
    return None


def _ordering_check(order_tokens: List[str], series: Dict[str, List[float]]) -> Tuple[bool, str]:
    if not order_tokens:
        return True, "not_requested"
    times: List[int] = []
    details: List[str] = []
    for token in order_tokens:
        t = _event_time(token, series)
        details.append(f"{token}:{t}")
        if t is None:
            return False, "missing:" + ",".join(details)
        times.append(t)
    ok = all(times[i] <= times[i + 1] for i in range(len(times) - 1))
    return ok, ",".join(details)


def _parse_magnitude_key(key: str) -> Tuple[str, int | None]:
    token = key.removeprefix("target.")
    marker = "_change_"
    if marker not in token:
        return token, None
    metric, tail = token.split(marker, 1)
    horizon = None
    if tail.endswith("y"):
        try:
            horizon = int(tail[:-1])
        except ValueError:
            horizon = None
    return metric, horizon


def _magnitude_check(
    bounds: Dict[str, List[float]],
    before_metrics: Dict[str, float],
    final_metrics: Dict[str, float],
) -> Tuple[bool, str]:
    if not bounds:
        return True, "not_requested"
    details: List[str] = []
    for key, bound in bounds.items():
        if len(bound) != 2:
            return False, f"invalid_bounds:{key}"
        metric, _ = _parse_magnitude_key(key)
        before = before_metrics.get(metric)
        after = final_metrics.get(metric)
        if before is None or after is None:
            return False, f"missing_metric:{metric}"
        delta = after - before
        lo, hi = float(bound[0]), float(bound[1])
        ok = lo <= delta <= hi
        details.append(f"{metric}:delta={delta:+.4f},range=[{lo:+.4f},{hi:+.4f}],ok={ok}")
        if not ok:
            return False, "; ".join(details)
    return True, "; ".join(details)


def run_case(case: Dict[str, Any], max_agents: int = 21) -> CaseResult:
    world = load_world(max_agents=max_agents)
    target_id = _apply_initial_overrides(world, case)
    if target_id == "target_missing":
        return CaseResult(
            case_id=str(case.get("case_id", "unknown")),
            directional_validity=False,
            ordering_validity="not_run",
            magnitude_validity="not_run",
            label="fail",
            notes="target_missing_in_world",
            metric_deltas={},
            ablations=[],
        )

    expected_signs = case.get("expected_signs", {})
    before: Dict[str, float] = {}
    for metric in expected_signs.keys():
        before[metric] = _extract_target_metric(world, target_id, metric)

    tracked_metrics = {
        "gdp": _extract_target_metric(world, target_id, "target.gdp"),
        "trade_intensity": _extract_target_metric(world, target_id, "target.trade_intensity"),
        "society.trust_gov": _extract_target_metric(world, target_id, "target.society.trust_gov"),
        "society.social_tension": _extract_target_metric(world, target_id, "target.society.social_tension"),
        "debt_ratio": _extract_target_metric(world, target_id, "target.debt_ratio"),
        "risk.debt_crisis_active_years": _extract_target_metric(world, target_id, "target.risk.debt_crisis_active_years"),
        "credit_risk_score": _extract_target_metric(world, target_id, "target.credit_risk_score"),
    }
    series: Dict[str, List[float]] = {k: [v] for k, v in tracked_metrics.items()}

    policies = {agent_id: simple_rule_based_policy for agent_id in world.agents}
    horizon = int(case.get("horizon_years", 3))
    for _ in range(max(1, horizon)):
        step_world(world, policies, phase_trace={})
        for metric in series.keys():
            series[metric].append(_extract_target_metric(world, target_id, "target." + metric))

    checks: List[Tuple[str, bool, float]] = []
    for metric, sign_rule in expected_signs.items():
        after = _extract_target_metric(world, target_id, metric)
        delta = after - before[metric]
        checks.append((metric, _sign_check(delta, str(sign_rule)), float(delta)))

    directional_validity = all(item[1] for item in checks)
    order_ok, order_note = _ordering_check(case.get("expected_order", []), series)

    final_metrics = {
        "gdp": series["gdp"][-1],
        "trade_intensity": series["trade_intensity"][-1],
        "society.trust_gov": series["society.trust_gov"][-1],
        "society.social_tension": series["society.social_tension"][-1],
        "debt_ratio": series["debt_ratio"][-1],
        "risk.debt_crisis_active_years": series["risk.debt_crisis_active_years"][-1],
        "credit_risk_score": series["credit_risk_score"][-1],
    }
    before_for_mag = {
        "gdp": series["gdp"][0],
        "trade_intensity": series["trade_intensity"][0],
        "society.trust_gov": series["society.trust_gov"][0],
        "society.social_tension": series["society.social_tension"][0],
        "debt_ratio": series["debt_ratio"][0],
        "risk.debt_crisis_active_years": series["risk.debt_crisis_active_years"][0],
        "credit_risk_score": series["credit_risk_score"][0],
    }
    mag_ok, mag_note = _magnitude_check(case.get("magnitude_bounds", {}), before_for_mag, final_metrics)

    if directional_validity and order_ok and mag_ok:
        label = "pass"
    elif directional_validity and order_ok:
        label = "weak_pass"
    else:
        label = "fail"

    notes = "; ".join(
        f"{metric}:delta={delta:+.4f},ok={ok}"
        for metric, ok, delta in checks
    )
    notes = f"{notes}; ordering={order_note}; magnitude={mag_note}"

    metric_deltas = {
        "gdp": final_metrics["gdp"] - before_for_mag["gdp"],
        "trade_intensity": final_metrics["trade_intensity"] - before_for_mag["trade_intensity"],
        "trust_gov": final_metrics["society.trust_gov"] - before_for_mag["society.trust_gov"],
        "social_tension": final_metrics["society.social_tension"] - before_for_mag["society.social_tension"],
        "debt_ratio": final_metrics["debt_ratio"] - before_for_mag["debt_ratio"],
        "debt_crisis_active_years": final_metrics["risk.debt_crisis_active_years"]
        - before_for_mag["risk.debt_crisis_active_years"],
        "credit_risk_score": final_metrics["credit_risk_score"] - before_for_mag["credit_risk_score"],
    }

    return CaseResult(
        case_id=str(case.get("case_id", "unknown")),
        directional_validity=directional_validity,
        ordering_validity="pass" if order_ok else "fail",
        magnitude_validity="pass" if mag_ok else "fail",
        label=label,
        notes=notes,
        metric_deltas=metric_deltas,
        ablations=[],
    )


def _run_case_with_overrides(
    case: Dict[str, Any],
    max_agents: int,
    channel_overrides: Dict[str, bool] | None,
) -> CaseResult:
    world = load_world(max_agents=max_agents)
    target_id = _apply_initial_overrides(world, case)
    if target_id == "target_missing":
        return CaseResult(
            case_id=str(case.get("case_id", "unknown")),
            directional_validity=False,
            ordering_validity="not_run",
            magnitude_validity="not_run",
            label="fail",
            notes="target_missing_in_world",
            metric_deltas={},
            ablations=[],
        )

    expected_signs = case.get("expected_signs", {})
    before: Dict[str, float] = {}
    for metric in expected_signs.keys():
        before[metric] = _extract_target_metric(world, target_id, metric)

    tracked_metrics = {
        "gdp": _extract_target_metric(world, target_id, "target.gdp"),
        "trade_intensity": _extract_target_metric(world, target_id, "target.trade_intensity"),
        "society.trust_gov": _extract_target_metric(world, target_id, "target.society.trust_gov"),
        "society.social_tension": _extract_target_metric(world, target_id, "target.society.social_tension"),
        "debt_ratio": _extract_target_metric(world, target_id, "target.debt_ratio"),
        "risk.debt_crisis_active_years": _extract_target_metric(world, target_id, "target.risk.debt_crisis_active_years"),
        "credit_risk_score": _extract_target_metric(world, target_id, "target.credit_risk_score"),
    }
    series: Dict[str, List[float]] = {k: [v] for k, v in tracked_metrics.items()}

    policies = {agent_id: simple_rule_based_policy for agent_id in world.agents}
    horizon = int(case.get("horizon_years", 3))
    for _ in range(max(1, horizon)):
        step_world(world, policies, phase_trace={}, channel_overrides=channel_overrides)
        for metric in series.keys():
            series[metric].append(_extract_target_metric(world, target_id, "target." + metric))

    checks: List[Tuple[str, bool, float]] = []
    for metric, sign_rule in expected_signs.items():
        after = _extract_target_metric(world, target_id, metric)
        delta = after - before[metric]
        checks.append((metric, _sign_check(delta, str(sign_rule)), float(delta)))

    directional_validity = all(item[1] for item in checks)
    order_ok, order_note = _ordering_check(case.get("expected_order", []), series)

    final_metrics = {
        "gdp": series["gdp"][-1],
        "trade_intensity": series["trade_intensity"][-1],
        "society.trust_gov": series["society.trust_gov"][-1],
        "society.social_tension": series["society.social_tension"][-1],
        "debt_ratio": series["debt_ratio"][-1],
        "risk.debt_crisis_active_years": series["risk.debt_crisis_active_years"][-1],
        "credit_risk_score": series["credit_risk_score"][-1],
    }
    before_for_mag = {
        "gdp": series["gdp"][0],
        "trade_intensity": series["trade_intensity"][0],
        "society.trust_gov": series["society.trust_gov"][0],
        "society.social_tension": series["society.social_tension"][0],
        "debt_ratio": series["debt_ratio"][0],
        "risk.debt_crisis_active_years": series["risk.debt_crisis_active_years"][0],
        "credit_risk_score": series["credit_risk_score"][0],
    }
    mag_ok, mag_note = _magnitude_check(case.get("magnitude_bounds", {}), before_for_mag, final_metrics)

    if directional_validity and order_ok and mag_ok:
        label = "pass"
    elif directional_validity and order_ok:
        label = "weak_pass"
    else:
        label = "fail"

    notes = "; ".join(
        f"{metric}:delta={delta:+.4f},ok={ok}"
        for metric, ok, delta in checks
    )
    notes = f"{notes}; ordering={order_note}; magnitude={mag_note}"

    metric_deltas = {
        "gdp": final_metrics["gdp"] - before_for_mag["gdp"],
        "trade_intensity": final_metrics["trade_intensity"] - before_for_mag["trade_intensity"],
        "trust_gov": final_metrics["society.trust_gov"] - before_for_mag["society.trust_gov"],
        "social_tension": final_metrics["society.social_tension"] - before_for_mag["society.social_tension"],
        "debt_ratio": final_metrics["debt_ratio"] - before_for_mag["debt_ratio"],
        "debt_crisis_active_years": final_metrics["risk.debt_crisis_active_years"]
        - before_for_mag["risk.debt_crisis_active_years"],
        "credit_risk_score": final_metrics["credit_risk_score"] - before_for_mag["credit_risk_score"],
    }

    return CaseResult(
        case_id=str(case.get("case_id", "unknown")),
        directional_validity=directional_validity,
        ordering_validity="pass" if order_ok else "fail",
        magnitude_validity="pass" if mag_ok else "fail",
        label=label,
        notes=notes,
        metric_deltas=metric_deltas,
        ablations=[],
    )


def run_all(case_dir: Path, max_agents: int = 21) -> List[CaseResult]:
    cases = _load_cases(case_dir)
    results: List[CaseResult] = []
    for case in cases:
        baseline = _run_case_with_overrides(case, max_agents=max_agents, channel_overrides=None)
        ablations: List[Dict[str, Any]] = []
        for target in case.get("ablation_targets", []):
            ablated = _run_case_with_overrides(
                case,
                max_agents=max_agents,
                channel_overrides={str(target): False},
            )
            delta_vs_baseline = {
                metric: float(ablated.metric_deltas.get(metric, 0.0) - baseline.metric_deltas.get(metric, 0.0))
                for metric in baseline.metric_deltas.keys()
            }
            ablations.append(
                {
                    "channel": str(target),
                    "label": ablated.label,
                    "directional_validity": ablated.directional_validity,
                    "ordering_validity": ablated.ordering_validity,
                    "magnitude_validity": ablated.magnitude_validity,
                    "delta_vs_baseline": delta_vs_baseline,
                }
            )
        baseline.ablations = ablations
        results.append(baseline)
    return results


def _as_dict_rows(results: Iterable[CaseResult]) -> List[Dict[str, Any]]:
    rows = []
    for result in results:
        rows.append(
            {
                "case_id": result.case_id,
                "directional_validity": result.directional_validity,
                "ordering_validity": result.ordering_validity,
                "magnitude_validity": result.magnitude_validity,
                "label": result.label,
                "notes": result.notes,
                "metric_deltas": result.metric_deltas,
                "ablations": result.ablations,
            }
        )
    return rows


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run crisis validation cases.")
    parser.add_argument(
        "--case-dir",
        default=str(REPO_ROOT / "tests" / "crisis_cases"),
        help="Path to crisis case JSON files",
    )
    parser.add_argument("--max-agents", type=int, default=21)
    parser.add_argument("--output", default="", help="Optional output JSON path")
    args = parser.parse_args(argv)

    case_dir = Path(args.case_dir)
    results = run_all(case_dir, max_agents=args.max_agents)
    rows = _as_dict_rows(results)

    out = _resolve_output_path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved: {out}")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
