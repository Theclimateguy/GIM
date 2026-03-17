from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Tuple


SOURCE_NOTES = {
    "nordhaus_2017": "Nordhaus (2017) DICE-2016R2, doi:10.1257/aer.20161007",
    "iacoviello_2022": "Caldara & Iacoviello (2022) GPR Index, AER doi:10.1257/aer.20191823",
    "boe_ml_2019": "Bluwstein et al. (2020) BoE ML crisis prediction, SSRN 3474600",
    "icews_base": "Boschee et al. (2015) ICEWS coded event data, Harvard Dataverse",
    "wdi_2023": "World Bank WDI 2023 panel and derived macro thresholds.",
    "expert_prior": "Expert prior carried over from the pre-calibration code path.",
}


@dataclass(frozen=True)
class GeoWeight:
    value: float
    ci95: Tuple[float, float]
    source: str


def _weight(value: float, half_width: float, source: str = "expert_prior") -> GeoWeight:
    return GeoWeight(value=value, ci95=(value - half_width, value + half_width), source=source)


def _prior(value: float, half_width: float = 0.08) -> GeoWeight:
    return _weight(value, half_width, "expert_prior")


def _cited(value: float, half_width: float, source: str) -> GeoWeight:
    return _weight(value, half_width, source)


# Base outcome model. Intercepts include any constant term created by expanding (1 - x)
# expressions from the legacy formulas so the refactor preserves identical outputs.
OUTCOME_INTERCEPTS: Dict[str, GeoWeight] = {
    "status_quo": _prior(1.20, 0.10),
    "controlled_suppression": _prior(0.05, 0.07),
    "internal_destabilization": _prior(-0.05, 0.07),
    "social_unrest_without_military": _prior(-0.12, 0.07),
    "sovereign_financial_crisis": _prior(-0.10, 0.07),
    "limited_proxy_escalation": _prior(0.00, 0.06),
    "maritime_chokepoint_crisis": _prior(-0.15, 0.07),
    "direct_strike_exchange": _prior(-0.10, 0.08),
    "broad_regional_escalation": _prior(-0.35, 0.10),
    "negotiated_deescalation": _prior(0.25, 0.08),
}

OUTCOME_DRIVERS: Dict[str, Dict[str, GeoWeight]] = {
    "status_quo": {
        "social_stress": _prior(-0.35, 0.08),
        "conflict_stress": _prior(-0.20, 0.07),
        "policy_space": _prior(0.25, 0.07),
        "resource_gap": _prior(-0.15, 0.06),
    },
    "controlled_suppression": {
        "social_stress": _prior(0.75, 0.10),
        "military_posture": _prior(0.35, 0.08),
        "negotiation_capacity": _prior(-0.20, 0.06),
    },
    "internal_destabilization": {
        "social_stress": _prior(0.95, 0.10),
        "debt_stress": _prior(0.45, 0.08),
        "resource_gap": _prior(0.35, 0.08),
        "policy_space": _prior(-0.20, 0.06),
    },
    "social_unrest_without_military": {
        "social_stress": _prior(0.90, 0.10),
        "resource_gap": _prior(0.30, 0.07),
        "debt_stress": _prior(0.25, 0.07),
        "conflict_stress": _prior(-0.20, 0.07),
    },
    "sovereign_financial_crisis": {
        "debt_stress": _prior(1.10, 0.11),
        "resource_gap": _prior(0.25, 0.07),
        "social_stress": _prior(0.20, 0.07),
        "policy_space": _prior(-0.15, 0.06),
    },
    "limited_proxy_escalation": {
        "conflict_stress": _prior(0.85, 0.10),
        "sanctions_pressure": _prior(0.25, 0.07),
        "actor_count_pressure": _prior(0.15, 0.06),
    },
    "maritime_chokepoint_crisis": {
        "energy_dependence": _prior(1.10, 0.10),
        "conflict_stress": _prior(0.40, 0.08),
        "resource_gap": _prior(0.25, 0.07),
    },
    "direct_strike_exchange": {
        "conflict_stress": _prior(0.90, 0.10),
        "military_posture": _prior(0.50, 0.08),
        "sanctions_pressure": _prior(0.20, 0.06),
    },
    "broad_regional_escalation": {
        "actor_count_pressure": _prior(0.30, 0.07),
        "multi_block_pressure": _prior(0.25, 0.07),
        "conflict_stress": _prior(0.35, 0.08),
    },
    "negotiated_deescalation": {
        "negotiation_capacity": _prior(0.80, 0.10),
        "conflict_stress": _prior(-0.15, 0.06),
        "tail_pressure": _prior(-0.20, 0.06),
    },
}

OUTCOME_LINK_SHIFTS: Dict[str, Dict[str, GeoWeight]] = {
    "broad_regional_escalation": {
        "direct_strike_exchange": _prior(0.30, 0.07),
        "limited_proxy_escalation": _prior(0.20, 0.06),
    }
}

TAIL_RISK_PARAMETERS: Dict[str, GeoWeight] = {
    "critical_pressure_threshold": _prior(1.25, 0.10),
    "critical_focus_bonus": _prior(0.18, 0.05),
    "critical_pressure_sensitivity": _prior(0.35, 0.08),
    "status_quo_penalty": _prior(0.10, 0.04),
}

ACTION_COUNT_SHIFTS: Dict[str, GeoWeight] = {
    "escalation_direct_strike": _prior(0.06, 0.03),
    "escalation_broad_regional": _prior(0.04, 0.03),
    "deescalation_negotiated": _prior(0.08, 0.03),
    "deescalation_broad_regional_relief": _prior(0.04, 0.03),
}

