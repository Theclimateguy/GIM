from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

from .decision_language import (
    OUTCOME_EXPLANATIONS,
    build_highlights,
    current_reading_text,
    scenario_summary_text,
    select_glossary_keys,
    top_driver_entries,
)
from .briefing import AnalyticsBriefRenderer, BriefConfig
from .explanations import DRIVER_LABELS
from .game_theory.equilibrium_runner import EquilibriumResult
from .game_runner import GameRunner
from .model_terms import DRIVER_EXPLANATIONS, TERM_EXPLANATIONS
from .runtime import WorldState
from .types import GameResult, RISK_LABELS, ScenarioDefinition, ScenarioEvaluation


RISK_COLORS = {
    "status_quo": "#2f855a",
    "controlled_suppression": "#b7791f",
    "internal_destabilization": "#c05621",
    "limited_proxy_escalation": "#dd6b20",
    "maritime_chokepoint_crisis": "#c53030",
    "direct_strike_exchange": "#9b2c2c",
    "broad_regional_escalation": "#742a2a",
    "negotiated_deescalation": "#2b6cb0",
}

SERIES_COLORS = (
    "#0f4c5c",
    "#e36414",
    "#6f1d1b",
    "#4f772d",
    "#7f5539",
    "#355070",
    "#8338ec",
    "#1b4332",
)

GLOBAL_CONTEXT_METRICS = (
    "global_oil_market_stress",
    "global_energy_volume_gap",
    "global_sanctions_footprint",
    "global_trade_fragmentation",
)


@dataclass
class DashboardConfig:
    output_path: str = "dashboard.html"
    show_trajectory: bool = True
    show_game_results: bool = False
    show_narrative: bool = False
    top_k_strategies: int = 5
    actor_filter: list[str] | None = None
    execution_label: str = "static"
    policy_mode_label: str = "snapshot"
    run_timestamp: str | None = None
    run_id: str | None = None
    n_runs: int = 1
    horizon_years: int = 0
    include_interpretive_summary: bool = True
    prefer_llm_interpretation: bool = True


