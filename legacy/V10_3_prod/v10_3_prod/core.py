from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

# Climate baselines (2023).
CO2_PREINDUSTRIAL_GT = 2184.0
CO2_STOCK_2023_GT = 3270.0
TGLOBAL_2023_C = 1.2
BIODIVERSITY_2023 = 0.72
WATER_STRESS_2023 = 0.55

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
    interest_payments: float = 0.0
    net_exports: float = 0.0
    gdp_per_capita: float = 0.0
    unemployment: float = 0.04
    inflation: float = 0.02
    birth_rate: float = 0.012
    death_rate: float = 0.008


@dataclass
class ResourceSubState:
    own_reserve: float
    production: float
    consumption: float
    efficiency: float = 1.0


@dataclass
class CulturalState:
    pdi: float = 50.0
    idv: float = 50.0
    mas: float = 50.0
    uai: float = 50.0
    lto: float = 50.0
    ind: float = 50.0
    survival_self_expression: float = 5.0
    traditional_secular: float = 5.0
    regime_type: str = "Democracy"


@dataclass
class SocietyState:
    trust_gov: float
    social_tension: float
    inequality_gini: float


@dataclass
class ClimateSubState:
    climate_risk: float
    co2_annual_emissions: float = 0.0
    biodiversity_local: float = 0.8


@dataclass
class RiskState:
    water_stress: float
    regime_stability: float
    debt_crisis_prone: float
    conflict_proneness: float


@dataclass
class TechnologyState:
    tech_level: float = 1.0
    military_power: float = 1.0
    security_index: float = 0.5


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
    memory_id: Optional[str] = None


@dataclass
class GlobalState:
    co2: float
    temperature_global: float
    biodiversity_index: float
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


@dataclass
class RelationState:
    trade_intensity: float
    trust: float
    conflict_level: float


@dataclass
class WorldState:
    time: int
    agents: Dict[str, AgentState]
    global_state: GlobalState
    relations: Dict[str, Dict[str, RelationState]]


@dataclass
class Observation:
    agent_id: str
    time: int
    self_state: Dict[str, Any]
    resource_balance: Dict[str, Dict[str, float]]
    external_actors: Dict[str, Any]
    summary: str = ""


@dataclass
class TradeDeal:
    partner: str
    resource: str
    direction: TradeDirection
    volume_change: float
    price_preference: PricePreference


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