ACTION_RISK_SHIFTS: Dict[str, Dict[str, GeoWeight]] = {
    "signal_deterrence": {
        "direct_strike_exchange": _prior(0.15, 0.05),
        "broad_regional_escalation": _prior(0.05, 0.04),
        "negotiated_deescalation": _prior(-0.05, 0.04),
    },
    "signal_restraint": {
        "direct_strike_exchange": _prior(-0.20, 0.05),
        "broad_regional_escalation": _prior(-0.15, 0.05),
        "negotiated_deescalation": _prior(0.20, 0.05),
    },
    "arm_proxy": {
        "limited_proxy_escalation": _prior(0.40, 0.08),
        "broad_regional_escalation": _prior(0.15, 0.05),
    },
    "restrain_proxy": {
        "limited_proxy_escalation": _prior(-0.30, 0.07),
        "negotiated_deescalation": _prior(0.15, 0.05),
    },
    "covert_disruption": {
        "limited_proxy_escalation": _prior(0.20, 0.05),
        "maritime_chokepoint_crisis": _prior(0.10, 0.04),
        "negotiated_deescalation": _prior(-0.05, 0.04),
    },
    "maritime_interdiction": {
        "maritime_chokepoint_crisis": _prior(0.55, 0.09),
        "direct_strike_exchange": _prior(0.15, 0.05),
        "broad_regional_escalation": _prior(0.15, 0.05),
    },
    "partial_mobilization": {
        "direct_strike_exchange": _prior(0.35, 0.08),
        "broad_regional_escalation": _prior(0.15, 0.05),
    },
    "targeted_strike": {
        "direct_strike_exchange": _prior(0.60, 0.10),
        "broad_regional_escalation": _prior(0.30, 0.07),
        "negotiated_deescalation": _prior(-0.20, 0.05),
    },
    "backchannel_offer": {
        "direct_strike_exchange": _prior(-0.10, 0.04),
        "broad_regional_escalation": _prior(-0.10, 0.04),
        "negotiated_deescalation": _prior(0.30, 0.07),
    },
    "accept_mediation": {
        "direct_strike_exchange": _prior(-0.15, 0.05),
        "broad_regional_escalation": _prior(-0.15, 0.05),
        "negotiated_deescalation": _prior(0.40, 0.08),
    },
    "information_campaign": {
        "controlled_suppression": _prior(0.05, 0.04),
        "internal_destabilization": _prior(0.05, 0.04),
        "social_unrest_without_military": _prior(0.08, 0.04),
    },
    "domestic_crackdown": {
        "controlled_suppression": _prior(0.35, 0.08),
        "internal_destabilization": _prior(0.10, 0.04),
        "negotiated_deescalation": _prior(-0.05, 0.04),
    },
    "impose_tariffs": {
        "internal_destabilization": _prior(0.15, 0.05),
        "sovereign_financial_crisis": _prior(0.10, 0.04),
        "limited_proxy_escalation": _prior(0.10, 0.04),
        "negotiated_deescalation": _prior(-0.05, 0.04),
    },
    "export_controls": {
        "internal_destabilization": _prior(0.08, 0.04),
        "sovereign_financial_crisis": _prior(0.08, 0.04),
        "limited_proxy_escalation": _prior(0.08, 0.04),
        "negotiated_deescalation": _prior(-0.04, 0.03),
    },
    "lift_sanctions": {
        "internal_destabilization": _prior(-0.20, 0.05),
        "sovereign_financial_crisis": _prior(-0.15, 0.05),
        "social_unrest_without_military": _prior(-0.08, 0.04),
        "negotiated_deescalation": _prior(0.25, 0.06),
    },
    "currency_intervention": {
        "internal_destabilization": _prior(0.06, 0.04),
        "sovereign_financial_crisis": _prior(0.24, 0.06),
        "controlled_suppression": _prior(0.05, 0.04),
        "status_quo": _prior(-0.04, 0.03),
    },
    "debt_restructuring": {
        "internal_destabilization": _prior(0.06, 0.04),
        "sovereign_financial_crisis": _prior(0.28, 0.07),
        "status_quo": _prior(-0.05, 0.03),
    },
    "capital_controls": {
        "internal_destabilization": _prior(0.04, 0.03),
        "sovereign_financial_crisis": _prior(0.22, 0.06),
        "social_unrest_without_military": _prior(0.06, 0.04),
        "controlled_suppression": _prior(0.05, 0.04),
        "limited_proxy_escalation": _prior(0.05, 0.04),
    },
    "cyber_probe": {
        "limited_proxy_escalation": _prior(0.08, 0.04),
        "internal_destabilization": _prior(0.05, 0.04),
    },
    "cyber_disruption_attack": {
        "direct_strike_exchange": _prior(0.20, 0.05),
        "broad_regional_escalation": _prior(0.10, 0.04),
        "negotiated_deescalation": _prior(-0.08, 0.04),
    },
    "cyber_espionage": {
        "limited_proxy_escalation": _prior(0.04, 0.03),
        "controlled_suppression": _prior(0.05, 0.04),
    },
    "cyber_defense_posture": {
        "direct_strike_exchange": _prior(-0.05, 0.03),
        "negotiated_deescalation": _prior(0.05, 0.03),
    },
}

SHOCK_RISK_SHIFTS: Dict[str, Dict[str, GeoWeight]] = {
    "sanctions": {
        "internal_destabilization": _prior(0.22, 0.06),
        "sovereign_financial_crisis": _prior(0.18, 0.05),
        "limited_proxy_escalation": _prior(0.10, 0.04),
        "controlled_suppression": _prior(0.12, 0.04),
    },
    "proxy": {
        "limited_proxy_escalation": _prior(0.25, 0.06),
        "broad_regional_escalation": _prior(0.10, 0.04),
    },
    "maritime": {
        "maritime_chokepoint_crisis": _prior(0.35, 0.08),
        "broad_regional_escalation": _prior(0.08, 0.04),
    },
    "domestic": {
        "controlled_suppression": _prior(0.18, 0.05),
        "internal_destabilization": _prior(0.25, 0.06),
        "social_unrest_without_military": _prior(0.30, 0.07),
    },
    "cyber": {
        "direct_strike_exchange": _prior(0.20, 0.05),
        "limited_proxy_escalation": _prior(0.10, 0.04),
        "internal_destabilization": _prior(0.08, 0.04),
        "broad_regional_escalation": _prior(0.08, 0.04),
    },
}

ESCALATORY_ACTIONS = {
    "arm_proxy",
    "covert_disruption",
    "maritime_interdiction",
    "partial_mobilization",
    "targeted_strike",
    "impose_tariffs",
    "export_controls",
    "capital_controls",
    "cyber_probe",
    "cyber_disruption_attack",
    "cyber_espionage",
}

DEESCALATORY_ACTIONS = {
    "signal_restraint",
    "restrain_proxy",
    "backchannel_offer",
    "accept_mediation",
    "lift_sanctions",
    "cyber_defense_posture",
}

