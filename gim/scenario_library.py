from .types import CalibrationGuardrails, ScenarioDefinition, ScenarioShock


_GENERAL_TAIL_RISK_TEMPLATE = {
    "title": "General tail-risk assessment",
    "narrative": (
        "A calibrated stress test that keeps the baseline world as the prior but leaves room "
        "for rare, high-impact states when multiple pressures compound."
    ),
    "risk_biases": {
        "status_quo": 0.10,
        "internal_destabilization": 0.15,
        "limited_proxy_escalation": 0.10,
        "negotiated_deescalation": 0.05,
    },
    "indicators": [
        "social_stress",
        "resource_gap",
        "conflict_stress",
        "debt_stress",
        "policy_space",
    ],
    "shocks": [],
}


TEMPLATE_REGISTRY = {
    "general_tail_risk": _GENERAL_TAIL_RISK_TEMPLATE,
    "generic_tail_risk": _GENERAL_TAIL_RISK_TEMPLATE,
    "sanctions_spiral": {
        "title": "Sanctions spiral",
        "narrative": (
            "Escalating sanctions pressure with second-round effects on trade access, social stress "
            "and strategic retaliation."
        ),
        "risk_biases": {
            "controlled_suppression": 0.20,
            "internal_destabilization": 0.45,
            "limited_proxy_escalation": 0.25,
            "negotiated_deescalation": 0.05,
        },
        "indicators": [
            "sanctions_pressure",
            "social_stress",
            "resource_gap",
            "trade_fragmentation",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "sanctions",
                "magnitude": 0.60,
                "cadence": "monthly",
                "rationale": "External financing and import access tighten over the horizon.",
            }
        ],
    },
    "alliance_fragmentation": {
        "title": "Alliance fragmentation",
        "narrative": (
            "A bloc-fracture scenario where trust erosion across several partner pairs weakens deterrence, "
            "coordination, and coalition cohesion."
        ),
        "risk_biases": {
            "broad_regional_escalation": 0.40,
            "limited_proxy_escalation": 0.22,
            "internal_destabilization": 0.12,
            "negotiated_deescalation": -0.05,
        },
        "indicators": [
            "conflict_stress",
            "negotiation_capacity",
            "policy_space",
            "social_stress",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "alliance",
                "magnitude": 0.55,
                "cadence": "monthly",
                "rationale": "Trust and burden-sharing frictions weaken bloc cohesion across multiple pairs.",
            }
        ],
    },
    "regional_pressure": {
        "title": "Regional pressure",
        "narrative": (
            "A regional theater where proxy escalation, coercive signaling and regime stress interact "
            "without assuming a binary war forecast."
        ),
        "risk_biases": {
            "limited_proxy_escalation": 0.55,
            "maritime_chokepoint_crisis": 0.35,
            "direct_strike_exchange": 0.30,
            "broad_regional_escalation": 0.15,
        },
        "indicators": [
            "conflict_stress",
            "military_posture",
            "energy_dependence",
            "social_stress",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "proxy",
                "magnitude": 0.55,
                "cadence": "weekly",
                "rationale": "Local non-state activity keeps the conflict ladder active.",
            }
        ],
    },
    "maritime_deterrence": {
        "title": "Maritime deterrence",
        "narrative": (
            "A chokepoint and route-security scenario where coercion can amplify into a regional crisis "
            "through energy and shipping dependencies."
        ),
        "risk_biases": {
            "maritime_chokepoint_crisis": 0.70,
            "direct_strike_exchange": 0.25,
            "broad_regional_escalation": 0.10,
            "negotiated_deescalation": 0.10,
        },
        "indicators": [
            "energy_dependence",
            "resource_gap",
            "conflict_stress",
            "negotiation_capacity",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "maritime",
                "magnitude": 0.70,
                "cadence": "weekly",
                "rationale": "Shipping disruptions and route insecurity raise shortage pressure.",
            }
        ],
    },
    "resource_competition": {
        "title": "Resource competition",
        "narrative": (
            "Competition over scarce food, metals, water and energy buffers amplifies domestic stress, "
            "trade friction and crisis spillovers."
        ),
        "risk_biases": {
            "social_unrest_without_military": 0.28,
            "internal_destabilization": 0.24,
            "sovereign_financial_crisis": 0.22,
            "maritime_chokepoint_crisis": 0.15,
        },
        "indicators": [
            "resource_gap",
            "energy_dependence",
            "climate_stress",
            "social_stress",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "resource",
                "magnitude": 0.60,
                "cadence": "monthly",
                "rationale": "Scarcity in critical resource channels raises price, reserve and import stress.",
            }
        ],
    },
    "tech_blockade": {
        "title": "Tech blockade",
        "narrative": (
            "A technology-containment scenario where export controls, chip constraints and innovation chokepoints "
            "propagate into macro and strategic rivalry channels."
        ),
        "risk_biases": {
            "internal_destabilization": 0.20,
            "sovereign_financial_crisis": 0.12,
            "limited_proxy_escalation": 0.10,
            "negotiated_deescalation": -0.04,
        },
        "indicators": [
            "sanctions_pressure",
            "policy_space",
            "negotiation_capacity",
            "social_stress",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "technology",
                "magnitude": 0.58,
                "cadence": "monthly",
                "rationale": "Technology export restrictions reduce diffusion, resilience and strategic flexibility.",
            }
        ],
    },
    "trade_war": {
        "title": "Trade war",
        "narrative": (
            "An economic confrontation centered on tariffs, export controls and sanctions-style pressure, "
            "with spillovers into domestic stability and strategic dependence."
        ),
        "risk_biases": {
            "internal_destabilization": 0.50,
            "limited_proxy_escalation": 0.15,
            "controlled_suppression": 0.10,
            "negotiated_deescalation": -0.05,
        },
        "indicators": [
            "sanctions_pressure",
            "resource_gap",
            "social_stress",
            "policy_space",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "sanctions",
                "magnitude": 0.55,
                "cadence": "monthly",
                "rationale": "Tariffs, export controls and retaliatory measures tighten trade access.",
            }
        ],
    },
    "cyber_disruption": {
        "title": "Cyber disruption",
        "narrative": (
            "A cyber confrontation where reconnaissance, infrastructure attacks and defensive hardening "
            "shape escalation risk without assuming immediate conventional war."
        ),
        "risk_biases": {
            "direct_strike_exchange": 0.30,
            "limited_proxy_escalation": 0.20,
            "internal_destabilization": 0.10,
            "broad_regional_escalation": 0.15,
        },
        "indicators": [
            "conflict_stress",
            "sanctions_pressure",
            "policy_space",
            "negotiation_capacity",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "cyber",
                "magnitude": 0.60,
                "cadence": "weekly",
                "rationale": "Persistent cyber pressure raises disruption risk and escalation miscalculation.",
            }
        ],
    },
    "regime_stress": {
        "title": "Regime stress",
        "narrative": (
            "A domestic instability scenario focused on protests, elite cohesion, repression capacity "
            "and the risk of spillover into international behavior."
        ),
        "risk_biases": {
            "controlled_suppression": 0.60,
            "internal_destabilization": 0.75,
            "negotiated_deescalation": -0.10,
        },
        "indicators": [
            "social_stress",
            "debt_stress",
            "policy_space",
            "negotiation_capacity",
            "tail_pressure",
        ],
        "shocks": [
            {
                "channel": "domestic",
                "magnitude": 0.65,
                "cadence": "monthly",
                "rationale": "Domestic unrest compounds with fiscal and legitimacy stress.",
            }
        ],
    },
}

