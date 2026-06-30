from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

# Climate baselines (2023).
CO2_PREINDUSTRIAL_GT = 2184.0
CO2_STOCK_2023_GT = 3270.0
# [FIX #3a 2026-06] 2023 surface-temperature anomaly above pre-industrial AND the zero point for
# incremental climate damage (start == damage reference, so warming damages begin at 0 in 2023).
# Was 1.2 (a decadal-mean-style value that left the forward run starting ~0.13 C below the model's
# own 1750->2023 spin-up and ~0.25 C below observed 2023). Re-anchored to the self-consistent
# spin-up value (gim/climate_backtest.py); the residual gap to observed ~1.47 is closed by the
# ECS bump (#3b), so the model *generates* observed warming rather than being pinned to it.
TGLOBAL_2023_C = 1.333
# [FIX #3a] Self-consistent 2023 deep-ocean anomaly from the same spin-up (surface-ocean gap ~0.93 C,
# i.e. real warming-in-the-pipeline). The legacy 0.4-C gap under-stated ocean heat uptake.
TOCEAN_2023_C = 0.404
BIODIVERSITY_2023 = 0.72
WATER_STRESS_2023 = 0.55
GTCO2_PER_PPM = 7.81
F2XCO2_W_M2 = 3.71

# Partition of the 2023 atmospheric CO2 excess across the 4 IPCC-AR6 impulse-response pools
# (timescales [inf, 394, 36.5, 4.3] yr), for initialising the *forward* world at 2023. Derived
# from a 1750->2023 spin-up driven by observed emissions (gim/climate_backtest.py): the historical
# excess is aged, so it sits mostly in the long-lived pools. Initialising it by the *flow*
# fractions (CARBON_POOL_FRACTIONS) instead over-loads the fast 4.3-yr pool (~0.28 vs the aged
# ~0.044) and creates a phantom ~50 GtCO2/yr sink that made the no-policy baseline CO2 *fall*.
# Reproduce: spin up update_global_climate from pre-industrial on data/global_co2_emissions_owid.csv
# and read the normalised carbon_pools at 2023.
CARBON_POOL_INIT_FRACTIONS_2023 = (0.3800, 0.3519, 0.2243, 0.0437)

# Global energy constraints.
WORLD_URR_FOSSIL_ENERGY_ZJ = 35.0
WORLD_PROVEN_RESERVES_ZJ = 32.5
WORLD_ANNUAL_SUPPLY_CAP_ZJ = 0.65

ClimatePolicy = Literal["none", "weak", "moderate", "strong"]
TradeDirection = Literal["import", "export"]
PricePreference = Literal["cheap", "fair", "premium"]
SanctionType = Literal["none", "mild", "strong"]
SecurityActionType = Literal[
    "none",
    "military_exercise",
    "arms_buildup",
    "border_incident",
    "conflict",
]
TradeRestrictionLevel = Literal["none", "soft", "hard"]

RESOURCE_NAMES = ("energy", "food", "metals")


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class EconomyState:
    gdp: float
    capital: float
    population: float
    public_debt: float
    fx_reserves: float
    taxes: float = 0.0
    gov_spending: float = 0.0
    social_spending: float = 0.0
    military_spending: float = 0.0
    rd_spending: float = 0.0
    climate_adaptation_spending: float = 0.0
    climate_shock_years: int = 0
    climate_shock_penalty: float = 0.0
    interest_payments: float = 0.0
    net_exports: float = 0.0
    gdp_per_capita: float = 0.0
    unemployment: float = 0.04
    inflation: float = 0.02
    birth_rate: float = 0.012
    death_rate: float = 0.008
    _gdp_prev: Optional[float] = None
    _debt_gdp_prev: Optional[float] = None


@dataclass
class ResourceSubState:
    own_reserve: float
    production: float
    consumption: float
    efficiency: float = 1.0


@dataclass
class CulturalState:
    # F3: only the load-bearing / theory-wired Hofstede dims are retained.
    # idv is load-bearing (inequality sensitivity); pdi/uai/lto are wired into the social
    # block via the switchable CULTURE_SOCIAL_LINKS channel. The 4 dropped dims
    # (mas, ind, traditional_secular, survival_self_expression) were empirically inert.
    pdi: float = 50.0
    idv: float = 50.0
    uai: float = 50.0
    lto: float = 50.0
    regime_type: str = "Democracy"


@dataclass
class SocietyState:
    trust_gov: float
    social_tension: float
    inequality_gini: float
    _trust_prev: Optional[float] = None
    _tension_prev: Optional[float] = None


@dataclass
class ClimateSubState:
    climate_risk: float
    co2_annual_emissions: float = 0.0
    biodiversity_local: float = 0.8
    _emissions_prev: Optional[float] = None


@dataclass
class RiskState:
    water_stress: float
    regime_stability: float
    debt_crisis_prone: float
    conflict_proneness: float
    debt_crisis_active_years: int = 0
    fx_crisis_active_years: int = 0
    regime_crisis_active_years: int = 0
    debt_crisis_trigger: str = "debt"
    external_debt_ratio: float = 0.0
    current_account_ratio: float = 0.0
    fx_reserve_cover_months: float = 0.0


@dataclass
class TechnologyState:
    tech_level: float = 1.0
    military_power: float = 1.0
    security_index: float = 0.5