OBJECTIVE_TO_RISK_UTILITY: Dict[str, Dict[str, GeoWeight]] = {
    "regime_retention": {
        "status_quo": _prior(0.60, 0.08),
        "controlled_suppression": _prior(0.45, 0.08),
        "negotiated_deescalation": _prior(0.35, 0.08),
        "internal_destabilization": _prior(-1.00, 0.10),
        "social_unrest_without_military": _prior(-0.80, 0.10),
        "sovereign_financial_crisis": _prior(-0.65, 0.09),
        "broad_regional_escalation": _prior(-0.80, 0.10),
    },
    "reduce_war_risk": {
        "status_quo": _prior(0.35, 0.08),
        "negotiated_deescalation": _prior(1.00, 0.10),
        "limited_proxy_escalation": _prior(-0.55, 0.08),
        "maritime_chokepoint_crisis": _prior(-0.55, 0.08),
        "direct_strike_exchange": _prior(-0.90, 0.10),
        "broad_regional_escalation": _prior(-1.00, 0.10),
    },
    "regional_influence": {
        "status_quo": _prior(0.15, 0.05),
        "limited_proxy_escalation": _prior(0.40, 0.08),
        "direct_strike_exchange": _prior(0.10, 0.05),
        "negotiated_deescalation": _prior(0.25, 0.06),
        "broad_regional_escalation": _prior(-0.30, 0.07),
    },
    "sanctions_resilience": {
        "status_quo": _prior(0.50, 0.08),
        "negotiated_deescalation": _prior(0.70, 0.09),
        "internal_destabilization": _prior(-0.50, 0.08),
        "sovereign_financial_crisis": _prior(-0.70, 0.09),
        "social_unrest_without_military": _prior(-0.35, 0.07),
        "maritime_chokepoint_crisis": _prior(-0.35, 0.07),
        "direct_strike_exchange": _prior(-0.55, 0.08),
        "broad_regional_escalation": _prior(-0.80, 0.10),
    },
    "resource_access": {
        "status_quo": _prior(0.50, 0.08),
        "negotiated_deescalation": _prior(0.70, 0.09),
        "maritime_chokepoint_crisis": _prior(-1.00, 0.10),
        "broad_regional_escalation": _prior(-0.55, 0.08),
    },
    "bargaining_power": {
        "status_quo": _prior(0.10, 0.05),
        "limited_proxy_escalation": _prior(0.20, 0.06),
        "direct_strike_exchange": _prior(0.10, 0.05),
        "negotiated_deescalation": _prior(0.40, 0.08),
        "social_unrest_without_military": _prior(-0.25, 0.07),
        "sovereign_financial_crisis": _prior(-0.40, 0.08),
        "broad_regional_escalation": _prior(-0.20, 0.06),
    },
}

ACTION_OBJECTIVE_BONUS: Dict[str, Dict[str, GeoWeight]] = {
    "signal_deterrence": {
        "bargaining_power": _prior(0.12, 0.04),
        "regional_influence": _prior(0.08, 0.03),
    },
    "signal_restraint": {"reduce_war_risk": _prior(0.12, 0.04)},
    "arm_proxy": {"regional_influence": _prior(0.18, 0.05)},
    "restrain_proxy": {"reduce_war_risk": _prior(0.08, 0.03)},
    "maritime_interdiction": {"regional_influence": _prior(0.08, 0.03)},
    "backchannel_offer": {
        "reduce_war_risk": _prior(0.10, 0.04),
        "bargaining_power": _prior(0.06, 0.03),
    },
    "accept_mediation": {"reduce_war_risk": _prior(0.15, 0.05)},
    "domestic_crackdown": {"regime_retention": _prior(0.10, 0.04)},
    "impose_tariffs": {
        "bargaining_power": _prior(0.08, 0.03),
        "sanctions_resilience": _prior(0.04, 0.03),
    },
    "export_controls": {
        "bargaining_power": _prior(0.10, 0.04),
        "regional_influence": _prior(0.04, 0.03),
    },
    "lift_sanctions": {
        "reduce_war_risk": _prior(0.12, 0.04),
        "sanctions_resilience": _prior(0.12, 0.04),
        "resource_access": _prior(0.06, 0.03),
    },
    "currency_intervention": {
        "regime_retention": _prior(0.06, 0.03),
        "sanctions_resilience": _prior(0.08, 0.03),
    },
    "debt_restructuring": {
        "regime_retention": _prior(0.08, 0.03),
        "sanctions_resilience": _prior(0.12, 0.04),
    },
    "capital_controls": {
        "regime_retention": _prior(0.05, 0.03),
        "sanctions_resilience": _prior(0.08, 0.03),
    },
    "cyber_probe": {
        "bargaining_power": _prior(0.06, 0.03),
        "regional_influence": _prior(0.05, 0.03),
    },
    "cyber_disruption_attack": {
        "bargaining_power": _prior(0.10, 0.04),
        "regional_influence": _prior(0.08, 0.03),
    },
    "cyber_espionage": {
        "bargaining_power": _prior(0.08, 0.03),
        "resource_access": _prior(0.05, 0.03),
    },
    "cyber_defense_posture": {
        "reduce_war_risk": _prior(0.08, 0.03),
        "regime_retention": _prior(0.04, 0.03),
    },
}