TEMPLATE_KEYWORDS = {
    "alliance_fragmentation": ("alliance", "nato", "brics", "bloc", "coalition split", "fragmentation"),
    "sanctions_spiral": ("sanction", "embargo", "pressure campaign"),
    "resource_competition": ("rare earth", "critical minerals", "grain", "wheat", "water", "metals"),
    "tech_blockade": ("semiconductor", "chip", "chips act", "huawei", "lithography", "technology export", "export controls"),
    "trade_war": ("trade war", "tariff", "tariffs", "export control", "export controls"),
    "cyber_disruption": ("cyber", "hack", "hacking", "malware", "infrastructure attack"),
    "regional_pressure": ("iran", "proxy", "middle east", "gulf", "regional escalation"),
    "maritime_deterrence": ("maritime", "strait", "chokepoint", "shipping", "blockade", "ormuz"),
    "regime_stress": ("protest", "riot", "regime", "domestic crisis", "leadership shock"),
}


def detect_template(question: str) -> str:
    lowered = question.lower()
    best_template = "general_tail_risk"
    best_hits = 0
    for template_id, keywords in TEMPLATE_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits > best_hits:
            best_template = template_id
            best_hits = hits
    return best_template


def build_scenario_from_template(
    template_id: str,
    question: str,
    base_year: int,
    horizon_months: int,
    actor_ids: list[str],
    actor_names: list[str],
    unresolved_actor_names: list[str] | None = None,
    actor_resolution_method: str = "explicit_match",
    actor_resolution_confidence: float = 1.0,
    actor_resolution_notes: list[str] | None = None,
    assumptions: list[str] | None = None,
    display_year: int | None = None,
) -> ScenarioDefinition:
    template = TEMPLATE_REGISTRY.get(template_id, TEMPLATE_REGISTRY["general_tail_risk"])
    scenario_assumptions = [
        "The GIM15 calibration is the baseline prior for moderate outcomes.",
        "Critical states remain in the distribution when stress channels align in the same direction.",
        "Hard clipping is replaced by soft guardrails; impossible states remain forbidden.",
    ]
    if assumptions:
        scenario_assumptions.extend(assumptions)

    shocks = [
        ScenarioShock(
            channel=shock["channel"],
            magnitude=shock["magnitude"],
            cadence=shock["cadence"],
            rationale=shock["rationale"],
        )
        for shock in template["shocks"]
    ]

    return ScenarioDefinition(
        id=f"{template_id}-{base_year}",
        title=template["title"],
        template_id=template_id,
        source_prompt=question,
        base_year=base_year,
        display_year=display_year if display_year is not None else base_year,
        horizon_months=horizon_months,
        actor_ids=actor_ids,
        actor_names=actor_names,
        unresolved_actor_names=unresolved_actor_names or [],
        actor_resolution_method=actor_resolution_method,
        actor_resolution_confidence=float(actor_resolution_confidence),
        actor_resolution_notes=actor_resolution_notes or [],
        monitored_indicators=list(template["indicators"]),
        assumptions=scenario_assumptions,
        narrative=template["narrative"],
        shocks=shocks,
        risk_biases=dict(template["risk_biases"]),
        critical_focus=True,
        tags=[template_id, "tail-risk", "policy-gaming"],
        calibration_guardrails=CalibrationGuardrails(),
    )
