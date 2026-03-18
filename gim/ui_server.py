from __future__ import annotations

import csv
import html
import json
import mimetypes
import os
import shlex
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
UI_HTML = ROOT / "ui_prototype" / "gim15_dashboard_prototype.html"
RESULTS_DIR = ROOT / "results"
DATA_DIR = ROOT / "data"
DEFAULT_ACTOR_STATE_CSV = DATA_DIR / "agent_states_operational_2026_calibrated.csv"

DOC_PATHS = [
    "README.md",
    "docs/README.md",
    "docs/MODEL_METHODOLOGY.md",
    "docs/GIM15_UNIFIED_MODEL_SPEC.md",
    "docs/CALIBRATION_REFERENCE.md",
    "docs/CALIBRATION_LAYER.md",
    "docs/SIMULATION_STEP_ORDER.md",
    "COMMAND_REFERENCE.md",
    "docs/CRISIS_VALIDATION_PROTOCOL.md",
    "docs/PARAMETER_CHANGE_POLICY.md",
]

NEGATIVE_OUTCOME_HINTS = (
    "destabilization",
    "direct_strike",
    "proxy_escalation",
    "regional_escalation",
    "crisis",
    "unrest",
    "chokepoint",
)

POSITIVE_OUTCOME_HINTS = (
    "status_quo",
    "deescalation",
    "suppression",
    "stable",
)


@dataclass
class RunState:
    run_id: str
    status: str = "queued"
    progress: float = 0.0
    step_index: int = 0
    step_total: int = 8
    note: str = "queued"
    started_at: float | None = None
    ended_at: float | None = None
    command: str = ""
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    return_code: int | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    manifest_path: str | None = None


RUNS: dict[str, RunState] = {}
RUNS_LOCK = threading.Lock()


def _safe_join(base: Path, rel: str) -> Path:
    candidate = (base / rel).resolve()
    if base.resolve() not in candidate.parents and candidate != base.resolve():
        raise ValueError("path escapes base")
    return candidate


def _list_docs() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for rel in DOC_PATHS:
        path = _safe_join(ROOT, rel)
        if path.exists():
            entries.append({"path": rel, "name": Path(rel).name})
    return entries


def _list_state_csvs() -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in DATA_DIR.glob("*.csv"))


def _default_actor_state_csv() -> Path | None:
    if DEFAULT_ACTOR_STATE_CSV.exists():
        return DEFAULT_ACTOR_STATE_CSV.resolve()
    csvs = sorted(DATA_DIR.glob("*.csv"))
    return csvs[0].resolve() if csvs else None


def _resolve_state_csv_selection(raw: str | None) -> Path | None:
    if raw:
        resolved = _resolve_repo_path(raw)
        if resolved is None or not resolved.exists() or resolved.suffix.lower() != ".csv":
            raise ValueError("invalid state csv")
        return resolved
    return _default_actor_state_csv()


def _list_actor_options(state_csv: str | None = None) -> dict[str, Any]:
    path = _resolve_state_csv_selection(state_csv)
    if path is None:
        return {"state_csv": None, "actors": []}

    actors: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            actor_id = str(row.get("id", "")).strip()
            actor_name = str(row.get("name", "")).strip() or actor_id
            key = actor_id or actor_name
            if not key or key in seen:
                continue
            seen.add(key)
            actors.append(
                {
                    "id": actor_id or actor_name,
                    "name": actor_name,
                    "label": f"{actor_name} [{actor_id}]" if actor_id and actor_id != actor_name else actor_name,
                }
            )
    actors.sort(key=lambda item: item["name"])
    return {"state_csv": _repo_relative(path), "actors": actors}