ACTION_CRISIS_SHIFTS: Dict[str, Dict[str, Dict[str, GeoWeight]]] = {
    "signal_deterrence": {
        "self": {
            "conflict_escalation_pressure": _prior(0.08, 0.03),
            "sanctions_strangulation": _prior(0.03, 0.02),
        },
        "others": {"conflict_escalation_pressure": _prior(0.02, 0.02)},
        "global": {"global_oil_market_stress": _prior(0.01, 0.02)},
    },
    "signal_restraint": {
        "self": {
            "conflict_escalation_pressure": _prior(-0.08, 0.03),
            "sanctions_strangulation": _prior(-0.03, 0.02),
            "regime_fragility": _prior(-0.02, 0.02),
        },
        "others": {"conflict_escalation_pressure": _prior(-0.03, 0.02)},
        "global": {
            "global_trade_fragmentation": _prior(-0.02, 0.02),
            "global_oil_market_stress": _prior(-0.01, 0.02),
        },
    },
    "arm_proxy": {
        "self": {
            "conflict_escalation_pressure": _prior(0.12, 0.04),
            "sanctions_strangulation": _prior(0.05, 0.03),
            "regime_fragility": _prior(0.03, 0.02),
        },
        "others": {
            "conflict_escalation_pressure": _prior(0.05, 0.03),
            "oil_vulnerability": _prior(0.02, 0.02),
        },
        "global": {
            "global_oil_market_stress": _prior(0.03, 0.02),
            "global_sanctions_footprint": _prior(0.02, 0.02),
        },
    },
    "restrain_proxy": {
        "self": {
            "conflict_escalation_pressure": _prior(-0.06, 0.03),
            "regime_fragility": _prior(-0.02, 0.02),
        },
        "others": {"conflict_escalation_pressure": _prior(-0.04, 0.03)},
        "global": {"global_sanctions_footprint": _prior(-0.01, 0.02)},
    },
    "covert_disruption": {
        "self": {
            "sanctions_strangulation": _prior(0.04, 0.03),
            "conflict_escalation_pressure": _prior(0.08, 0.03),
        },
        "others": {
            "strategic_dependency": _prior(0.03, 0.02),
            "conflict_escalation_pressure": _prior(0.03, 0.02),
        },
        "global": {"global_trade_fragmentation": _prior(0.03, 0.02)},
    },
    "maritime_interdiction": {
        "self": {
            "conflict_escalation_pressure": _prior(0.12, 0.04),
            "sanctions_strangulation": _prior(0.06, 0.03),
        },
        "others": {
            "oil_vulnerability": _prior(0.10, 0.04),
            "chokepoint_exposure": _prior(0.12, 0.04),
            "inflation": _prior(0.04, 0.03),
        },
        "global": {
            "global_oil_market_stress": _prior(0.12, 0.04),
            "global_energy_volume_gap": _prior(0.10, 0.04),
            "global_trade_fragmentation": _prior(0.04, 0.03),
        },
    },
    "partial_mobilization": {
        "self": {
            "conflict_escalation_pressure": _prior(0.10, 0.04),
            "regime_fragility": _prior(0.03, 0.02),
            "sovereign_stress": _prior(0.02, 0.02),
        },
        "others": {"conflict_escalation_pressure": _prior(0.03, 0.02)},
        "global": {"global_oil_market_stress": _prior(0.02, 0.02)},
    },
    "targeted_strike": {
        "self": {
            "conflict_escalation_pressure": _prior(0.18, 0.05),
            "sanctions_strangulation": _prior(0.10, 0.04),
            "regime_fragility": _prior(0.05, 0.03),
        },
        "others": {
            "conflict_escalation_pressure": _prior(0.08, 0.03),
            "oil_vulnerability": _prior(0.04, 0.03),
            "chokepoint_exposure": _prior(0.05, 0.03),
        },
        "global": {
            "global_oil_market_stress": _prior(0.08, 0.03),
            "global_trade_fragmentation": _prior(0.06, 0.03),
            "global_sanctions_footprint": _prior(0.04, 0.03),
        },
    },
    "backchannel_offer": {
        "self": {
            "conflict_escalation_pressure": _prior(-0.07, 0.03),
            "sanctions_strangulation": _prior(-0.02, 0.02),
            "regime_fragility": _prior(-0.02, 0.02),
        },
        "others": {"conflict_escalation_pressure": _prior(-0.03, 0.02)},
        "global": {"global_trade_fragmentation": _prior(-0.02, 0.02)},
    },
    "accept_mediation": {
        "self": {
            "conflict_escalation_pressure": _prior(-0.10, 0.04),
            "sanctions_strangulation": _prior(-0.04, 0.03),
            "regime_fragility": _prior(-0.03, 0.02),
        },
        "others": {
            "conflict_escalation_pressure": _prior(-0.05, 0.03),
            "oil_vulnerability": _prior(-0.03, 0.02),
            "chokepoint_exposure": _prior(-0.03, 0.02),
        },
        "global": {
            "global_oil_market_stress": _prior(-0.04, 0.03),
            "global_trade_fragmentation": _prior(-0.03, 0.02),
            "global_sanctions_footprint": _prior(-0.02, 0.02),
        },
    },
    "information_campaign": {
        "self": {
            "regime_fragility": _prior(0.03, 0.02),
            "protest_pressure": _prior(0.02, 0.02),
        },
        "others": {
            "regime_fragility": _prior(0.02, 0.02),
            "protest_pressure": _prior(0.02, 0.02),
        },
        "global": {},
    },
    "domestic_crackdown": {
        "self": {
            "regime_fragility": _prior(0.08, 0.03),
            "protest_pressure": _prior(0.04, 0.03),
            "sanctions_strangulation": _prior(0.03, 0.02),
        },
        "others": {"sanctions_strangulation": _prior(0.01, 0.02)},
        "global": {"global_sanctions_footprint": _prior(0.01, 0.02)},
    },
    "impose_tariffs": {
        "self": {
            "inflation": _prior(0.03, 0.02),
            "sanctions_strangulation": _prior(0.02, 0.02),
        },
        "others": {
            "strategic_dependency": _prior(0.05, 0.03),
            "inflation": _prior(0.03, 0.02),
        },
        "global": {"global_trade_fragmentation": _prior(0.08, 0.03)},
    },
    "export_controls": {
        "self": {
            "sanctions_strangulation": _prior(0.04, 0.03),
            "strategic_dependency": _prior(0.08, 0.03),
        },
        "others": {
            "strategic_dependency": _prior(0.10, 0.04),
            "inflation": _prior(0.02, 0.02),
        },
        "global": {
            "global_trade_fragmentation": _prior(0.07, 0.03),
            "global_sanctions_footprint": _prior(0.03, 0.02),
        },
    },
    "lift_sanctions": {
        "self": {
            "sanctions_strangulation": _prior(-0.10, 0.04),
            "fx_stress": _prior(-0.05, 0.03),
            "regime_fragility": _prior(-0.02, 0.02),
        },
        "others": {
            "sanctions_strangulation": _prior(-0.06, 0.03),
            "strategic_dependency": _prior(-0.03, 0.02),
        },
        "global": {
            "global_trade_fragmentation": _prior(-0.06, 0.03),
            "global_sanctions_footprint": _prior(-0.08, 0.03),
        },
    },
    "currency_intervention": {
        "self": {
            "fx_stress": _prior(0.18, 0.05),
            "inflation": _prior(0.10, 0.04),
        },
        "others": {"inflation": _prior(0.01, 0.02)},
        "global": {},
    },
    "debt_restructuring": {
        "self": {
            "sovereign_stress": _prior(-0.25, 0.06),
            "regime_fragility": _prior(0.05, 0.03),
            "protest_pressure": _prior(0.03, 0.02),
        },
        "others": {},
        "global": {},
    },
    "capital_controls": {
        "self": {
            "sanctions_strangulation": _prior(0.12, 0.04),
            "fx_stress": _prior(0.15, 0.05),
            "strategic_dependency": _prior(0.04, 0.03),
        },
        "others": {"strategic_dependency": _prior(0.03, 0.02)},
        "global": {"global_trade_fragmentation": _prior(0.05, 0.03)},
    },
    "cyber_probe": {
        "self": {"conflict_escalation_pressure": _prior(0.03, 0.02)},
        "others": {
            "conflict_escalation_pressure": _prior(0.02, 0.02),
            "strategic_dependency": _prior(0.02, 0.02),
        },
        "global": {"global_trade_fragmentation": _prior(0.01, 0.02)},
    },
    "cyber_disruption_attack": {
        "self": {
            "conflict_escalation_pressure": _prior(0.12, 0.04),
            "sanctions_strangulation": _prior(0.04, 0.03),
        },
        "others": {
            "conflict_escalation_pressure": _prior(0.08, 0.03),
            "strategic_dependency": _prior(0.06, 0.03),
            "chokepoint_exposure": _prior(0.03, 0.02),
            "inflation": _prior(0.03, 0.02),
        },
        "global": {
            "global_trade_fragmentation": _prior(0.05, 0.03),
            "global_oil_market_stress": _prior(0.02, 0.02),
        },
    },
    "cyber_espionage": {
        "self": {"regime_fragility": _prior(0.01, 0.02)},
        "others": {
            "strategic_dependency": _prior(0.10, 0.04),
            "sanctions_strangulation": _prior(0.02, 0.02),
        },
        "global": {"global_trade_fragmentation": _prior(0.02, 0.02)},
    },
    "cyber_defense_posture": {
        "self": {
            "conflict_escalation_pressure": _prior(-0.05, 0.03),
            "strategic_dependency": _prior(-0.04, 0.03),
        },
        "others": {"conflict_escalation_pressure": _prior(-0.01, 0.02)},
        "global": {"global_trade_fragmentation": _prior(-0.01, 0.02)},
    },
}

