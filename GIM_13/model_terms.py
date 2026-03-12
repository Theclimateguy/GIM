from __future__ import annotations

from .crisis_metrics import AGENT_METRIC_DESCRIPTIONS, GLOBAL_METRIC_DESCRIPTIONS


DRIVER_EXPLANATIONS = {
    "debt_stress": "Debt rollover and fiscal-financing pressure. Higher values mean debt is harder to service without destabilizing growth or politics.",
    "social_stress": "Combined strain from social tension, weak trust in government and low regime stability.",
    "resource_gap": "Average shortage pressure across energy, food and metals. Higher values mean demand is harder to meet from current production.",
    "energy_dependence": "Dependence on imported energy or externally exposed supply routes.",
    "conflict_stress": "Composite escalation pressure from conflict proneness, hawkishness and military-security posture.",
    "sanctions_pressure": "Exposure to sanctions links, coercive trade restrictions and related balance-sheet stress.",
    "military_posture": "Current force and security posture. Higher values mean the actor is more able and more prepared to escalate.",
    "climate_stress": "Combined climate-risk and water-stress burden acting on the actor.",
    "policy_space": "Fiscal, political and institutional room to react to shocks without causing a broader domestic destabilization.",
    "negotiation_capacity": "Ability to absorb pressure through coalition-building, trust and regime stability rather than escalation.",
    "tail_pressure": "Aggregate pressure that pushes the system toward extreme outcomes rather than baseline states.",
    "multi_block_pressure": "Pressure created when scenario actors come from different alliance blocs, making coordination harder.",
    "actor_count_pressure": "Pressure created by having more actors involved in the scenario, which raises coordination and spillover risk.",
}


TERM_EXPLANATIONS = {
    **DRIVER_EXPLANATIONS,
    **AGENT_METRIC_DESCRIPTIONS,
    **GLOBAL_METRIC_DESCRIPTIONS,
    "gdp_delta_pct": "Percent change in GDP from the first simulated state to the terminal state.",
    "debt_gdp": "Public debt divided by GDP. Higher values indicate weaker fiscal resilience.",
    "social_tension": "Model score from 0 to 1 capturing domestic social strain and polarization pressure.",
    "climate_risk": "Model score from 0 to 1 capturing vulnerability to climate-related disruption.",
}