def _is_within_root(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    root = ROOT.resolve()
    return resolved == root or root in resolved.parents


def _repo_relative(path: Path) -> str | None:
    resolved = path.expanduser().resolve()
    if not _is_within_root(resolved):
        return None
    return str(resolved.relative_to(ROOT))


def _resolve_repo_path(raw: Any) -> Path | None:
    if raw in (None, ""):
        return None
    candidate = Path(str(raw)).expanduser()
    resolved = (ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not _is_within_root(resolved):
        return None
    return resolved


def _list_run_manifests() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    manifests = [p.resolve() for p in RESULTS_DIR.glob("*/run_manifest.json") if p.is_file()]
    manifests.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return manifests


def _latest_manifest_path(command: str | None = None) -> Path | None:
    for manifest_path in _list_run_manifests():
        if command is None:
            return manifest_path
        try:
            if json.loads(manifest_path.read_text(encoding="utf-8")).get("command") == command:
                return manifest_path
        except Exception:
            continue
    return None


def _latest_result_run() -> Path | None:
    runs = [p for p in RESULTS_DIR.iterdir() if p.is_dir()] if RESULTS_DIR.exists() else []
    if not runs:
        return None
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]


def _read_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _artifacts_payload_from_run_dir(run_dir: Path, *, run_id: str | None = None, command: str | None = None) -> dict[str, Any]:
    resolved_dir = run_dir.resolve()
    candidates = {
        "run_manifest.json": resolved_dir / "run_manifest.json",
        "evaluation.json": resolved_dir / "evaluation.json",
        "dashboard.html": resolved_dir / "dashboard.html",
        "decision_brief.md": resolved_dir / "decision_brief.md",
        "game_result.json": resolved_dir / "game_result.json",
        "metrics.json": resolved_dir / "metrics.json",
        "world.csv": resolved_dir / "world.csv",
    }
    artifacts = {
        name: rel
        for name, path in candidates.items()
        if path.exists() and (rel := _repo_relative(path)) is not None
    }
    return {
        "run_id": run_id or resolved_dir.name,
        "command": command,
        "latest_run": run_id or resolved_dir.name,
        "artifacts": artifacts,
    }


def _artifacts_payload_from_manifest_path(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return {"run_id": None, "command": None, "latest_run": None, "artifacts": {}}

    run_dir = _resolve_repo_path(manifest.get("artifacts_dir")) or manifest_path.parent.resolve()
    payload = _artifacts_payload_from_run_dir(
        run_dir,
        run_id=str(manifest.get("run_id") or run_dir.name),
        command=str(manifest.get("command") or ""),
    )

    outputs = manifest.get("outputs", {})
    if isinstance(outputs, dict):
        explicit_names = {
            "evaluation_json": "evaluation.json",
            "dashboard_html": "dashboard.html",
            "brief_markdown": "decision_brief.md",
            "game_result_json": "game_result.json",
            "metrics_json": "metrics.json",
            "world_csv": "world.csv",
        }
        for output_key, artifact_name in explicit_names.items():
            resolved = _resolve_repo_path(outputs.get(output_key))
            rel = _repo_relative(resolved) if resolved and resolved.exists() else None
            if rel is not None:
                payload["artifacts"][artifact_name] = rel
        for raw_path in outputs.values():
            resolved = _resolve_repo_path(raw_path)
            rel = _repo_relative(resolved) if resolved and resolved.exists() else None
            if rel is not None:
                payload["artifacts"].setdefault(resolved.name, rel)

    manifest_rel = _repo_relative(manifest_path)
    if manifest_rel is not None:
        payload["manifest_path"] = manifest_rel
        payload["artifacts"]["run_manifest.json"] = manifest_rel
    return payload


def _latest_evaluation_path() -> Path | None:
    if not RESULTS_DIR.exists():
        return None
    candidates = list(RESULTS_DIR.glob("*/evaluation.json"))
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, float]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            traj = data.get("trajectory")
            n = len(traj) if isinstance(traj, list) else 0
        except Exception:
            n = 0
        return (n, path.stat().st_mtime)

    candidates.sort(key=score, reverse=True)
    return candidates[0]


def _brief_path_from_manifest_path(
    manifest_path: Path,
    manifest: dict[str, Any] | None = None,
) -> Path | None:
    manifest = manifest or _read_manifest(manifest_path)
    if manifest is None:
        return None
    outputs = manifest.get("outputs", {})
    brief_path = _resolve_repo_path(outputs.get("brief_markdown")) if isinstance(outputs, dict) else None
    if brief_path is not None and brief_path.exists():
        return brief_path
    fallback = manifest_path.parent / "decision_brief.md"
    return fallback if fallback.exists() else None


def _strip_markdown_tokens(line: str) -> str:
    cleaned = line.replace("**", "").replace("`", "").strip()
    if cleaned.startswith("_Note:") and cleaned.endswith("_"):
        cleaned = f"Note:{cleaned[len('_Note:'):-1]}"
    return cleaned.strip()


def _brief_excerpt_from_markdown(markdown: str) -> str:
    wanted_sections = ("Decision-Maker Interpretation", "Executive Summary")
    sections = _brief_sections_from_markdown(markdown)
    blocks: list[str] = []
    for section in wanted_sections:
        lines = sections.get(section, [])
        if not lines:
            continue
        if blocks:
            blocks.append("")
        blocks.append(section.upper())
        blocks.extend(lines)
    return "\n".join(blocks).strip() if blocks else markdown.strip()


def _brief_sections_from_markdown(markdown: str) -> dict[str, list[str]]:
    wanted_sections = (
        "Decision-Maker Interpretation",
        "Executive Summary",
        "Outcome Distribution",
        "Main Drivers",
    )
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in markdown.splitlines():
        if raw_line.startswith("## "):
            current = raw_line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(raw_line.rstrip())

    blocks: list[str] = []
    for section in wanted_sections:
        lines = [_strip_markdown_tokens(line) for line in sections.get(section, [])]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        if not lines:
            continue
        sections[section] = lines
    return sections


def _fallback_outcome_lines(evaluation: dict[str, Any]) -> list[str]:
    ranked = sorted(
        (evaluation.get("risk_probabilities") or {}).items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return [
        f"{idx}. {risk_name.replace('_', ' ').title()}: {100.0 * probability:.1f}%"
        for idx, (risk_name, probability) in enumerate(ranked[:5], start=1)
    ]


def _fallback_driver_lines(evaluation: dict[str, Any]) -> list[str]:
    ranked = sorted(
        (evaluation.get("driver_scores") or {}).items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return [
        f"{name.replace('_', ' ').title()}: {value:.2f}"
        for name, value in ranked[:5]
    ]


def _brief_excerpt_from_manifest_path(manifest_path: Path) -> str | None:
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return None

    brief_path = _brief_path_from_manifest_path(manifest_path, manifest)
    if brief_path is not None:
        return _brief_excerpt_from_markdown(brief_path.read_text(encoding="utf-8", errors="replace"))

    evaluation_path = _evaluation_path_from_manifest_path(manifest_path, manifest)
    if evaluation_path is None:
        return None

    try:
        from .briefing import AnalyticsBriefRenderer, BriefConfig

        payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
        rendered = AnalyticsBriefRenderer().render_payload(
            payload,
            config=BriefConfig(output_path="decision_brief.md"),
        )
        return _brief_excerpt_from_markdown(rendered)
    except Exception:
        return None


def _extract_actor_series(
    trajectory: list[dict[str, Any]],
    value_path: tuple[str, str],
    top_n: int = 3,
) -> list[dict[str, Any]]:
    if not trajectory:
        return []
    last = trajectory[-1]
    agents_last = last.get("agents", {}) if isinstance(last, dict) else {}
    if not isinstance(agents_last, dict):
        return []

    ranked: list[tuple[str, float]] = []
    for aid, payload in agents_last.items():
        try:
            v = float(payload[value_path[0]][value_path[1]])
        except Exception:
            continue
        ranked.append((aid, v))
    ranked.sort(key=lambda x: x[1], reverse=True)
    selected = [aid for aid, _ in ranked[:top_n]]

    series: list[dict[str, Any]] = []
    for aid in selected:
        points: list[float] = []
        for t in trajectory:
            try:
                points.append(float(t["agents"][aid][value_path[0]][value_path[1]]))
            except Exception:
                points.append(points[-1] if points else 0.0)
        name = trajectory[-1]["agents"][aid].get("name", aid)
        series.append({"id": aid, "name": name, "values": points})
    return series


def _global_inflation_series(trajectory: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for state in trajectory:
        agents = state.get("agents", {}) if isinstance(state, dict) else {}
        vals: list[float] = []
        if isinstance(agents, dict):
            for a in agents.values():
                try:
                    vals.append(float(a["economy"]["inflation"]))
                except Exception:
                    pass
        out.append(sum(vals) / len(vals) if vals else (out[-1] if out else 0.0))
    return out


def _global_metric_series(trajectory: list[dict[str, Any]], metric: str) -> list[float]:
    # Trajectory snapshots do not always include crisis_dashboard metrics;
    # derive stable synthetic channel from global_state when needed.
    out: list[float] = []
    for state in trajectory:
        g = state.get("global_state", {}) if isinstance(state, dict) else {}
        prices = g.get("prices", {}) if isinstance(g, dict) else {}
        if metric == "energy_stress":
            v = float(prices.get("energy", 1.0))
        elif metric == "food_stress":
            v = float(prices.get("food", 1.0))
        else:
            v = float(prices.get("metals", 1.0))
        out.append(v)
    return out


def _normalize_index(values: list[float], base: float = 100.0) -> list[float]:
    if not values:
        return []
    start = values[0] if values[0] != 0 else 1.0
    return [base * (v / start) for v in values]


def _normalize_unit(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if abs(hi - lo) < 1e-12:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _scenario_color(name: str) -> str:
    lower = name.lower()
    if any(x in lower for x in NEGATIVE_OUTCOME_HINTS):
        return "#d85c5c"
    if any(x in lower for x in POSITIVE_OUTCOME_HINTS):
        return "#3fbf74"
    return "#f0b85d"


def _empty_analytics_payload(summary: str, *, source: str | None = None, run_id: str | None = None, command: str | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "command": command,
        "source": source,
        "summary": summary,
        "brief_outcomes": [],
        "brief_drivers": [],
        "scenario_distribution": [],
        "criticality": 0.0,
        "years": [],
        "gdp_series": [],
        "social_tension_series": [],
        "inflation_series": [],
        "energy_pass_series": [],
        "core_infl_series": [],
        "quant": [],
    }


def _analytics_payload_from_evaluation_path(
    path: Path,
    *,
    run_id: str | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    if not path.exists():
        return _empty_analytics_payload(
            "No evaluation.json found yet. Run a scenario to populate analytics.",
            source=None,
            run_id=run_id,
            command=command,
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    evaluation = data.get("evaluation", {})
    trajectory = data.get("trajectory") if isinstance(data.get("trajectory"), list) else []

    if not trajectory:
        trajectory = []

    years: list[int] = []
    base_year = int(data.get("scenario", {}).get("base_year", 2026))
    years = [base_year + i for i in range(len(trajectory))] if trajectory else [base_year]

    risk_probs = evaluation.get("risk_probabilities", {})
    dist = [
        {"name": k.replace("_", " ").title(), "value": float(v), "color": _scenario_color(k)}
        for k, v in risk_probs.items()
    ]
    dist.sort(key=lambda x: x["value"], reverse=True)

    gdp_raw = _extract_actor_series(trajectory, ("economy", "gdp"), top_n=3)
    gdp_series = [
        {**s, "values": _normalize_index(s["values"], base=100.0)} for s in gdp_raw
    ]
    tension_series = _extract_actor_series(trajectory, ("society", "social_tension"), top_n=3)
    tension_series = [
        {**s, "values": _normalize_unit(s["values"])} for s in tension_series
    ]

    inflation = _global_inflation_series(trajectory)
    energy = _global_metric_series(trajectory, "energy_stress")
    core = [max(0.0, i - 0.4 * (e - 1.0)) for i, e in zip(inflation, energy)] if inflation else []

    global_metrics = (
        evaluation.get("crisis_dashboard", {})
        .get("global_context", {})
        .get("metrics", {})
    )

    def _metric_card(name: str, label: str) -> dict[str, Any]:
        metric = global_metrics.get(name, {})
        try:
            raw_value = float(metric.get("value", 0.0))
        except Exception:
            raw_value = 0.0
        try:
            scale_value = float(metric.get("severity", metric.get("level", 0.0)))
        except Exception:
            scale_value = 0.0
        scale_value = max(0.0, min(1.0, scale_value))
        unit = str(metric.get("unit", "index") or "index")
        threshold_flag = bool(metric.get("threshold_flag", False))
        threshold_text = "triggered" if threshold_flag else "within range"
        return {
            "name": label,
            "value": scale_value,
            "min": 0.0,
            "max": 1.0,
            "note": f"severity scale (0-1) • raw {raw_value:.2f} {unit} • {threshold_text}",
            "raw_value": raw_value,
            "unit": unit,
        }

    quant = [
        _metric_card("global_oil_market_stress", "Global oil market stress"),
        _metric_card("global_sanctions_footprint", "Sanctions footprint"),
        _metric_card("global_trade_fragmentation", "Trade fragmentation"),
        _metric_card("global_energy_volume_gap", "Energy volume gap"),
    ]

    dom = evaluation.get("dominant_outcomes", [])
    summary = (
        f"Dominant risk regimes: {', '.join(dom[:3]).replace('_', ' ')}. "
        f"Top crisis probability mass remains in high-stress branches; stabilize debt rollover and trade fragmentation first."
        if dom
        else "No dominant outcomes available yet."
    )

    return {
        "run_id": run_id,
        "command": command,
        "source": str(path.relative_to(ROOT)),
        "summary": summary,
        "brief_outcomes": _fallback_outcome_lines(evaluation),
        "brief_drivers": _fallback_driver_lines(evaluation),
        "scenario_distribution": dist[:8],
        "criticality": float(evaluation.get("criticality_score", 0.0)),
        "years": years,
        "gdp_series": gdp_series,
        "social_tension_series": tension_series,
        "inflation_series": inflation,
        "energy_pass_series": _normalize_unit(energy),
        "core_infl_series": core,
        "quant": quant,
    }


def _analytics_payload_from_manifest_path(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return _empty_analytics_payload("Unable to read run manifest.", source=None)

    run_id = str(manifest.get("run_id") or manifest_path.parent.name)
    command = str(manifest.get("command") or "")
    evaluation_path = _evaluation_path_from_manifest_path(manifest_path, manifest)
    if evaluation_path is None:
        source = _repo_relative(manifest_path)
        return _empty_analytics_payload(
            "This run did not produce an evaluation artifact for analytics rendering.",
            source=source,
            run_id=run_id,
            command=command,
        )
    payload = _analytics_payload_from_evaluation_path(evaluation_path, run_id=run_id, command=command)
    brief_excerpt = _brief_excerpt_from_manifest_path(manifest_path)
    if brief_excerpt:
        payload["summary"] = brief_excerpt
    brief_path = _brief_path_from_manifest_path(manifest_path, manifest)
    if brief_path is not None:
        sections = _brief_sections_from_markdown(brief_path.read_text(encoding="utf-8", errors="replace"))
        payload["brief_outcomes"] = sections.get("Outcome Distribution", payload["brief_outcomes"])
        payload["brief_drivers"] = sections.get("Main Drivers", payload["brief_drivers"])
    return payload


def _evaluation_path_from_manifest_path(
    manifest_path: Path,
    manifest: dict[str, Any] | None = None,
) -> Path | None:
    manifest = manifest or _read_manifest(manifest_path)
    if manifest is None:
        return None
    outputs = manifest.get("outputs", {})
    evaluation_path = _resolve_repo_path(outputs.get("evaluation_json")) if isinstance(outputs, dict) else None
    if evaluation_path is not None and evaluation_path.exists():
        return evaluation_path
    fallback = manifest_path.parent / "evaluation.json"
    return fallback if fallback.exists() else None


def _latest_analytics_payload() -> dict[str, Any]:
    for manifest_path in _list_run_manifests():
        if _evaluation_path_from_manifest_path(manifest_path) is not None:
            return _analytics_payload_from_manifest_path(manifest_path)

    path = _latest_evaluation_path()
    if path is None:
        return _empty_analytics_payload("No evaluation.json found yet. Run a scenario to populate analytics.")
    return _analytics_payload_from_evaluation_path(path)


def _latest_artifacts_payload() -> dict[str, Any]:
    manifest_path = _latest_manifest_path()
    if manifest_path is not None:
        return _artifacts_payload_from_manifest_path(manifest_path)

    run_dir = _latest_result_run()
    if run_dir is None:
        return {"run_id": None, "command": None, "latest_run": None, "artifacts": {}}
    return _artifacts_payload_from_run_dir(run_dir)


def _append_tail(lines: list[str], text: str, max_len: int = 120) -> None:
    for raw in text.splitlines():
        if raw.strip():
            lines.append(raw)
    if len(lines) > max_len:
        del lines[:-max_len]


def _update_progress(run: RunState, line: str) -> None:
    l = line.lower()
    for idx, marker in enumerate(
        (
            "baseline",
            "resolve_foreign_policy",
            "sanctions",
            "resource",
            "economy",
            "migration",
            "reconcile",
            "credit",
        ),
        start=1,
    ):
        if marker in l:
            run.step_index = max(run.step_index, idx)
            run.progress = min(100.0, (run.step_index / run.step_total) * 100.0)
            run.note = line[:180]
            return

    if line.startswith("[sim]"):
        try:
            pct = float(line.split("%", 1)[0].split()[-1])
            run.progress = max(run.progress, pct)
            run.note = line[:180]
            run.step_index = max(run.step_index, int(round((run.progress / 100.0) * run.step_total)))
        except Exception:
            pass


def _select_manifest_for_run(command: str, *, known_manifests: set[Path], started_at: float) -> Path | None:
    candidates: list[Path] = []
    for manifest_path in _list_run_manifests():
        manifest = _read_manifest(manifest_path)
        if manifest is None:
            continue
        if str(manifest.get("command") or "") != command:
            continue
        mtime = manifest_path.stat().st_mtime
        if manifest_path not in known_manifests or mtime >= started_at - 1.0:
            candidates.append(manifest_path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _run_command_async(run: RunState, argv: list[str], env: dict[str, str], known_manifests: set[Path]) -> None:
    run.status = "running"
    run.started_at = time.time()
    run.command = " ".join(shlex.quote(x) for x in argv)
    command = argv[3] if len(argv) > 3 else ""

    proc = subprocess.Popen(
        argv,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        bufsize=1,
    )

    def read_pipe(stream, sink: list[str], is_err: bool) -> None:
        assert stream is not None
        for line in stream:
            _append_tail(sink, line)
            if is_err:
                _update_progress(run, line.strip())

    t_out = threading.Thread(target=read_pipe, args=(proc.stdout, run.stdout_tail, False), daemon=True)
    t_err = threading.Thread(target=read_pipe, args=(proc.stderr, run.stderr_tail, True), daemon=True)
    t_out.start()
    t_err.start()

    code = proc.wait()
    t_out.join(timeout=1.0)
    t_err.join(timeout=1.0)

    run.return_code = code
    run.ended_at = time.time()
    run.progress = 100.0 if code == 0 else max(run.progress, 1.0)
    run.status = "completed" if code == 0 else "failed"
    run.note = "Simulation complete" if code == 0 else "Simulation failed"
    if code == 0 and run.started_at is not None:
        manifest_path = _select_manifest_for_run(command, known_manifests=known_manifests, started_at=run.started_at)
        if manifest_path is not None:
            payload = _artifacts_payload_from_manifest_path(manifest_path)
            run.artifacts = payload.get("artifacts", {})
            run.manifest_path = payload.get("manifest_path")
            return
    fallback = _latest_artifacts_payload()
    run.artifacts = fallback.get("artifacts", {})
    run.manifest_path = fallback.get("manifest_path")


def _build_cli_from_payload(payload: dict[str, Any]) -> list[str]:
    command = str(payload.get("command", "question"))
    args = ["python3", "-m", "gim", command]

    def add_flag(name: str, value: Any) -> None:
        if value is None:
            return
        value_s = str(value).strip()
        if value_s == "":
            return
        args.extend([name, value_s])

    if command == "question":
        add_flag("--question", payload.get("question"))
        raw_actors = payload.get("actors", "")
        if isinstance(raw_actors, (list, tuple)):
            parsed_actors = [str(actor).strip() for actor in raw_actors if str(actor).strip()]
        else:
            actors = str(raw_actors).strip()
            if actors:
                try:
                    parsed_actors = shlex.split(actors)
                except ValueError:
                    parsed_actors = actors.split()
            else:
                parsed_actors = []
        if parsed_actors:
            args.extend(["--actors", *parsed_actors])
        add_flag("--template", payload.get("template"))

    add_flag("--state-year", payload.get("state_year"))
    max_countries = payload.get("max_countries")
    if str(max_countries).strip() not in ("", "0", "None"):
        add_flag("--max-countries", max_countries)

    state_csv = str(payload.get("state_csv", "")).strip()
    if state_csv:
        args.extend(["--state-csv", state_csv])

    if command in {"question", "game", "calibrate"}:
        add_flag("--horizon", payload.get("horizon"))
        if payload.get("sim", True):
            args.append("--sim")
        add_flag("--background-policy", payload.get("background_policy"))
        add_flag("--llm-refresh", payload.get("llm_refresh"))
        add_flag("--llm-refresh-years", payload.get("llm_refresh_years"))

    if command in {"question", "game"}:
        if payload.get("dashboard", True):
            args.append("--dashboard")
            add_flag("--dashboard-output", payload.get("dashboard_output") or "dashboard.html")
        if payload.get("brief", True):
            args.append("--brief")
            add_flag("--brief-output", payload.get("brief_output") or "decision_brief.md")
        if payload.get("narrative", False):
            args.append("--narrative")

    if payload.get("json", False):
        args.append("--json")

    return args


class UIHandler(BaseHTTPRequestHandler):
    server_version = "GIM15UI/1.0"

    def _send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_text(self, payload: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        raw = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_text("Not found", status=404)
            return
        data = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self._send_file(UI_HTML)
            return

        if path == "/api/docs":
            self._send_json({"docs": _list_docs()})
            return

        if path == "/api/state-csvs":
            self._send_json({"state_csvs": _list_state_csvs()})
            return

        if path == "/api/actors":
            raw_state_csv = query.get("state_csv", [""])[0].strip()
            try:
                self._send_json(_list_actor_options(raw_state_csv or None))
            except ValueError:
                self._send_json({"error": "invalid state csv"}, status=400)
            return

        if path == "/docs/view":
            rel = query.get("path", [""])[0]
            try:
                target = _safe_join(ROOT, rel)
            except Exception:
                self._send_text("Invalid path", status=400)
                return
            if not target.exists():
                self._send_text("Not found", status=404)
                return
            text = target.read_text(encoding="utf-8", errors="replace")
            body = f"""<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(rel)}</title>
            <style>body{{background:#0d1117;color:#e6edf3;font-family:ui-monospace,Menlo,monospace;margin:0;padding:18px;}}
            pre{{white-space:pre-wrap;line-height:1.4;}}</style></head><body><h3>{html.escape(rel)}</h3><pre>{html.escape(text)}</pre></body></html>"""
            self._send_text(body, content_type="text/html; charset=utf-8")
            return

        if path == "/api/artifacts/latest":
            self._send_json(_latest_artifacts_payload())
            return

        if path == "/api/analytics/latest":
            self._send_json(_latest_analytics_payload())
            return

        if path.startswith("/api/run/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) != 4:
                self._send_text("Not found", status=404)
                return
            rid = parts[2]
            action = parts[3]
            with RUNS_LOCK:
                run = RUNS.get(rid)
            if run is None:
                self._send_json({"error": "run not found"}, status=404)
                return
            if action == "status":
                self._send_json(
                    {
                        "run_id": run.run_id,
                        "status": run.status,
                        "progress": run.progress,
                        "step_index": run.step_index,
                        "step_total": run.step_total,
                        "note": run.note,
                        "return_code": run.return_code,
                        "command": run.command,
                        "stdout_tail": run.stdout_tail[-40:],
                        "stderr_tail": run.stderr_tail[-40:],
                        "artifacts": run.artifacts,
                        "manifest_path": run.manifest_path,
                    }
                )
                return
            if action == "artifacts":
                if run.manifest_path:
                    manifest_path = _safe_join(ROOT, run.manifest_path)
                    self._send_json(_artifacts_payload_from_manifest_path(manifest_path))
                else:
                    self._send_json(
                        {
                            "run_id": run.run_id,
                            "command": run.command,
                            "latest_run": run.run_id,
                            "artifacts": run.artifacts,
                        }
                    )
                return
            if action == "analytics":
                if run.manifest_path:
                    manifest_path = _safe_join(ROOT, run.manifest_path)
                    self._send_json(_analytics_payload_from_manifest_path(manifest_path))
                else:
                    self._send_json(
                        _empty_analytics_payload(
                            "Analytics are not ready for this run yet.",
                            source=None,
                            run_id=run.run_id,
                            command=run.command,
                        )
                    )
                return
            self._send_text("Not found", status=404)
            return

        if path == "/api/download":
            rel = query.get("path", [""])[0]
            try:
                target = _safe_join(ROOT, rel)
            except Exception:
                self._send_text("Invalid path", status=400)
                return
            self._send_file(target)
            return

        self._send_text("Not found", status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/run":
            content_len = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_len) if content_len > 0 else b"{}"
            payload = json.loads(body.decode("utf-8"))

            run_id = f"run-{uuid.uuid4().hex[:10]}"
            run = RunState(run_id=run_id)

            argv = _build_cli_from_payload(payload)
            env = os.environ.copy()
            api_key = str(payload.get("deepseek_api_key", "")).strip()
            if api_key:
                env["DEEPSEEK_API_KEY"] = api_key

            with RUNS_LOCK:
                RUNS[run_id] = run

            known_manifests = set(_list_run_manifests())
            thread = threading.Thread(target=_run_command_async, args=(run, argv, env, known_manifests), daemon=True)
            thread.start()

            self._send_json({"run_id": run_id, "command": " ".join(shlex.quote(a) for a in argv)})
            return

        self._send_text("Not found", status=404)


def run_ui_server(host: str = "127.0.0.1", port: int = 8090) -> None:
    server = ThreadingHTTPServer((host, port), UIHandler)
    print(f"[ui] GIM15 UI server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_ui_server()