OBJECTIVE_TO_CRISIS_UTILITY: Dict[str, Dict[str, GeoWeight]] = {
    "regime_retention": {
        "regime_fragility": _prior(-0.70, 0.09),
        "protest_pressure": _prior(-0.55, 0.08),
        "inflation": _prior(-0.20, 0.06),
        "sanctions_strangulation": _prior(-0.20, 0.06),
    },
    "reduce_war_risk": {
        "conflict_escalation_pressure": _prior(-0.80, 0.10),
        "chokepoint_exposure": _prior(-0.45, 0.08),
        "oil_vulnerability": _prior(-0.20, 0.06),
    },
    "regional_influence": {
        "regime_fragility": _prior(-0.25, 0.06),
        "conflict_escalation_pressure": _prior(-0.15, 0.05),
    },
    "sanctions_resilience": {
        "sanctions_strangulation": _prior(-0.85, 0.10),
        "fx_stress": _prior(-0.60, 0.09),
        "inflation": _prior(-0.25, 0.06),
        "sovereign_stress": _prior(-0.25, 0.06),
    },
    "resource_access": {
        "oil_vulnerability": _prior(-0.70, 0.09),
        "strategic_dependency": _prior(-0.55, 0.08),
        "chokepoint_exposure": _prior(-0.70, 0.09),
        "food_affordability_stress": _prior(-0.25, 0.06),
    },
    "bargaining_power": {
        "regime_fragility": _prior(-0.30, 0.07),
        "sanctions_strangulation": _prior(-0.25, 0.06),
    },
}

OBJECTIVE_TO_GLOBAL_CRISIS_UTILITY: Dict[str, Dict[str, GeoWeight]] = {
    "regime_retention": {
        "stability_stress_shift": _prior(-0.25, 0.06),
        "net_crisis_shift": _prior(-0.15, 0.05),
    },
    "reduce_war_risk": {
        "geopolitical_stress_shift": _prior(-0.55, 0.08),
        "net_crisis_shift": _prior(-0.20, 0.06),
    },
    "regional_influence": {"net_crisis_shift": _prior(-0.08, 0.04)},
    "sanctions_resilience": {
        "macro_stress_shift": _prior(-0.25, 0.06),
        "geopolitical_stress_shift": _prior(-0.15, 0.05),
    },
    "resource_access": {
        "macro_stress_shift": _prior(-0.30, 0.07),
        "geopolitical_stress_shift": _prior(-0.30, 0.07),
    },
    "bargaining_power": {"net_crisis_shift": _prior(-0.10, 0.04)},
}

PROFILE_WEIGHTS: Dict[str, GeoWeight] = {
    "debt_ratio_floor": _prior(0.25, 0.05),
    "social_tension_weight": _prior(0.45, 0.08),
    "social_distrust_weight": _prior(0.25, 0.07),
    "social_instability_weight": _prior(0.30, 0.07),
    "conflict_proneness_weight": _prior(0.30, 0.07),
    "hawkishness_weight": _prior(0.25, 0.06),
    "military_surplus_weight": _prior(0.20, 0.06),
    "military_surplus_threshold": _prior(0.75, 0.08),
    "security_gap_weight": _prior(0.15, 0.05),
    "coalition_gap_weight": _prior(0.10, 0.04),
    "sanctions_link_weight": _prior(0.18, 0.05),
    "sanctions_debt_overhang_threshold": _prior(0.50, 0.08),
    "military_posture_military_weight": _prior(0.55, 0.08),
    "military_posture_security_weight": _prior(0.45, 0.08),
    "climate_risk_weight": _prior(0.60, 0.08),
    "water_stress_weight": _prior(0.40, 0.08),
    "negotiation_coalition_weight": _prior(0.40, 0.08),
    "negotiation_trust_weight": _prior(0.30, 0.07),
    "negotiation_stability_weight": _prior(0.30, 0.07),
    "tail_debt_weight": _prior(0.40, 0.08),
    "tail_climate_weight": _prior(0.20, 0.06),
    "multi_block_divisor": _prior(3.0, 0.5),
    "actor_count_divisor": _prior(3.0, 0.5),
}

ARCHETYPE_THRESHOLDS: Dict[str, GeoWeight] = {
    "hydrocarbon_exporter_energy_export_min": _prior(0.15, 0.04),
    "fragile_conflict_proneness_min": _prior(0.75, 0.08),
    "fragile_regime_stability_max": _prior(0.40, 0.08),
    "industrial_gdp_large_min": _prior(10.0, 1.0),
    "industrial_gdp_mid_min": _prior(4.0, 0.5),
    "industrial_population_min": _cited(150_000_000.0, 20_000_000.0, "wdi_2023"),
    "advanced_democracy_gdp_pc_min": _cited(35_000.0, 5_000.0, "wdi_2023"),
    "developing_importer_energy_gap_min": _prior(0.10, 0.04),
    "developing_importer_fx_gdp_max": _prior(0.15, 0.05),
    "default_avg_trust": _prior(0.50, 0.08),
}

