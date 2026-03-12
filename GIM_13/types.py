from dataclasses import dataclass, field
from typing import Any, Dict, List


RISK_CLASSES = (
    "status_quo",
    "controlled_suppression",
    "internal_destabilization",
    "limited_proxy_escalation",
    "maritime_chokepoint_crisis",
    "direct_strike_exchange",
    "broad_regional_escalation",
    "negotiated_deescalation",
)

TAIL_RISK_CLASSES = (
    "controlled_suppression",
    "internal_destabilization",
    "limited_proxy_escalation",
    "maritime_chokepoint_crisis",
    "direct_strike_exchange",
    "broad_regional_escalation",
)

RISK_LABELS = {
    "status_quo": "Status quo",
    "controlled_suppression": "Controlled suppression",
    "internal_destabilization": "Internal destabilization",
    "limited_proxy_escalation": "Limited proxy escalation",
    "maritime_chokepoint_crisis": "Maritime chokepoint crisis",
    "direct_strike_exchange": "Direct strike exchange",
    "broad_regional_escalation": "Broad regional escalation",
    "negotiated_deescalation": "Negotiated de-escalation",
}

AVAILABLE_ACTIONS = (
    "signal_deterrence",
    "signal_restraint",
    "arm_proxy",
    "restrain_proxy",
    "covert_disruption",
    "maritime_interdiction",
    "partial_mobilization",
    "targeted_strike",
    "backchannel_offer",
    "accept_mediation",
    "information_campaign",
    "domestic_crackdown",
    "impose_tariffs",
    "export_controls",
    "lift_sanctions",
    "currency_intervention",
    "debt_restructuring",
    "capital_controls",
    "cyber_probe",
    "cyber_disruption_attack",
    "cyber_espionage",
    "cyber_defense_posture",
)


@dataclass
class CalibrationGuardrails:
    focus_on_critical_states: bool = True
    preserve_baseline_calibration: bool = True
    require_causal_explanations: bool = True
    allow_soft_threshold_overrides: bool = True
    forbid_physics_breaking_states: bool = True
    notes: List[str] = field(
        default_factory=lambda: [
            "Tail-risk is explicitly preserved for wars, sanctions, crises and other critical states.",
            "Legacy hard thresholds are treated as soft guardrails rather than silent clipping rules.",
            "Any extreme trajectory must be justified by a causal chain and remain physically interpretable.",
        ]
    )


@dataclass
class ScenarioShock:
    channel: str
    magnitude: float
    cadence: str
    rationale: str


@dataclass
class ScenarioDefinition:
    id: str
    title: str
    template_id: str
    source_prompt: str
    base_year: int
    horizon_months: int
    actor_ids: List[str]
    actor_names: List[str]
    unresolved_actor_names: List[str] = field(default_factory=list)
    risk_classes: List[str] = field(default_factory=lambda: list(RISK_CLASSES))
    monitored_indicators: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    narrative: str = ""
    shocks: List[ScenarioShock] = field(default_factory=list)
    risk_biases: Dict[str, float] = field(default_factory=dict)
    critical_focus: bool = True
    tags: List[str] = field(default_factory=list)
    calibration_guardrails: CalibrationGuardrails = field(default_factory=CalibrationGuardrails)


@dataclass
class PlayerDefinition:
    player_id: str
    display_name: str
    objectives: Dict[str, float]
    allowed_actions: List[str]
    constraints: List[str] = field(default_factory=list)


@dataclass
class GameDefinition:
    id: str
    title: str
    scenario: ScenarioDefinition
    players: List[PlayerDefinition]
    constraints: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class ScenarioEvaluation:
    scenario: ScenarioDefinition
    raw_risk_scores: Dict[str, float]
    risk_probabilities: Dict[str, float]
    driver_scores: Dict[str, float]
    actor_profiles: Dict[str, Dict[str, float]]
    crisis_dashboard: object
    crisis_delta_by_agent: Dict[str, Dict[str, Dict[str, float]]]
    crisis_signal_summary: Dict[str, float]
    dominant_outcomes: List[str]
    criticality_score: float
    calibration_score: float
    physical_consistency_score: float
    consistency_notes: List[str]
    threshold_override_notes: List[str]


@dataclass
class GameCombinationResult:
    actions: Dict[str, str]
    evaluation: ScenarioEvaluation
    player_payoffs: Dict[str, float]
    total_payoff: float


@dataclass
class GameResult:
    game: GameDefinition
    baseline_evaluation: ScenarioEvaluation
    best_combination: GameCombinationResult
    combinations: List[GameCombinationResult]
    truncated_action_space: bool = False
    trajectory: List[Any] | None = None
    baseline_trajectory: List[Any] | None = None