class DashboardRenderer:
    def render(
        self,
        evaluation: ScenarioEvaluation,
        game_result: GameResult | None,
        equilibrium_result: EquilibriumResult | None,
        trajectory: list[WorldState] | None,
        scenario_def: ScenarioDefinition,
        config: DashboardConfig,
    ) -> str:
        snapshots = list(trajectory or [])
        if not snapshots:
            raise ValueError("Dashboard rendering requires at least one WorldState snapshot")

        initial_world = snapshots[0]
        terminal_world = snapshots[-1]
        actor_ids = self._resolve_actor_ids(initial_world, scenario_def, config.actor_filter)
        actor_names = [initial_world.agents[actor_id].name for actor_id in actor_ids if actor_id in initial_world.agents]
        scenario_dict = asdict(scenario_def)
        evaluation_dict = asdict(evaluation)
        trajectory_dicts = [asdict(state) for state in snapshots]

        initial_evaluation = self._initial_evaluation(
            initial_world=initial_world,
            scenario_def=scenario_def,
            game_result=game_result,
        )
        initial_evaluation_dict = asdict(initial_evaluation) if initial_evaluation is not None else None
        game_result_dict = asdict(game_result) if game_result is not None else None
        equilibrium_result_dict = asdict(equilibrium_result) if equilibrium_result is not None else None
        initial_dashboard = initial_evaluation.crisis_dashboard if initial_evaluation is not None else evaluation.crisis_dashboard
        years = self._timeline_years(scenario_def.base_year, len(snapshots))
        events_by_index = self._extract_events(snapshots)
        climate_event_count = sum(
            1 for labels in events_by_index.values() for label in labels if "climate" in label.lower()
        )
        del climate_event_count
        highlight_cards = [
            {"kind": item.kind, "title": item.title, "body": item.body}
            for item in build_highlights(
                evaluation=evaluation_dict,
                initial_evaluation=initial_evaluation_dict,
                game_result=game_result_dict,
                trajectory=trajectory_dicts,
                actor_ids=actor_ids,
            )
        ]
        brief_markdown = AnalyticsBriefRenderer().render(
            evaluation=evaluation,
            game_result=game_result,
            equilibrium_result=equilibrium_result,
            trajectory=snapshots,
            scenario_def=scenario_def,
            config=BriefConfig(
                output_path="decision_brief.md",
                include_trajectory=config.show_trajectory and len(snapshots) > 1,
                include_game_results=config.show_game_results and game_result is not None,
                execution_label=config.execution_label,
                policy_mode_label=config.policy_mode_label,
                run_timestamp=config.run_timestamp,
                run_id=config.run_id,
                n_runs=config.n_runs,
                horizon_years=config.horizon_years,
                include_interpretive_summary=config.include_interpretive_summary,
                prefer_llm_interpretation=config.prefer_llm_interpretation,
            ),
        )

        sections = [
            self._render_header(
                evaluation=evaluation,
                scenario_def=scenario_def,
                actor_names=actor_names,
                config=config,
                scenario_summary=scenario_summary_text(
                    scenario_dict,
                    evaluation_dict,
                    actor_names=actor_names,
                    horizon_years=config.horizon_years,
                ),
            ),
            self._render_brief_section(brief_markdown),
            self._render_outcomes(
                evaluation=evaluation,
                initial_evaluation=initial_evaluation,
                config=config,
                current_reading=current_reading_text(evaluation_dict),
            ),
            self._render_world_snapshot(
                evaluation=evaluation,
                initial_dashboard=initial_dashboard,
                initial_world=initial_world,
                terminal_world=terminal_world,
                actor_ids=actor_ids,
            ),
        ]

        if config.show_trajectory and len(snapshots) > 1:
            sections.append(
                self._render_trajectory_dynamics(
                    trajectory=snapshots,
                    years=years,
                    events_by_index=events_by_index,
                    glossary_keys=select_glossary_keys(evaluation_dict, actor_ids) + ["global_oil_market_stress"],
                )
            )

        sections.append(
            self._render_game_and_highlights(
                evaluation=evaluation,
                game_result=game_result,
                equilibrium_result=equilibrium_result,
                highlight_cards=highlight_cards,
                config=config,
            )
        )

        if config.show_narrative:
            sections.append(
                self._render_narrative(
                    evaluation=evaluation,
                    initial_evaluation=initial_evaluation,
                    highlight_cards=highlight_cards,
                )
            )

        title = escape(scenario_def.source_prompt or scenario_def.title)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GIM14 Decision Brief - {title}</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --paper: #fffdfa;
      --ink: #1d1b18;
      --muted: #6b665d;
      --line: #d7d0c4;
      --accent: #8c3d1f;
      --good: #2f855a;
      --warn: #b7791f;
      --bad: #9b2c2c;
      --blue: #1f4e79;
      --shadow: 0 12px 28px rgba(29, 27, 24, 0.08);
      --radius: 18px;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; background: radial-gradient(circle at top, #fff4e6 0%, var(--bg) 52%, #ece7dd 100%); color: var(--ink); }}
    body {{ font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Arial, sans-serif; line-height: 1.45; }}
    .page {{ max-width: 1420px; margin: 0 auto; padding: 28px 24px 48px; }}
    .hero {{
      background: linear-gradient(135deg, #1f2937 0%, #22304a 45%, #4a2f21 100%);
      color: #fffdf7;
      border-radius: 26px;
      padding: 26px 28px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -10% -55% auto;
      width: 280px;
      height: 280px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0) 70%);
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.3fr 1fr 1fr;
      gap: 18px;
      position: relative;
      z-index: 1;
    }}
    .eyebrow {{
      letter-spacing: 0.18em;
      text-transform: uppercase;
      font-size: 12px;
      color: rgba(255, 245, 230, 0.7);
      margin-bottom: 10px;
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 34px;
      line-height: 1.08;
      max-width: 860px;
    }}
    .hero-summary {{
      margin-top: 14px;
      max-width: 760px;
      color: rgba(255, 245, 230, 0.90);
      font-size: 15px;
      line-height: 1.55;
    }}
    .hero-meta, .hero-run {{
      display: grid;
      gap: 8px;
      align-content: start;
    }}
    .meta-card {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 16px;
      padding: 14px 16px;
      backdrop-filter: blur(6px);
    }}
    .meta-label {{
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.14em;
      color: rgba(255, 245, 230, 0.65);
      margin-bottom: 4px;
    }}
    .meta-value {{
      font-size: 18px;
      font-weight: 700;
      color: #fffdf7;
    }}
    .meta-sub {{
      font-size: 13px;
      color: rgba(255, 245, 230, 0.78);
      margin-top: 4px;
    }}
    .banner {{
      margin-top: 16px;
      padding: 12px 14px;
      border-radius: 14px;
      font-weight: 700;
      border: 1px solid rgba(255,255,255,0.2);
    }}
    .banner.warn {{ background: rgba(183, 121, 31, 0.22); color: #ffe8b3; }}
    .banner.bad {{ background: rgba(155, 44, 44, 0.24); color: #ffd6d6; }}
    .section {{
      margin-top: 24px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: baseline;
      margin-bottom: 18px;
    }}
    .section-title {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 28px;
      margin: 0;
    }}
    .section-note {{
      color: var(--muted);
      font-size: 14px;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 22px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      background: linear-gradient(180deg, #fffdf8 0%, #fbf7ef 100%);
    }}
    .card h3 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    .reading-box {{
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 14px;
      background: #f3ede2;
      border: 1px solid #ddd2be;
      color: #3b342c;
      font-size: 14px;
    }}
    .driver-list {{
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }}
    .driver-item {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      font-size: 14px;
    }}
    .driver-score {{
      font-variant-numeric: tabular-nums;
      font-weight: 700;
      color: #5b2a12;
      white-space: nowrap;
    }}
    .term {{
      position: relative;
      display: inline-block;
      border-bottom: 1px dotted rgba(59, 52, 44, 0.55);
      cursor: help;
    }}
    .term-tip {{
      position: absolute;
      left: 0;
      bottom: calc(100% + 10px);
      min-width: 240px;
      max-width: 320px;
      padding: 10px 12px;
      border-radius: 12px;
      background: #1f2937;
      color: #fffdf7;
      font-size: 12px;
      line-height: 1.45;
      box-shadow: 0 12px 24px rgba(29, 27, 24, 0.18);
      opacity: 0;
      pointer-events: none;
      transform: translateY(6px);
      transition: opacity 120ms ease, transform 120ms ease;
      z-index: 20;
    }}
    .term:hover .term-tip, .term:focus-within .term-tip {{
      opacity: 1;
      transform: translateY(0);
    }}
    .prob-list {{
      display: grid;
      gap: 12px;
    }}
    .prob-row {{
      display: grid;
      grid-template-columns: minmax(180px, 260px) 1fr auto;
      gap: 14px;
      align-items: center;
      font-size: 14px;
    }}
    .prob-label {{ font-weight: 700; }}
    .prob-track {{
      background: #efe8da;
      border-radius: 999px;
      overflow: hidden;
      height: 18px;
      border: 1px solid #ddd2be;
    }}
    .prob-fill {{
      height: 100%;
      border-radius: 999px;
    }}
    .prob-val {{
      font-variant-numeric: tabular-nums;
      font-weight: 700;
      min-width: 56px;
      text-align: right;
    }}
    .shift-table, .stress-table, .strategy-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .shift-table th, .shift-table td,
    .stress-table th, .stress-table td,
    .strategy-table th, .strategy-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
    }}
    .shift-table th, .stress-table th, .strategy-table th {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      color: var(--muted);
    }}
    .gauge-wrap {{
      display: grid;
      gap: 10px;
      align-items: center;
      justify-items: center;
      margin-top: 12px;
    }}
    .gauge-value {{
      font-size: 32px;
      font-weight: 800;
      margin-top: -8px;
    }}
    .gauge-caption {{
      color: var(--muted);
      font-size: 13px;
    }}
    .glossary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px 18px;
    }}
    .glossary-item {{
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fcf8f0;
    }}
    .glossary-item strong {{
      display: block;
      margin-bottom: 4px;
      font-size: 14px;
    }}
    .glossary-item span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .brief-markdown {{
      color: #2b2620;
      font-size: 15px;
      line-height: 1.6;
    }}
    .brief-markdown h1, .brief-markdown h2, .brief-markdown h3 {{
      font-family: Georgia, "Times New Roman", serif;
      color: #241f19;
      margin: 20px 0 10px;
    }}
    .brief-markdown h1 {{
      font-size: 28px;
      margin-top: 0;
    }}
    .brief-markdown h2 {{
      font-size: 22px;
    }}
    .brief-markdown h3 {{
      font-size: 18px;
    }}
    .brief-markdown p {{
      margin: 10px 0;
    }}
    .brief-markdown ul {{
      margin: 10px 0;
      padding-left: 22px;
    }}
    .brief-markdown li {{
      margin: 6px 0;
    }}
    .brief-markdown code {{
      background: #f3ede2;
      border: 1px solid #ddd2be;
      border-radius: 8px;
      padding: 1px 6px;
      font-size: 0.95em;
    }}
    .brief-markdown table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      font-size: 14px;
    }}
    .brief-markdown th, .brief-markdown td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    .brief-markdown th {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      color: var(--muted);
    }}
    .brief-markdown blockquote {{
      margin: 14px 0;
      padding: 12px 14px;
      border-left: 4px solid #d5b46a;
      background: #fff7df;
      color: #6c5523;
      border-radius: 10px;
    }}
    .matrix-grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 22px;
    }}
    .meter-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .meter {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      background: #fffdf9;
    }}
    .meter-name {{
      font-weight: 700;
      font-size: 14px;
      margin-bottom: 10px;
    }}
    .meter-track {{
      position: relative;
      height: 14px;
      background: #efe7d8;
      border-radius: 999px;
      overflow: hidden;
      margin-bottom: 10px;
    }}
    .meter-fill {{
      height: 100%;
      border-radius: 999px;
      opacity: 0.9;
    }}
    .meter-fill.initial {{
      position: absolute;
      inset: 0 auto 0 0;
      background: rgba(31, 78, 121, 0.45);
      border-right: 2px solid rgba(17, 24, 39, 0.3);
    }}
    .meter-fill.terminal {{
      background: linear-gradient(90deg, #c53030 0%, #dd6b20 100%);
    }}
    .meter-values {{
      display: flex;
      justify-content: space-between;
      color: var(--muted);
      font-size: 13px;
    }}
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 14px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: linear-gradient(180deg, #fffefb 0%, #fbf5eb 100%);
    }}
    .metric-card h4 {{
      margin: 0 0 12px;
      font-size: 17px;
    }}
    .metric-list {{
      display: grid;
      gap: 10px;
    }}
    .metric-row {{
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: center;
      font-size: 14px;
    }}
    .metric-chip {{
      font-weight: 700;
    }}
    .metric-sev {{
      min-width: 48px;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .metric-mom {{
      min-width: 24px;
      text-align: center;
      font-size: 16px;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .chart-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: linear-gradient(180deg, #fffefb 0%, #fbf7ef 100%);
    }}
    .chart-title {{
      margin: 0 0 8px;
      font-weight: 800;
      font-size: 16px;
    }}
    .chart-note {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      margin-top: 10px;
      font-size: 12px;
      color: var(--muted);
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }}
    .legend-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }}
    .event-strip {{
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .event-pill {{
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      border: 1px solid #d7cab3;
      background: #f8f1e3;
      color: #6b4f2d;
    }}
    .highlights-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .highlight {{
      border-radius: 18px;
      padding: 16px 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #fffdf9 0%, #fbf2e7 100%);
    }}
    .highlight.k-up {{ border-left: 6px solid var(--bad); }}
    .highlight.k-down {{ border-left: 6px solid var(--good); }}
    .highlight.k-flat {{ border-left: 6px solid var(--warn); }}
    .highlight-title {{
      font-size: 13px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 800;
      margin-bottom: 6px;
      color: var(--accent);
    }}
    .highlight-body {{
      font-size: 15px;
      color: var(--ink);
    }}
    .best-strategy {{
      background: linear-gradient(180deg, #f4fbf2 0%, #eef8ec 100%);
      box-shadow: inset 0 0 0 2px rgba(47, 133, 90, 0.25);
    }}
    .warning-note {{
      margin-bottom: 12px;
      padding: 10px 12px;
      border-radius: 12px;
      background: #fff7df;
      border: 1px solid #ecd9a2;
      color: #8a6116;
      font-size: 14px;
      font-weight: 700;
    }}
    .narrative {{
      font-size: 16px;
      color: #2d3748;
      background: linear-gradient(180deg, #fffefc 0%, #faf4ea 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
    }}
    .mono {{
      font-variant-numeric: tabular-nums;
      font-feature-settings: "tnum";
    }}
    @media (max-width: 1120px) {{
      .hero-grid, .two-col, .matrix-grid, .chart-grid, .glossary-grid {{ grid-template-columns: 1fr; }}
      .prob-row {{ grid-template-columns: 1fr; }}
      .meter-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {''.join(sections)}
  </div>
</body>
 </html>"""

    def write_dashboard_artifacts(
        self,
        *,
        evaluation: ScenarioEvaluation,
        game_result: GameResult | None,
        equilibrium_result: EquilibriumResult | None,
        trajectory: list[WorldState] | None,
        scenario_def: ScenarioDefinition,
        config: DashboardConfig,
        save_json: bool = False,
    ) -> dict[str, str]:
        html = self.render(
            evaluation=evaluation,
            game_result=game_result,
            equilibrium_result=equilibrium_result,
            trajectory=trajectory,
            scenario_def=scenario_def,
            config=config,
        )
        output_path = Path(config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        written = {"html": str(output_path)}

        if save_json:
            json_path = output_path.with_name("evaluation.json")
            payload = {
                "scenario": asdict(scenario_def),
                "evaluation": asdict(evaluation),
                "game_result": asdict(game_result) if game_result is not None else None,
                "equilibrium_result": asdict(equilibrium_result) if equilibrium_result is not None else None,
                "trajectory": [asdict(state) for state in (trajectory or [])],
                "dashboard_config": asdict(config),
            }
            json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            written["json"] = str(json_path)

        return written

    def _render_header(
        self,
        *,
        evaluation: ScenarioEvaluation,
        scenario_def: ScenarioDefinition,
        actor_names: list[str],
        config: DashboardConfig,
        scenario_summary: str,
    ) -> str:
        run_timestamp = config.run_timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
        horizon_years = config.horizon_years
        display_year = scenario_def.display_year or scenario_def.base_year
        if horizon_years <= 0:
            horizon_label = f"{scenario_def.horizon_months} months"
        else:
            horizon_label = f"{horizon_years} years ({display_year}->{display_year + horizon_years})"

        actor_line = " &middot; ".join(escape(name) for name in actor_names) or "Auto-resolved"
        confidence_banner = ""
        if evaluation.calibration_score < 0.60:
            confidence_banner = '<div class="banner bad">Low confidence result. Calibration score is below 0.60.</div>'
        elif evaluation.calibration_score < 0.75:
            confidence_banner = '<div class="banner warn">Low confidence result. Calibration score is below 0.75.</div>'

        return f"""
<section class="hero">
  <div class="hero-grid">
    <div>
      <div class="eyebrow">Scenario</div>
      <h1>{escape(scenario_def.source_prompt or scenario_def.title)}</h1>
      <div class="meta-sub">{actor_line}</div>
      <div class="hero-summary">{escape(scenario_summary)}</div>
      {confidence_banner}
    </div>
    <div class="hero-meta">
      <div class="meta-card">
        <div class="meta-label">Template</div>
        <div class="meta-value">{escape(scenario_def.template_id)}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Data snapshot</div>
        <div class="meta-value">{scenario_def.base_year}</div>
        <div class="meta-sub">Display year: {scenario_def.display_year}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Horizon</div>
        <div class="meta-value">{escape(horizon_label)}</div>
      </div>
    </div>
    <div class="hero-run">
      <div class="meta-card">
        <div class="meta-label">Path</div>
        <div class="meta-value">{escape(config.execution_label)} / {escape(config.policy_mode_label)}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Run</div>
        <div class="meta-value">{escape(run_timestamp)}</div>
        <div class="meta-sub">id={escape(config.run_id or 'n/a')} · n_runs={config.n_runs} · mean_score={evaluation.calibration_score:.2f}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Criticality</div>
        <div class="meta-value">{evaluation.criticality_score:.2f}</div>
        <div class="meta-sub">physical={evaluation.physical_consistency_score:.2f}</div>
      </div>
    </div>
  </div>
</section>
"""

    def _render_outcomes(
        self,
        *,
        evaluation: ScenarioEvaluation,
        initial_evaluation: ScenarioEvaluation | None,
        config: DashboardConfig,
        current_reading: str,
    ) -> str:
        rows = []
        for rank, risk_name in enumerate(
            sorted(evaluation.risk_probabilities, key=evaluation.risk_probabilities.get, reverse=True),
            start=1,
        ):
            probability = evaluation.risk_probabilities[risk_name]
            rows.append(
                f"""
<div class="prob-row">
  <div class="prob-label">{escape(RISK_LABELS.get(risk_name, risk_name))}{'  <strong style="color:#8c3d1f;">TOP</strong>' if rank == 1 else ''}</div>
  <div class="prob-track"><div class="prob-fill" style="width:{100.0 * probability:.1f}%; background:{RISK_COLORS.get(risk_name, '#8c3d1f')};"></div></div>
  <div class="prob-val mono">{100.0 * probability:.1f}%</div>
</div>"""
            )

        shift_block = ""
        if config.show_trajectory and initial_evaluation is not None:
            top_outcomes = list(evaluation.dominant_outcomes[:3])
            shift_rows = []
            for risk_name in top_outcomes:
                start_value = initial_evaluation.risk_probabilities.get(risk_name, 0.0)
                end_value = evaluation.risk_probabilities.get(risk_name, 0.0)
                delta = end_value - start_value
                shift_rows.append(
                    f"""
<tr>
  <td>{escape(RISK_LABELS.get(risk_name, risk_name))}</td>
  <td class="mono">{100.0 * start_value:.1f}%</td>
  <td class="mono">{100.0 * end_value:.1f}%</td>
  <td class="mono">{delta:+.1%} {self._arrow_entity(delta)}</td>
</tr>"""
                )
            shift_block = f"""
<div class="card">
  <h3>Trajectory shift</h3>
  <table class="shift-table">
    <thead>
      <tr><th>Outcome</th><th>t=0</th><th>t=N</th><th>Delta</th></tr>
    </thead>
    <tbody>
      {''.join(shift_rows)}
    </tbody>
  </table>
</div>"""
        top_drivers = sorted(
            evaluation.driver_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        driver_block = "".join(
            f"""
<div class="driver-item">
  <div>{self._term_html(driver_name, DRIVER_LABELS.get(driver_name, self._labelize(driver_name)))}</div>
  <div class="driver-score">{driver_value:.2f}</div>
</div>"""
            for driver_name, driver_value in top_drivers
        )

        return f"""
<section class="section">
  <div class="section-header">
    <h2 class="section-title">Outcome Distribution</h2>
    <div class="section-note">Probabilistic answer to the scenario question</div>
  </div>
  <div class="two-col">
    <div class="card">
      <h3>Probability bars</h3>
      <div class="prob-list">
        {''.join(rows)}
      </div>
      {'<div style="margin-top:18px;">' + shift_block + '</div>' if shift_block else ''}
    </div>
    <div class="card">
      <h3>Criticality gauge</h3>
      {self._render_gauge(evaluation.criticality_score)}
      <div class="reading-box"><strong>Current reading.</strong> {escape(current_reading)}</div>
      <div class="reading-box">
        <strong>Key drivers</strong>
        <div class="driver-list">
          {driver_block}
        </div>
      </div>
    </div>
  </div>
</section>
"""

    def _render_world_snapshot(
        self,
        *,
        evaluation: ScenarioEvaluation,
        initial_dashboard: Any,
        initial_world: WorldState,
        terminal_world: WorldState,
        actor_ids: list[str],
    ) -> str:
        stress_rows = []
        for actor_id in actor_ids:
            if actor_id not in terminal_world.agents:
                continue
            init_agent = initial_world.agents[actor_id]
            term_agent = terminal_world.agents[actor_id]
            report = evaluation.crisis_dashboard.agents.get(actor_id)
            if report is None:
                continue

            gdp_delta = self._pct_change(init_agent.economy.gdp, term_agent.economy.gdp)
            debt_ratio = self._safe_div(term_agent.economy.public_debt, max(term_agent.economy.gdp, 1e-9))
            inflation_metric = report.metrics["inflation"]
            conflict_metric = report.metrics["conflict_escalation_pressure"]
            social_value = term_agent.society.social_tension
            climate_value = term_agent.climate.climate_risk
            inflation_label = self._severity_band(inflation_metric.severity)

            stress_rows.append(
                f"""
<tr>
  <td><strong>{escape(term_agent.name)}</strong></td>
  <td class="mono" style="background:{self._delta_heat(gdp_delta)};">{gdp_delta:+.1f}%</td>
  <td class="mono" style="background:{self._heat_color(min(debt_ratio / 1.5, 1.0))};">{debt_ratio:.2f}</td>
  <td style="background:{self._heat_color(inflation_metric.severity)};">{inflation_label}</td>
  <td class="mono" style="background:{self._heat_color(social_value)};">{social_value:.2f}</td>
  <td class="mono" style="background:{self._heat_color(conflict_metric.severity)};">{conflict_metric.severity:.2f}</td>
  <td class="mono" style="background:{self._heat_color(climate_value)};">{climate_value:.2f}</td>
</tr>"""
            )

        meters = []
        for metric_name in GLOBAL_CONTEXT_METRICS:
            initial_metric = initial_dashboard.global_context.metrics.get(metric_name)
            terminal_metric = evaluation.crisis_dashboard.global_context.metrics.get(metric_name)
            if initial_metric is None or terminal_metric is None:
                continue
            delta = terminal_metric.level - initial_metric.level
            meters.append(
                f"""
<div class="meter">
  <div class="meter-name">{self._term_html(metric_name, self._labelize(metric_name))}</div>
  <div class="meter-track">
    <div class="meter-fill initial" style="width:{100.0 * initial_metric.level:.1f}%;"></div>
    <div class="meter-fill terminal" style="width:{100.0 * terminal_metric.level:.1f}%;"></div>
  </div>
  <div class="meter-values">
    <span>t=0 <strong class="mono">{initial_metric.level:.2f}</strong></span>
    <span>t=N <strong class="mono">{terminal_metric.level:.2f}</strong> {self._arrow_entity(delta)}</span>
  </div>
</div>"""
            )

        metric_cards = []
        for actor_id in actor_ids:
            report = evaluation.crisis_dashboard.agents.get(actor_id)
            if report is None:
                continue
            rows = []
            for metric_name in report.top_metric_names[:3]:
                metric = report.metrics[metric_name]
                rows.append(
                    f"""
<div class="metric-row">
  <div class="metric-chip">{self._term_html(metric_name, self._labelize(metric_name))}</div>
  <div class="metric-sev mono">{metric.severity:.2f}</div>
  <div class="metric-mom">{self._arrow_entity(metric.momentum)}</div>
</div>"""
                )
            metric_cards.append(
                f"""
<div class="metric-card">
  <h4>{escape(report.agent_name)}</h4>
  <div class="metric-list">
    {''.join(rows)}
  </div>
</div>"""
            )

        return f"""
<section class="section">
  <div class="section-header">
    <h2 class="section-title">World State Snapshot</h2>
    <div class="section-note">Terminal moment if simulated, otherwise current loaded world state</div>
  </div>
  <div class="matrix-grid">
    <div class="card">
      <h3>Actor stress matrix</h3>
      <table class="stress-table">
        <thead>
          <tr>
            <th>Actor</th>
            <th>{self._term_html("gdp_delta_pct", "GDP \u0394%")}</th>
            <th>{self._term_html("debt_gdp", "Debt/GDP")}</th>
            <th>Inflation</th>
            <th>{self._term_html("social_tension", "Social")}</th>
            <th>{self._term_html("conflict_escalation_pressure", "Conflict")}</th>
            <th>{self._term_html("climate_risk", "Climate")}</th>
          </tr>
        </thead>
        <tbody>
          {''.join(stress_rows)}
        </tbody>
      </table>
    </div>
    <div class="card">
      <h3>Global context meters</h3>
      <div class="meter-grid">
        {''.join(meters)}
      </div>
    </div>
  </div>
  <div class="card" style="margin-top:22px;">
    <h3>Top crisis metrics per actor</h3>
    <div class="metrics-grid">
      {''.join(metric_cards)}
    </div>
  </div>
</section>
"""

    def _render_trajectory_dynamics(
        self,
        *,
        trajectory: list[WorldState],
        years: list[int],
        events_by_index: dict[int, list[str]],
        glossary_keys: list[str],
    ) -> str:
        gdp_series = {"World GDP": [self._world_gdp(state) for state in trajectory]}
        debt_series = {"Global debt / GDP": [self._global_debt_ratio(state) for state in trajectory]}
        social_series = {
            "Global social tension": [self._global_social_tension(state) for state in trajectory]
        }

        emissions_series = {"Global emissions": [self._global_emissions(state) for state in trajectory]}
        energy_series = {"Energy price": [state.global_state.prices.get("energy", 1.0) for state in trajectory]}

        charts = [
            self._render_line_chart_card(
                title="Economic output",
                note="World GDP, aggregated across all agents",
                years=years,
                series=gdp_series,
                markers=events_by_index,
            ),
            self._render_line_chart_card(
                title="Fiscal stress",
                note="Global public debt divided by world GDP",
                years=years,
                series=debt_series,
                markers=events_by_index,
                value_formatter=lambda value: f"{value:.2f}",
            ),
            self._render_line_chart_card(
                title="Social stability",
                note="Population-weighted global social tension on a 0..1 scale",
                years=years,
                series=social_series,
                markers=events_by_index,
                min_override=0.0,
                max_override=1.0,
                value_formatter=lambda value: f"{value:.2f}",
            ),
            self._render_dual_axis_chart_card(
                title="Climate and energy",
                note="Global annual emissions and energy price",
                years=years,
                left_series=emissions_series,
                right_series=energy_series,
                markers=events_by_index,
            ),
        ]

        return f"""
<section class="section">
  <div class="section-header">
    <h2 class="section-title">Trajectory Dynamics</h2>
    <div class="section-note">Year-by-year global view. Each chart uses its own scale to avoid cross-country distortion.</div>
  </div>
  <div class="chart-grid">
    {''.join(charts)}
  </div>
  {self._render_glossary(glossary_keys)}
</section>
"""

    def _render_game_and_highlights(
        self,
        *,
        evaluation: ScenarioEvaluation,
        game_result: GameResult | None,
        equilibrium_result: EquilibriumResult | None,
        highlight_cards: list[dict[str, str]],
        config: DashboardConfig,
    ) -> str:
        strategy_block = ""
        if config.show_game_results and game_result is not None:
            rows = []
            for index, combination in enumerate(game_result.combinations[: config.top_k_strategies], start=1):
                profile_lines = []
                for player in game_result.game.players:
                    action = combination.actions.get(player.player_id, "n/a")
                    profile_lines.append(f"{escape(player.display_name)}: {escape(self._titleize_action(action))}")
                crit_delta = combination.evaluation.criticality_score - game_result.baseline_evaluation.criticality_score
                row_class = "best-strategy" if index == 1 else ""
                rows.append(
                    f"""
<tr class="{row_class}">
  <td class="mono">{index}</td>
  <td>{'<br/>'.join(profile_lines)}</td>
  <td class="mono">{combination.total_payoff:+.2f}</td>
  <td class="mono">{crit_delta:+.2f} {self._arrow_entity(crit_delta)}</td>
</tr>"""
                )

            warning = ""
            if game_result.truncated_action_space:
                warning = '<div class="warning-note">Action space was truncated before evaluation. Only the first three actions per player were searched.</div>'

            strategy_block = f"""
<div class="card" style="margin-bottom:22px;">
  <h3>Strategy ranking</h3>
  {warning}
  <table class="strategy-table">
    <thead>
      <tr><th>Rank</th><th>Strategy profile</th><th>Score</th><th>Criticality \u0394</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</div>"""

        highlights_html = "".join(
            f"""
<div class="highlight {escape(card['kind'])}">
  <div class="highlight-title">{escape(card['title'])}</div>
  <div class="highlight-body">{escape(card['body'])}</div>
</div>"""
            for card in highlight_cards
        )
        equilibrium_block = self._render_equilibrium_block(equilibrium_result)

        return f"""
<section class="section">
  <div class="section-header">
    <h2 class="section-title">Policy Game Results and Orchestrator Highlights</h2>
    <div class="section-note">Decision-facing summary generated from model outputs only</div>
  </div>
  {strategy_block}
  <div class="card">
    <h3>Orchestrator highlights</h3>
    <div class="highlights-grid">
      {highlights_html}
    </div>
  </div>
  {equilibrium_block}
</section>
"""

    def _render_equilibrium_block(self, equilibrium_result: EquilibriumResult | None) -> str:
        if equilibrium_result is None:
            return ""
        player_names = {
            player.player_id: player.display_name
            for player in equilibrium_result.game.players
        }
        regret_rows = "".join(
            f"<tr><td>{escape(player_names.get(player_id, player_id))}</td><td class=\"mono\">{value:.4f}</td></tr>"
            for player_id, value in equilibrium_result.mean_external_regret.items()
        )
        coalition_rows = "".join(
            f"<tr><td>{escape(block)}</td><td class=\"mono\">{value:.4f}</td></tr>"
            for block, value in equilibrium_result.mean_coalition_regret.items()
        )
        recommended_rows = "".join(
            f"<li><strong>{escape(player_names.get(player_id, player_id))}</strong>: {escape(self._titleize_action(action_name))}</li>"
            for player_id, action_name in equilibrium_result.recommended_profile.items()
        )
        welfare = equilibrium_result.welfare
        welfare_html = ""
        if welfare is not None:
            welfare_bits = [
                f"alpha={equilibrium_result.trust_alpha:.2f}",
                f"trust-weighted={welfare.trust_weighted_sw:+.3f}",
                f"utilitarian={welfare.utilitarian_sw:+.3f}",
                f"Gini={welfare.payoff_gini:.4f}",
            ]
            if welfare.positive_normative_kl is not None:
                welfare_bits.append(f"KL gap={welfare.positive_normative_kl:.6f}")
            if equilibrium_result.price_of_anarchy is not None:
                welfare_bits.append(f"PoA={equilibrium_result.price_of_anarchy:.4f}")
            welfare_html = (
                '<div class="reading-box"><strong>Welfare diagnostics.</strong> '
                + ", ".join(welfare_bits)
                + ".</div>"
            )
        warning_html = ""
        if equilibrium_result.warnings:
            warning_html = (
                '<div class="reading-box" style="margin-top:12px;"><strong>Warnings.</strong> '
                + " ".join(escape(warning) for warning in equilibrium_result.warnings)
                + "</div>"
            )
        return f"""
<div class="card" style="margin-top:22px;">
  <h3>Equilibrium diagnostics</h3>
  <div class="reading-box"><strong>Status.</strong> Episodes={equilibrium_result.episodes}, converged={'yes' if equilibrium_result.converged else 'no'}, solver={escape(equilibrium_result.correlated_equilibrium.solver_status)}, max deviation={equilibrium_result.correlated_equilibrium.max_incentive_deviation:.6f}.</div>
  <div class="reading-box" style="margin-top:12px;"><strong>Normative CE.</strong> {escape(equilibrium_result.correlated_equilibrium.objective_description)}</div>
  {warning_html}
  <div class="two-col" style="margin-top:16px;">
    <div>
      <h3 style="margin-top:0;">Mean external regret</h3>
      <table class="strategy-table"><tbody>{regret_rows}</tbody></table>
      {'<h3 style="margin-top:14px;">Coalition regret</h3><table class="strategy-table"><tbody>' + coalition_rows + '</tbody></table>' if coalition_rows else ''}
    </div>
    <div>
      <h3 style="margin-top:0;">Recommended profile</h3>
      <ul>{recommended_rows}</ul>
    </div>
  </div>
  {welfare_html}
</div>
"""

    def _render_brief_section(self, brief_markdown: str) -> str:
        body = brief_markdown.strip()
        if body.startswith("# "):
            body = "\n".join(body.splitlines()[1:]).lstrip()
        return f"""
<section class="section">
  <div class="section-header">
    <h2 class="section-title">Decision Brief</h2>
    <div class="section-note">Narrative briefing rendered from the same run context as the dashboard</div>
  </div>
  <div class="card">
    <div class="brief-markdown">
      {self._markdown_to_html(body)}
    </div>
  </div>
</section>
"""

    def _render_narrative(
        self,
        *,
        evaluation: ScenarioEvaluation,
        initial_evaluation: ScenarioEvaluation | None,
        highlight_cards: list[dict[str, str]],
    ) -> str:
        opening = (
            f"The terminal scenario remains dominated by {RISK_LABELS.get(evaluation.dominant_outcomes[0], evaluation.dominant_outcomes[0]).lower()} "
            f"at {100.0 * evaluation.risk_probabilities[evaluation.dominant_outcomes[0]]:.1f}%."
        )
        if initial_evaluation is not None:
            delta = evaluation.criticality_score - initial_evaluation.criticality_score
            opening += f" Criticality moved by {delta:+.2f} over the observed horizon."
        summary = " ".join(card["body"] for card in highlight_cards[:3])
        return f"""
<section class="section">
  <div class="section-header">
    <h2 class="section-title">Narrative Brief</h2>
    <div class="section-note">Deterministic summary assembled from dashboard signals</div>
  </div>
  <div class="narrative">{escape(opening + ' ' + summary)}</div>
</section>
"""

    def _initial_evaluation(
        self,
        *,
        initial_world: WorldState,
        scenario_def: ScenarioDefinition,
        game_result: GameResult | None,
    ) -> ScenarioEvaluation | None:
        if game_result is not None and game_result.baseline_evaluation is not None and game_result.baseline_trajectory:
            if len(game_result.baseline_trajectory) > 1:
                return GameRunner(initial_world).evaluate_scenario(scenario_def)
            return game_result.baseline_evaluation
        return GameRunner(initial_world).evaluate_scenario(scenario_def)

    def _resolve_actor_ids(
        self,
        world: WorldState,
        scenario_def: ScenarioDefinition,
        actor_filter: list[str] | None,
    ) -> list[str]:
        if actor_filter:
            selected = []
            for token in actor_filter:
                normalized = token.strip().lower()
                for agent_id, agent in world.agents.items():
                    if normalized in {agent_id.lower(), agent.name.lower()}:
                        selected.append(agent_id)
                        break
            if selected:
                return selected

        actor_ids = [agent_id for agent_id in scenario_def.actor_ids if agent_id in world.agents]
        if actor_ids:
            return actor_ids
        return list(evaluation_id for evaluation_id in world.agents.keys())[: min(5, len(world.agents))]

    def _timeline_years(self, base_year: int, length: int) -> list[int]:
        return [base_year + index for index in range(length)]

    def _extract_events(self, trajectory: list[WorldState]) -> dict[int, list[str]]:
        events: dict[int, list[str]] = {}
        for index in range(1, len(trajectory)):
            prev_state = trajectory[index - 1]
            current_state = trajectory[index]
            labels: list[str] = []
            debt_events = 0
            regime_events = 0
            climate_events = 0
            for actor_id in current_state.agents:
                if actor_id not in prev_state.agents:
                    continue
                prev_agent = prev_state.agents[actor_id]
                current_agent = current_state.agents[actor_id]
                prev_debt = self._safe_div(prev_agent.economy.public_debt, max(prev_agent.economy.gdp, 1e-9))
                current_debt = self._safe_div(current_agent.economy.public_debt, max(current_agent.economy.gdp, 1e-9))
                if prev_debt <= 1.0 < current_debt:
                    debt_events += 1
                if prev_agent.risk.regime_stability >= 0.35 > current_agent.risk.regime_stability:
                    regime_events += 1
                if (
                    current_agent.economy.climate_shock_years > prev_agent.economy.climate_shock_years
                    or current_agent.economy.climate_shock_penalty > prev_agent.economy.climate_shock_penalty + 1e-6
                ):
                    climate_events += 1
            if debt_events:
                labels.append(f"Debt stress events: {debt_events}")
            if regime_events:
                labels.append(f"Regime stress events: {regime_events}")
            if climate_events:
                labels.append(f"Climate events: {climate_events}")
            if labels:
                events[index] = labels
        return events

    def _scenario_summary(
        self,
        *,
        evaluation: ScenarioEvaluation,
        scenario_def: ScenarioDefinition,
        actor_names: list[str],
        horizon_years: int,
    ) -> str:
        if horizon_years > 0:
            horizon_label = f"over the next {horizon_years} years"
        else:
            horizon_label = f"over roughly the next {max(1, scenario_def.horizon_months // 12)} years"
        actor_label = self._actor_phrase(actor_names)
        top_outcome = evaluation.dominant_outcomes[0]
        second_outcome = evaluation.dominant_outcomes[1] if len(evaluation.dominant_outcomes) > 1 else top_outcome
        return (
            f"This run asks whether tensions involving {actor_label} {horizon_label} move the system toward "
            f"{RISK_LABELS.get(top_outcome, top_outcome).lower()} rather than "
            f"{RISK_LABELS.get(second_outcome, second_outcome).lower()}. "
            f"The current leading answer is {100.0 * evaluation.risk_probabilities.get(top_outcome, 0.0):.1f}% "
            f"for {RISK_LABELS.get(top_outcome, top_outcome).lower()}, meaning "
            f"{OUTCOME_EXPLANATIONS.get(top_outcome, '').lower()}"
        )

    def _actor_phrase(self, actor_names: list[str]) -> str:
        if not actor_names:
            return "the selected actors"
        if len(actor_names) == 1:
            return actor_names[0]
        if len(actor_names) == 2:
            return f"{actor_names[0]} and {actor_names[1]}"
        return ", ".join(actor_names[:-1]) + f", and {actor_names[-1]}"

    def _world_gdp(self, world: WorldState) -> float:
        return sum(agent.economy.gdp for agent in world.agents.values())

    def _global_debt_ratio(self, world: WorldState) -> float:
        total_debt = sum(agent.economy.public_debt for agent in world.agents.values())
        total_gdp = self._world_gdp(world)
        return self._safe_div(total_debt, total_gdp)

    def _global_social_tension(self, world: WorldState) -> float:
        total_population = sum(max(agent.economy.population, 0.0) for agent in world.agents.values())
        if total_population <= 1e-9:
            return 0.0
        weighted = sum(
            max(agent.economy.population, 0.0) * agent.society.social_tension
            for agent in world.agents.values()
        )
        return weighted / total_population

    def _build_highlights(
        self,
        *,
        evaluation: ScenarioEvaluation,
        initial_evaluation: ScenarioEvaluation | None,
        game_result: GameResult | None,
        trajectory: list[WorldState],
        scenario_def: ScenarioDefinition,
        actor_ids: list[str],
        climate_event_count: int,
    ) -> list[dict[str, str]]:
        highlights: list[dict[str, str]] = []
        initial_criticality = initial_evaluation.criticality_score if initial_evaluation is not None else evaluation.criticality_score
        delta_criticality = evaluation.criticality_score - initial_criticality
        top_outcome = evaluation.dominant_outcomes[0]

        if delta_criticality > 0.05:
            highlights.append(
                {
                    "kind": "k-up",
                    "title": "Escalation risk rising",
                    "body": (
                        f"{RISK_LABELS.get(top_outcome, top_outcome)} gained prominence over the horizon. "
                        f"Criticality moved from {initial_criticality:.2f} to {evaluation.criticality_score:.2f}, "
                        f"with strongest drivers in {', '.join(self._labelize(name) for name in list(evaluation.driver_scores)[:2])}."
                    ),
                }
            )

        if game_result is not None:
            best = game_result.best_combination
            best_delta = best.evaluation.criticality_score - game_result.baseline_evaluation.criticality_score
            top_negotiation = max(
                (profile.get("negotiation_capacity", 0.0) for profile in best.evaluation.actor_profiles.values()),
                default=0.0,
            )
            if best_delta < -0.03 and top_negotiation > 0.55:
                highlights.append(
                    {
                        "kind": "k-down",
                        "title": "Negotiation window exists",
                        "body": (
                            f"The top-ranked strategy reduces criticality by {best_delta:+.2f} against baseline. "
                            f"Negotiation capacity remains viable at {top_negotiation:.2f}, which keeps de-escalatory options open."
                        ),
                    }
                )

        terminal_world = trajectory[-1]
        worst_debt_actor = None
        worst_debt_ratio = 0.0
        for actor_id in actor_ids:
            if actor_id not in terminal_world.agents:
                continue
            agent = terminal_world.agents[actor_id]
            debt_ratio = self._safe_div(agent.economy.public_debt, max(agent.economy.gdp, 1e-9))
            if debt_ratio > worst_debt_ratio:
                worst_debt_ratio = debt_ratio
                worst_debt_actor = agent
        if worst_debt_actor is not None and worst_debt_ratio > 1.0:
            highlights.append(
                {
                    "kind": "k-flat",
                    "title": "Debt fragility",
                    "body": (
                        f"{worst_debt_actor.name} reaches debt/GDP {worst_debt_ratio:.2f}. "
                        f"That is consistent with elevated sovereign stress in the terminal dashboard."
                    ),
                }
            )

        terminal_global = evaluation.crisis_dashboard.global_context.metrics
        sanctions_metric = terminal_global.get("global_sanctions_footprint")
        if sanctions_metric is not None and sanctions_metric.level > 0.35:
            highlights.append(
                {
                    "kind": "k-up",
                    "title": "Sanctions footprint widening",
                    "body": (
                        f"Global sanctions footprint ends at level {sanctions_metric.level:.2f}, "
                        f"which raises system-wide trade fragmentation and rerouting pressure."
                    ),
                }
            )

        if climate_event_count == 0:
            highlights.append(
                {
                    "kind": "k-down",
                    "title": "Climate feedback minor",
                    "body": (
                        f"No climate shock events were detected across {max(len(trajectory) - 1, 0)} simulated yearly steps. "
                        f"Climate risk remained secondary to geopolitical and fiscal drivers."
                    ),
                }
            )

        if not highlights:
            top_driver_names = sorted(
                evaluation.driver_scores,
                key=evaluation.driver_scores.get,
                reverse=True,
            )[:3]
            highlights.append(
                {
                    "kind": "k-flat",
                    "title": "Primary stress pattern",
                    "body": (
                        f"The scenario is still driven mainly by {', '.join(self._labelize(name) for name in top_driver_names)}."
                    ),
                }
            )

        return highlights[:5]

    def _render_gauge(self, value: float) -> str:
        clamped = max(0.0, min(1.0, value))
        color = "#2f855a" if clamped < 0.3 else "#b7791f" if clamped < 0.6 else "#9b2c2c"
        dash = 100.0 * clamped
        return f"""
<div class="gauge-wrap">
  <svg width="280" height="182" viewBox="0 0 240 170" role="img" aria-label="Criticality gauge">
    <path d="M 35 122 A 85 85 0 0 1 205 122" pathLength="100" fill="none" stroke="#eadfcb" stroke-width="18" stroke-linecap="round"></path>
    <path d="M 35 122 A 85 85 0 0 1 205 122" pathLength="100" fill="none" stroke="{color}" stroke-width="18" stroke-linecap="round" stroke-dasharray="{dash:.1f} 100"></path>
    <text x="120" y="94" text-anchor="middle" font-size="14" fill="#6b665d">criticality</text>
    <text x="120" y="124" text-anchor="middle" font-size="38" font-weight="800" fill="#1d1b18">{clamped:.2f}</text>
    <text x="35" y="150" text-anchor="middle" font-size="12" fill="#6b665d">0.0</text>
    <text x="120" y="150" text-anchor="middle" font-size="12" fill="#6b665d">0.5</text>
    <text x="205" y="150" text-anchor="middle" font-size="12" fill="#6b665d">1.0</text>
  </svg>
  <div class="gauge-caption">0.0-0.3 green, 0.3-0.6 amber, 0.6-1.0 red</div>
</div>"""

    def _render_line_chart_card(
        self,
        *,
        title: str,
        note: str,
        years: list[int],
        series: dict[str, list[float]],
        markers: dict[int, list[str]],
        min_override: float | None = None,
        max_override: float | None = None,
        value_formatter=None,
    ) -> str:
        svg = self._svg_line_chart(
            years=years,
            series=series,
            markers=markers,
            min_override=min_override,
            max_override=max_override,
        )
        legend = self._legend_html(series.keys())
        event_strip = self._event_strip_html(years, markers)
        return f"""
<div class="chart-card">
  <div class="chart-title">{escape(title)}</div>
  <div class="chart-note">{escape(note)}</div>
  {svg}
  {legend}
  {event_strip}
</div>"""

    def _render_dual_axis_chart_card(
        self,
        *,
        title: str,
        note: str,
        years: list[int],
        left_series: dict[str, list[float]],
        right_series: dict[str, list[float]],
        markers: dict[int, list[str]],
    ) -> str:
        svg = self._svg_dual_axis_chart(
            years=years,
            left_series=left_series,
            right_series=right_series,
            markers=markers,
        )
        legend = self._legend_html(tuple(left_series.keys()) + tuple(right_series.keys()))
        event_strip = self._event_strip_html(years, markers)
        return f"""
<div class="chart-card">
  <div class="chart-title">{escape(title)}</div>
  <div class="chart-note">{escape(note)}</div>
  {svg}
  {legend}
  {event_strip}
</div>"""

    def _svg_line_chart(
        self,
        *,
        years: list[int],
        series: dict[str, list[float]],
        markers: dict[int, list[str]],
        min_override: float | None = None,
        max_override: float | None = None,
    ) -> str:
        width = 620
        height = 250
        left = 66
        right = 22
        top = 18
        bottom = 42
        plot_width = width - left - right
        plot_height = height - top - bottom

        values = [value for seq in series.values() for value in seq]
        y_min = min(values) if values else 0.0
        y_max = max(values) if values else 1.0
        if min_override is not None:
            y_min = min_override
        if max_override is not None:
            y_max = max_override
        if math.isclose(y_min, y_max):
            y_max = y_min + 1.0

        def x_pos(index: int) -> float:
            if len(years) <= 1:
                return left + plot_width / 2.0
            return left + plot_width * index / (len(years) - 1)

        def y_pos(value: float) -> float:
            return top + plot_height * (1.0 - ((value - y_min) / max(y_max - y_min, 1e-9)))

        grid = []
        for fraction in (0.0, 0.5, 1.0):
            y = top + plot_height * fraction
            label = y_max - fraction * (y_max - y_min)
            grid.append(
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e7dfd1" stroke-width="1" />'
            )
            grid.append(
                f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#6b665d" style="paint-order:stroke;stroke:#fffdfa;stroke-width:4px;">{label:.2f}</text>'
            )

        marker_lines = []
        for index, labels in markers.items():
            x = x_pos(index)
            marker_lines.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#b7791f" stroke-width="1.5" stroke-dasharray="5 4" />'
            )

        paths = []
        for idx, (label, seq) in enumerate(series.items()):
            color = SERIES_COLORS[idx % len(SERIES_COLORS)]
            points = " ".join(f"{x_pos(index):.1f},{y_pos(value):.1f}" for index, value in enumerate(seq))
            paths.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" points="{points}" />'
            )

        year_labels = []
        for index, year in enumerate(years):
            x = x_pos(index)
            year_labels.append(
                f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" font-size="11" fill="#6b665d" style="paint-order:stroke;stroke:#fffdfa;stroke-width:4px;">{year}</text>'
            )

        return f"""
<svg width="100%" viewBox="0 0 {width} {height}" role="img" aria-label="trajectory chart">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fffdfa" rx="14"></rect>
  {''.join(grid)}
  {''.join(marker_lines)}
  {''.join(paths)}
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#beb5a4" stroke-width="1.2" />
  {''.join(year_labels)}
</svg>"""

    def _svg_dual_axis_chart(
        self,
        *,
        years: list[int],
        left_series: dict[str, list[float]],
        right_series: dict[str, list[float]],
        markers: dict[int, list[str]],
    ) -> str:
        width = 620
        height = 250
        left = 66
        right = 66
        top = 18
        bottom = 42
        plot_width = width - left - right
        plot_height = height - top - bottom

        left_values = [value for seq in left_series.values() for value in seq] or [0.0, 1.0]
        right_values = [value for seq in right_series.values() for value in seq] or [0.0, 1.0]
        left_min = min(left_values)
        left_max = max(left_values)
        right_min = min(right_values)
        right_max = max(right_values)
        if math.isclose(left_min, left_max):
            left_max = left_min + 1.0
        if math.isclose(right_min, right_max):
            right_max = right_min + 1.0

        def x_pos(index: int) -> float:
            if len(years) <= 1:
                return left + plot_width / 2.0
            return left + plot_width * index / (len(years) - 1)

        def left_y(value: float) -> float:
            return top + plot_height * (1.0 - ((value - left_min) / max(left_max - left_min, 1e-9)))

        def right_y(value: float) -> float:
            return top + plot_height * (1.0 - ((value - right_min) / max(right_max - right_min, 1e-9)))

        grid = []
        for fraction in (0.0, 0.5, 1.0):
            y = top + plot_height * fraction
            left_label = left_max - fraction * (left_max - left_min)
            right_label = right_max - fraction * (right_max - right_min)
            grid.append(
                f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e7dfd1" stroke-width="1" />'
            )
            grid.append(
                f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#6b665d" style="paint-order:stroke;stroke:#fffdfa;stroke-width:4px;">{left_label:.2f}</text>'
            )
            grid.append(
                f'<text x="{left + plot_width + 10}" y="{y + 4:.1f}" text-anchor="start" font-size="11" fill="#6b665d" style="paint-order:stroke;stroke:#fffdfa;stroke-width:4px;">{right_label:.2f}</text>'
            )

        marker_lines = []
        for index in markers:
            x = x_pos(index)
            marker_lines.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#b7791f" stroke-width="1.5" stroke-dasharray="5 4" />'
            )

        paths = []
        for idx, (_label, seq) in enumerate(left_series.items()):
            color = SERIES_COLORS[idx % len(SERIES_COLORS)]
            points = " ".join(f"{x_pos(index):.1f},{left_y(value):.1f}" for index, value in enumerate(seq))
            paths.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" points="{points}" />'
            )
        offset = len(left_series)
        for idx, (_label, seq) in enumerate(right_series.items()):
            color = SERIES_COLORS[(offset + idx) % len(SERIES_COLORS)]
            points = " ".join(f"{x_pos(index):.1f},{right_y(value):.1f}" for index, value in enumerate(seq))
            paths.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="7 5" points="{points}" />'
            )

        year_labels = []
        for index, year in enumerate(years):
            x = x_pos(index)
            year_labels.append(
                f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" font-size="11" fill="#6b665d" style="paint-order:stroke;stroke:#fffdfa;stroke-width:4px;">{year}</text>'
            )

        return f"""
<svg width="100%" viewBox="0 0 {width} {height}" role="img" aria-label="dual axis trajectory chart">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fffdfa" rx="14"></rect>
  {''.join(grid)}
  {''.join(marker_lines)}
  {''.join(paths)}
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#beb5a4" stroke-width="1.2" />
  {''.join(year_labels)}
</svg>"""

    def _legend_html(self, labels: Iterable[str]) -> str:
        labels = list(labels)
        if len(labels) <= 1:
            return ""
        items = []
        for index, label in enumerate(labels):
            color = SERIES_COLORS[index % len(SERIES_COLORS)]
            items.append(
                f'<span class="legend-item"><span class="legend-swatch" style="background:{color};"></span>{escape(label)}</span>'
            )
        return f'<div class="legend">{"".join(items)}</div>'

    def _render_glossary(self, keys: list[str]) -> str:
        items = []
        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            description = TERM_EXPLANATIONS.get(key)
            if not description:
                continue
            items.append(
                f'<div class="glossary-item"><strong>{escape(self._labelize(key))}</strong><span>{escape(description)}</span></div>'
            )
        if not items:
            return ""
        return f"""
<div class="card" style="margin-top:22px;">
  <h3>Model terms</h3>
  <div class="glossary-grid">
    {''.join(items)}
  </div>
</div>"""

    def _markdown_to_html(self, markdown_text: str) -> str:
        lines = markdown_text.splitlines()
        blocks: list[str] = []
        index = 0
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            if stripped.startswith("|"):
                table_lines = []
                while index < len(lines) and lines[index].strip().startswith("|"):
                    table_lines.append(lines[index].strip())
                    index += 1
                blocks.append(self._markdown_table_to_html(table_lines))
                continue
            if stripped.startswith("> "):
                quote_lines = []
                while index < len(lines) and lines[index].strip().startswith("> "):
                    quote_lines.append(lines[index].strip()[2:])
                    index += 1
                blocks.append(f"<blockquote>{self._markdown_inline(' '.join(quote_lines))}</blockquote>")
                continue
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                blocks.append(f"<h{level}>{self._markdown_inline(heading_match.group(2))}</h{level}>")
                index += 1
                continue
            if stripped.startswith("- "):
                items = []
                while index < len(lines) and lines[index].strip().startswith("- "):
                    items.append(f"<li>{self._markdown_inline(lines[index].strip()[2:])}</li>")
                    index += 1
                blocks.append(f"<ul>{''.join(items)}</ul>")
                continue
            paragraph_lines = [stripped]
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate or candidate.startswith(("|", "> ", "- ")) or re.match(r"^#{1,6}\s+", candidate):
                    break
                paragraph_lines.append(candidate)
                index += 1
            blocks.append(f"<p>{self._markdown_inline(' '.join(paragraph_lines))}</p>")
        return "".join(blocks)

    def _markdown_table_to_html(self, table_lines: list[str]) -> str:
        if len(table_lines) < 2:
            return ""
        rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in table_lines]
        header = rows[0]
        body_rows = rows[2:] if len(rows) > 2 else []
        thead = "<thead><tr>" + "".join(f"<th>{self._markdown_inline(cell)}</th>" for cell in header) + "</tr></thead>"
        tbody = "<tbody>" + "".join(
            "<tr>" + "".join(f"<td>{self._markdown_inline(cell)}</td>" for cell in row) + "</tr>"
            for row in body_rows
        ) + "</tbody>"
        return f"<table>{thead}{tbody}</table>"

    def _markdown_inline(self, text: str) -> str:
        escaped = escape(text)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        return escaped

    def _event_strip_html(self, years: list[int], markers: dict[int, list[str]]) -> str:
        if not markers:
            return ""
        pills = []
        for index, labels in sorted(markers.items()):
            year = years[index] if index < len(years) else index
            preview = ", ".join(labels[:2])
            pills.append(f'<span class="event-pill">{year}: {escape(preview)}</span>')
        return f'<div class="event-strip">{"".join(pills)}</div>'

    def _global_emissions(self, world: WorldState) -> float:
        return sum(agent.climate.co2_annual_emissions for agent in world.agents.values())

    def _labelize(self, value: str) -> str:
        return value.replace("_", " ").strip().title()

    def _term_html(self, term_key: str, label: str) -> str:
        description = TERM_EXPLANATIONS.get(term_key) or DRIVER_EXPLANATIONS.get(term_key)
        if not description:
            return escape(label)
        return (
            f'<span class="term" tabindex="0">{escape(label)}'
            f'<span class="term-tip">{escape(description)}</span></span>'
        )

    def _titleize_action(self, action_name: str) -> str:
        return action_name.replace("_", " ").strip().title()

    def _heat_color(self, severity: float) -> str:
        x = max(0.0, min(1.0, severity))
        red = int(226 * x + 233 * (1.0 - x))
        green = int(85 * (1.0 - x) + 238 * (1.0 - x) * 0.2)
        blue = int(74 * (1.0 - x) + 210 * (1.0 - x) * 0.2)
        return f"rgba({red}, {green}, {blue}, 0.22)"

    def _delta_heat(self, pct: float) -> str:
        if pct >= 0:
            alpha = min(abs(pct) / 12.0, 1.0)
            return f"rgba(47, 133, 90, {0.10 + 0.20 * alpha:.3f})"
        alpha = min(abs(pct) / 12.0, 1.0)
        return f"rgba(155, 44, 44, {0.10 + 0.20 * alpha:.3f})"

    def _arrow_entity(self, value: float) -> str:
        if value > 1e-6:
            return "&uarr;"
        if value < -1e-6:
            return "&darr;"
        return "&rarr;"

    def _severity_band(self, value: float) -> str:
        if value >= 0.66:
            return "HIGH"
        if value >= 0.33:
            return "MED"
        return "LOW"

    def _pct_change(self, start: float, end: float) -> float:
        if abs(start) <= 1e-9:
            return 0.0
        return 100.0 * (end / start - 1.0)

    def _safe_div(self, numerator: float, denominator: float) -> float:
        if abs(denominator) <= 1e-9:
            return 0.0
        return numerator / denominator


def write_dashboard_artifacts(
    *,
    renderer: DashboardRenderer,
    evaluation: ScenarioEvaluation,
    game_result: GameResult | None,
    equilibrium_result: EquilibriumResult | None,
    trajectory: list[WorldState] | None,
    scenario_def: ScenarioDefinition,
    config: DashboardConfig,
    save_json: bool = False,
) -> dict[str, str]:
    return renderer.write_dashboard_artifacts(
        evaluation=evaluation,
        game_result=game_result,
        equilibrium_result=equilibrium_result,
        trajectory=trajectory,
        scenario_def=scenario_def,
        config=config,
        save_json=save_json,
    )