ARCHETYPE_RELEVANCE: Dict[str, Dict[str, GeoWeight]] = {
    "advanced_service_democracy": {
        "inflation": _prior(0.80, 0.08),
        "oil_vulnerability": _prior(0.35, 0.07),
        "fx_stress": _prior(0.30, 0.07),
        "sovereign_stress": _prior(0.85, 0.08),
        "food_affordability_stress": _prior(0.20, 0.06),
        "protest_pressure": _prior(0.60, 0.08),
        "regime_fragility": _prior(0.45, 0.08),
        "sanctions_strangulation": _prior(0.60, 0.08),
        "conflict_escalation_pressure": _prior(0.60, 0.08),
        "strategic_dependency": _prior(0.75, 0.08),
        "chokepoint_exposure": _prior(0.50, 0.08),
    },
    "developing_importer": {
        "inflation": _prior(0.90, 0.08),
        "oil_vulnerability": _prior(0.90, 0.08),
        "fx_stress": _prior(0.95, 0.08),
        "sovereign_stress": _prior(0.80, 0.08),
        "food_affordability_stress": _prior(0.95, 0.08),
        "protest_pressure": _prior(0.90, 0.08),
        "regime_fragility": _prior(0.80, 0.08),
        "sanctions_strangulation": _prior(0.65, 0.08),
        "conflict_escalation_pressure": _prior(0.55, 0.08),
        "strategic_dependency": _prior(0.85, 0.08),
        "chokepoint_exposure": _prior(0.80, 0.08),
    },
    "hydrocarbon_exporter": {
        "inflation": _prior(0.70, 0.08),
        "oil_vulnerability": _prior(0.95, 0.08),
        "fx_stress": _prior(0.55, 0.08),
        "sovereign_stress": _prior(0.60, 0.08),
        "food_affordability_stress": _prior(0.55, 0.08),
        "protest_pressure": _prior(0.75, 0.08),
        "regime_fragility": _prior(0.85, 0.08),
        "sanctions_strangulation": _prior(0.90, 0.08),
        "conflict_escalation_pressure": _prior(0.85, 0.08),
        "strategic_dependency": _prior(0.70, 0.08),
        "chokepoint_exposure": _prior(0.95, 0.08),
    },
    "industrial_power": {
        "inflation": _prior(0.75, 0.08),
        "oil_vulnerability": _prior(0.55, 0.08),
        "fx_stress": _prior(0.40, 0.08),
        "sovereign_stress": _prior(0.70, 0.08),
        "food_affordability_stress": _prior(0.30, 0.07),
        "protest_pressure": _prior(0.55, 0.08),
        "regime_fragility": _prior(0.55, 0.08),
        "sanctions_strangulation": _prior(0.90, 0.08),
        "conflict_escalation_pressure": _prior(0.85, 0.08),
        "strategic_dependency": _prior(0.90, 0.08),
        "chokepoint_exposure": _prior(0.75, 0.08),
    },
    "fragile_conflict_state": {
        "inflation": _prior(0.80, 0.08),
        "oil_vulnerability": _prior(0.70, 0.08),
        "fx_stress": _prior(0.85, 0.08),
        "sovereign_stress": _prior(0.90, 0.08),
        "food_affordability_stress": _prior(1.00, 0.08),
        "protest_pressure": _prior(1.00, 0.08),
        "regime_fragility": _prior(1.00, 0.08),
        "sanctions_strangulation": _prior(0.80, 0.08),
        "conflict_escalation_pressure": _prior(0.95, 0.08),
        "strategic_dependency": _prior(0.90, 0.08),
        "chokepoint_exposure": _prior(0.65, 0.08),
    },
    "mixed_emerging": {
        "inflation": _prior(0.80, 0.08),
        "oil_vulnerability": _prior(0.70, 0.08),
        "fx_stress": _prior(0.70, 0.08),
        "sovereign_stress": _prior(0.75, 0.08),
        "food_affordability_stress": _prior(0.60, 0.08),
        "protest_pressure": _prior(0.75, 0.08),
        "regime_fragility": _prior(0.70, 0.08),
        "sanctions_strangulation": _prior(0.65, 0.08),
        "conflict_escalation_pressure": _prior(0.65, 0.08),
        "strategic_dependency": _prior(0.75, 0.08),
        "chokepoint_exposure": _prior(0.65, 0.08),
    },
}

REGIONAL_ROUTE_RISK: Dict[str, GeoWeight] = {
    "Middle East": _prior(0.85, 0.08),
    "East Asia": _prior(0.70, 0.08),
    "Europe": _prior(0.45, 0.08),
    "North America": _prior(0.25, 0.06),
    "Global South": _prior(0.50, 0.08),
    "__default__": _prior(0.40, 0.08),
}