@dataclass
class PoliticalState:
    legitimacy: float = 0.5
    protest_pressure: float = 0.0
    hawkishness: float = 0.5
    protectionism: float = 0.3
    coalition_openness: float = 0.5
    sanction_propensity: float = 0.4
    policy_space: float = 0.5
    last_block_change: int = -999


@dataclass
class PolicyRecord:
    step: int
    action: str
    action_params: Dict[str, Any]
    gdp_delta: Optional[float]
    debt_gdp_delta: Optional[float]
    trust_delta: Optional[float]
    tension_delta: Optional[float]
    crisis_flags_after: List[str] = field(default_factory=list)


@dataclass
class AgentState:
    id: str
    type: str
    name: str
    region: str
    economy: EconomyState
    resources: Dict[str, ResourceSubState]
    society: SocietyState
    climate: ClimateSubState
    culture: CulturalState
    technology: TechnologyState
    risk: RiskState
    alliance_block: str = "NonAligned"
    active_sanctions: Dict[str, SanctionType] = field(default_factory=dict)
    sanction_years: Dict[str, int] = field(default_factory=dict)
    political: PoliticalState = field(default_factory=PoliticalState)
    credit_rating: int = 13
    credit_zone: str = "investment"
    credit_risk_score: float = 0.5
    credit_rating_details: Dict[str, float] = field(default_factory=dict)
    memory_id: Optional[str] = None
    policy_log: List[PolicyRecord] = field(default_factory=list)


@dataclass
class GlobalState:
    co2: float
    temperature_global: float
    biodiversity_index: float
    temperature_ocean: float = 0.0
    forcing_total: float = 0.0
    carbon_pools: List[float] = field(default_factory=list)
    baseline_gdp_pc: float = 0.0
    prices: Dict[str, float] = field(
        default_factory=lambda: {
            "energy": 1.0,
            "food": 1.0,
            "metals": 1.0,
        }
    )
    global_reserves: Dict[str, float] = field(
        default_factory=lambda: {
            "energy": WORLD_PROVEN_RESERVES_ZJ,
            "food": 100.0,
            "metals": 100.0,
        }
    )
    temp_history: List[float] = field(default_factory=list)
    temp_trend_3yr: float = 0.0


@dataclass
class RelationState:
    trade_intensity: float
    trust: float
    conflict_level: float
    trade_barrier: float = 0.0
    at_war: bool = False
    war_years: int = 0
    war_start_gdp: float = 0.0
    war_start_pop: float = 0.0
    war_start_resource: float = 0.0


def effective_trade_intensity(relation: RelationState) -> float:
    return max(0.0, relation.trade_intensity * (1.0 - clamp01(relation.trade_barrier)))


@dataclass
class InstitutionState:
    id: str
    name: str
    org_type: str
    mandate: List[str]
    members: List[str]
    legitimacy: float = 0.6
    budget: float = 0.0
    base_budget_share: float = 0.0
    active_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldState:
    time: int
    agents: Dict[str, AgentState]
    global_state: GlobalState
    relations: Dict[str, Dict[str, RelationState]]
    institutions: Dict[str, InstitutionState] = field(default_factory=dict)
    institution_reports: List[Dict[str, Any]] = field(default_factory=list)
    # NOTE: the per-run parameter context (Phase 1, option B2) is attached at runtime as
    # ``world.params`` (a ParameterSet) by world_factory, NOT as a dataclass field, so it is
    # excluded from dataclasses.asdict() serialization. Access it via params.resolve_params().


@dataclass
class Observation:
    agent_id: str
    time: int
    self_state: Dict[str, Any]
    resource_balance: Dict[str, Dict[str, float]]
    external_actors: Dict[str, Any]
    summary: str = ""
    memory: Dict[str, Any] = field(default_factory=dict)

    def main_payload(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "time": self.time,
            "self_state": self.self_state,
            "resource_balance": self.resource_balance,
            "external_actors": self.external_actors,
            "summary": self.summary,
        }


@dataclass
class TradeDeal:
    partner: str
    resource: str
    direction: TradeDirection
    volume_change: float
    price_preference: PricePreference


@dataclass
class TradeRestriction:
    target: str
    level: TradeRestrictionLevel
    reason: str = ""


@dataclass
class SanctionsAction:
    target: str
    type: SanctionType
    reason: str = ""


@dataclass
class SecurityActions:
    type: SecurityActionType
    target: Optional[str]


@dataclass
class DomesticPolicy:
    tax_fuel_change: float
    social_spending_change: float
    military_spending_change: float
    rd_investment_change: float
    climate_policy: ClimatePolicy


@dataclass
class ForeignPolicy:
    proposed_trade_deals: List[TradeDeal] = field(default_factory=list)
    sanctions_actions: List[SanctionsAction] = field(default_factory=list)
    trade_restrictions: List[TradeRestriction] = field(default_factory=list)
    security_actions: SecurityActions = field(
        default_factory=lambda: SecurityActions(type="none", target=None)
    )


@dataclass
class FinancePolicy:
    borrow_from_global_markets: float
    use_fx_reserves_change: float


@dataclass
class Action:
    agent_id: str
    time: int
    domestic_policy: DomesticPolicy
    foreign_policy: ForeignPolicy
    finance: FinancePolicy
    explanation: str = ""


# In-memory yearly snapshots keyed by agent_id.
AgentMemory = Dict[str, List[Dict[str, Any]]]