CRISIS_METRIC_WEIGHTS: Dict[str, GeoWeight] = {
    "severity_level_weight": _prior(0.45, 0.08),
    "severity_momentum_weight": _prior(0.20, 0.06),
    "severity_buffer_weight": _prior(0.20, 0.06),
    "severity_trigger_weight": _prior(0.15, 0.05),
    "global_oil_energy_gap_weight": _prior(0.65, 0.08),
    "global_oil_sanctions_weight": _prior(0.20, 0.06),
    "global_oil_conflict_weight": _prior(0.15, 0.05),
    "global_oil_normalize_low": _prior(1.0, 0.2),
    "global_oil_normalize_high": _prior(2.5, 0.3),
    "global_oil_buffer_gap_ref": _prior(0.25, 0.06),
    "global_oil_trigger_threshold": _prior(0.55, 0.08),
    "global_energy_gap_normalize_high": _prior(0.20, 0.05),
    "global_energy_gap_trigger_threshold": _prior(0.50, 0.08),
    "global_energy_gap_flag": _prior(0.10, 0.04),
    "global_sanctions_normalize_high": _prior(0.15, 0.04),
    "global_sanctions_trigger_threshold": _prior(0.40, 0.07),
    "global_sanctions_flag": _prior(0.06, 0.03),
    "global_trade_fragmentation_normalize_high": _prior(0.70, 0.08),
    "global_trade_fragmentation_trigger_threshold": _prior(0.45, 0.07),
    "global_trade_fragmentation_flag": _prior(0.25, 0.06),
    "baseline_gdp_pc_default": _cited(20_000.0, 3_000.0, "wdi_2023"),
    "import_dependency_energy_weight": _prior(0.50, 0.08),
    "import_dependency_food_weight": _prior(0.30, 0.07),
    "import_dependency_metals_weight": _prior(0.20, 0.06),
    "sanctions_scale_denominator": _prior(4.0, 0.5),
    "inflation_energy_price_weight": _prior(0.07, 0.03),
    "inflation_energy_gap_base": _prior(0.40, 0.08),
    "inflation_energy_gap_weight": _prior(0.60, 0.08),
    "inflation_food_price_weight": _prior(0.05, 0.03),
    "inflation_food_gap_base": _prior(0.30, 0.07),
    "inflation_food_gap_weight": _prior(0.70, 0.08),
    "inflation_metals_price_weight": _prior(0.03, 0.02),
    "inflation_metals_gap_base": _prior(0.20, 0.06),
    "inflation_metals_gap_weight": _prior(0.80, 0.08),
    "inflation_sanctions_weight": _prior(0.04, 0.02),
    "inflation_trade_barrier_weight": _prior(0.03, 0.02),
    "inflation_normalize_low": _prior(0.02, 0.01),
    "inflation_normalize_high": _prior(0.15, 0.03),
    "inflation_trigger_threshold": _prior(0.55, 0.08),
    "import_bill_base_share": _prior(0.08, 0.03),
    "import_bill_dependency_weight": _prior(0.24, 0.06),
    "import_bill_trade_weight": _prior(0.10, 0.04),
    "months_per_year": _prior(12.0, 1.0),
    "fx_cover_months_ref": _prior(6.0, 1.0),
    "fx_trigger_months_ref": _prior(3.0, 0.7),
    "sovereign_debt_weight": _prior(0.35, 0.08),
    "sovereign_rate_weight": _prior(0.25, 0.07),
    "sovereign_interest_revenue_weight": _prior(0.20, 0.06),
    "sovereign_fx_weight": _prior(0.20, 0.06),
    "sovereign_debt_low": _prior(0.60, 0.08),
    "sovereign_debt_high": _prior(1.40, 0.10),
    "sovereign_rate_low": _prior(0.03, 0.02),
    "sovereign_rate_high": _prior(0.15, 0.03),
    "sovereign_interest_revenue_low": _prior(0.10, 0.03),
    "sovereign_interest_revenue_high": _prior(0.40, 0.06),
    "sovereign_buffer_fx_weight": _prior(0.50, 0.08),
    "sovereign_buffer_debt_weight": _prior(0.50, 0.08),
    "sovereign_trigger_debt_weight": _prior(0.60, 0.08),
    "sovereign_trigger_rate_weight": _prior(0.40, 0.08),
    "sovereign_trigger_debt_threshold": _prior(1.20, 0.10),
    "sovereign_trigger_debt_ref": _prior(0.40, 0.06),
    "sovereign_trigger_rate_threshold": _prior(0.12, 0.03),
    "sovereign_trigger_rate_ref": _prior(0.08, 0.03),
    "income_buffer_ref_multiplier": _prior(1.50, 0.15),
    "basket_food_weight": _prior(0.60, 0.08),
    "basket_energy_weight": _prior(0.25, 0.06),
    "basket_metals_weight": _prior(0.15, 0.05),
    "food_gap_weight": _prior(0.45, 0.08),
    "food_basket_weight": _prior(0.25, 0.07),
    "food_inflation_weight": _prior(0.15, 0.05),
    "food_income_weight": _prior(0.15, 0.05),
    "food_basket_low": _prior(1.0, 0.2),
    "food_basket_high": _prior(2.2, 0.3),
    "food_buffer_income_weight": _prior(0.50, 0.08),
    "food_buffer_cover_weight": _prior(0.50, 0.08),
    "food_cover_days_ref": _prior(180.0, 20.0),
    "food_trigger_gap_weight": _prior(0.60, 0.08),
    "food_trigger_buffer_weight": _prior(0.40, 0.08),
    "unemployment_normalize_low": _prior(0.04, 0.02),
    "unemployment_normalize_high": _prior(0.20, 0.04),
    "protest_base_weight": _prior(0.35, 0.08),
    "protest_inflation_weight": _prior(0.20, 0.06),
    "protest_unemployment_weight": _prior(0.15, 0.05),
    "protest_food_weight": _prior(0.15, 0.05),
    "protest_distrust_weight": _prior(0.15, 0.05),
    "protest_buffer_trust_weight": _prior(0.50, 0.08),
    "protest_buffer_stability_weight": _prior(0.50, 0.08),
    "protest_trigger_level_weight": _prior(0.50, 0.08),
    "protest_trigger_pressure_weight": _prior(0.50, 0.08),
    "regime_stability_gap_weight": _prior(0.30, 0.07),
    "regime_distrust_weight": _prior(0.20, 0.06),
    "regime_tension_weight": _prior(0.20, 0.06),
    "regime_protest_weight": _prior(0.15, 0.05),
    "regime_sanctions_weight": _prior(0.15, 0.05),
    "regime_buffer_security_weight": _prior(0.35, 0.08),
    "regime_buffer_policy_space_weight": _prior(0.30, 0.07),
    "regime_buffer_trust_weight": _prior(0.35, 0.08),
    "regime_trigger_protest_weight": _prior(0.60, 0.08),
    "regime_trigger_stability_weight": _prior(0.40, 0.08),
    "sanctions_level_scale_weight": _prior(0.35, 0.08),
    "sanctions_level_barrier_weight": _prior(0.20, 0.06),
    "sanctions_level_fragmentation_weight": _prior(0.20, 0.06),
    "sanctions_level_fx_weight": _prior(0.15, 0.05),
    "sanctions_level_trade_slack_weight": _prior(0.10, 0.04),
    "sanctions_trade_slack_threshold": _prior(0.50, 0.08),
    "sanctions_trade_slack_ref": _prior(0.50, 0.08),
    "sanctions_buffer_policy_space_weight": _prior(0.50, 0.08),
    "sanctions_buffer_barrier_relief_weight": _prior(0.50, 0.08),
    "sanctions_trigger_scale_weight": _prior(0.70, 0.08),
    "sanctions_trigger_barrier_weight": _prior(0.30, 0.07),
    "reserve_stress_energy_weight": _prior(0.50, 0.08),
    "reserve_stress_food_weight": _prior(0.30, 0.07),
    "reserve_stress_metals_weight": _prior(0.20, 0.06),
    "reserve_stress_energy_ref": _prior(5.0, 0.7),
    "reserve_stress_food_ref": _prior(3.0, 0.5),
    "reserve_stress_metals_ref": _prior(5.0, 0.7),
    "strategic_import_weight": _prior(0.60, 0.08),
    "strategic_reserve_weight": _prior(0.40, 0.08),
    "strategic_trigger_import_weight": _prior(0.70, 0.08),
    "strategic_trigger_reserve_weight": _prior(0.30, 0.07),
    "chokepoint_gap_trade_weight": _prior(0.40, 0.08),
    "chokepoint_trade_weight": _prior(0.20, 0.06),
    "chokepoint_oil_weight": _prior(0.25, 0.06),
    "chokepoint_route_weight": _prior(0.15, 0.05),
    "chokepoint_trigger_oil_weight": _prior(0.60, 0.08),
    "chokepoint_trigger_level_weight": _prior(0.40, 0.08),
    "oil_gap_weight": _prior(0.45, 0.08),
    "oil_cover_weight": _prior(0.20, 0.06),
    "oil_chokepoint_weight": _prior(0.20, 0.06),
    "oil_export_weight": _prior(0.15, 0.05),
    "energy_cover_days_ref": _prior(180.0, 20.0),
    "oil_buffer_cover_weight": _prior(0.60, 0.08),
    "oil_buffer_gap_relief_weight": _prior(0.40, 0.08),
    "oil_trigger_oil_weight": _prior(0.50, 0.08),
    "oil_trigger_gap_weight": _prior(0.50, 0.08),
    "conflict_conflict_weight": _prior(0.30, 0.07),
    "conflict_distrust_weight": _prior(0.20, 0.06),
    "conflict_hawkishness_weight": _prior(0.15, 0.05),
    "conflict_military_weight": _prior(0.15, 0.05),
    "conflict_sanctions_weight": _prior(0.10, 0.04),
    "conflict_war_links_weight": _prior(0.10, 0.04),
    "conflict_military_ref": _prior(2.0, 0.3),
    "conflict_buffer_coalition_weight": _prior(0.50, 0.08),
    "conflict_buffer_security_weight": _prior(0.50, 0.08),
    "conflict_trigger_conflict_weight": _prior(0.50, 0.08),
    "conflict_trigger_hawkishness_weight": _prior(0.30, 0.07),
    "conflict_trigger_war_links_weight": _prior(0.20, 0.06),
}

WEIGHT_COLLECTIONS: Dict[str, object] = {
    "outcome_intercept": OUTCOME_INTERCEPTS,
    "outcome_driver": OUTCOME_DRIVERS,
    "outcome_link": OUTCOME_LINK_SHIFTS,
    "tail_risk": TAIL_RISK_PARAMETERS,
    "action_count_shift": ACTION_COUNT_SHIFTS,
    "action_risk_shift": ACTION_RISK_SHIFTS,
    "shock_risk_shift": SHOCK_RISK_SHIFTS,
    "objective_risk_utility": OBJECTIVE_TO_RISK_UTILITY,
    "action_objective_bonus": ACTION_OBJECTIVE_BONUS,
    "action_crisis_shift": ACTION_CRISIS_SHIFTS,
    "objective_crisis_utility": OBJECTIVE_TO_CRISIS_UTILITY,
    "objective_global_crisis_utility": OBJECTIVE_TO_GLOBAL_CRISIS_UTILITY,
    "profile_weight": PROFILE_WEIGHTS,
    "archetype_threshold": ARCHETYPE_THRESHOLDS,
    "archetype_relevance": ARCHETYPE_RELEVANCE,
    "regional_route_risk": REGIONAL_ROUTE_RISK,
    "crisis_metric_weight": CRISIS_METRIC_WEIGHTS,
}


def _iter_nested(category: str, value: object, prefix: tuple[str, ...] = ()) -> Iterator[tuple[str, str, str, GeoWeight]]:
    if isinstance(value, GeoWeight):
        key = prefix[0] if prefix else ""
        subkey = ".".join(prefix[1:]) if len(prefix) > 1 else ""
        yield (category, key, subkey, value)
        return
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            yield from _iter_nested(category, item_value, prefix + (str(item_key),))


def iter_geo_weight_entries() -> Iterator[tuple[str, str, str, GeoWeight]]:
    for category, value in WEIGHT_COLLECTIONS.items():
        yield from _iter_nested(category, value)


def iter_geo_weights() -> Iterator[GeoWeight]:
    for _category, _key, _subkey, weight in iter_geo_weight_entries():
        yield weight


def collect_geo_weight_paths() -> Dict[str, GeoWeight]:
    return {
        f"{category}:{key}:{subkey}".rstrip(":"): weight
        for category, key, subkey, weight in iter_geo_weight_entries()
    }


def _resolve_weight_slot(path: str) -> tuple[dict[str, object], str]:
    parts = path.split(":", 2)
    if len(parts) < 2:
        raise KeyError(f"Invalid geo-weight path: {path}")

    category = parts[0]
    key = parts[1]
    subkey = parts[2] if len(parts) > 2 else ""

    collection = WEIGHT_COLLECTIONS.get(category)
    if collection is None or not isinstance(collection, dict):
        raise KeyError(f"Unknown geo-weight category: {category}")

    if not subkey:
        return collection, key

    target = collection[key]
    leaf_parts = subkey.split(".")
    for part in leaf_parts[:-1]:
        if not isinstance(target, dict):
            raise KeyError(f"Path does not resolve to a mutable geo-weight mapping: {path}")
        target = target[part]
    if not isinstance(target, dict):
        raise KeyError(f"Path does not resolve to a mutable geo-weight mapping: {path}")
    return target, leaf_parts[-1]


def replace_geo_weight_path(path: str, weight: GeoWeight) -> GeoWeight:
    container, leaf_key = _resolve_weight_slot(path)
    current = container[leaf_key]
    if not isinstance(current, GeoWeight):
        raise KeyError(f"Geo-weight path does not point to a GeoWeight: {path}")
    container[leaf_key] = weight
    return current


def set_geo_weight_value(path: str, value: float, *, source: str | None = None) -> GeoWeight:
    current = collect_geo_weight_paths()[path]
    updated = GeoWeight(
        value=value,
        ci95=current.ci95,
        source=source or current.source,
    )
    return replace_geo_weight_path(path, updated)


def lookup_value(mapping: Dict[str, GeoWeight], key: str) -> float:
    return mapping[key].value


def nested_value(mapping: Dict[str, Dict[str, GeoWeight]], key: str, subkey: str) -> float:
    return mapping[key][subkey].value


def nested_value_3(
    mapping: Dict[str, Dict[str, Dict[str, GeoWeight]]],
    key: str,
    subkey: str,
    leaf_key: str,
) -> float:
    return mapping[key][subkey][leaf_key].value
