from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
from gim.core import calibration_params as cal
from gim.core.core import (
    AgentState,
    ClimateSubState,
    CulturalState,
    EconomyState,
    GlobalState,
    RiskState,
    SocietyState,
    TechnologyState,
    WorldState,
)
from gim.core.country_params import (
    get_country_macro_prior,
    get_savings_rate,
    get_social_spend_share,
    get_tax_rate,
)
from gim.core.economy import update_public_finances


class CountryMacroPriorTests(unittest.TestCase):
    def _make_agent(self, name: str) -> AgentState:
        return AgentState(
            id=name.lower().replace(" ", "_"),
            type="state",
            name=name,
            region="test-region",
            economy=EconomyState(
                gdp=10.0,
                capital=20.0,
                population=100_000_000,
                public_debt=5.0,
                fx_reserves=1.0,
            ),
            resources={},
            society=SocietyState(
                trust_gov=0.5,
                social_tension=0.3,
                inequality_gini=40.0,
            ),
            climate=ClimateSubState(
                climate_risk=0.2,
                co2_annual_emissions=5.0,
            ),
            culture=CulturalState(),
            technology=TechnologyState(),
            risk=RiskState(
                water_stress=0.2,
                regime_stability=0.8,
                debt_crisis_prone=0.1,
                conflict_proneness=0.2,
            ),
        )

    def _make_world(self, agent: AgentState) -> WorldState:
        return WorldState(
            time=0,
            agents={agent.id: agent},
            global_state=GlobalState(
                co2=0.0,
                temperature_global=1.2,
                biodiversity_index=0.72,
            ),
            relations={agent.id: {}},
        )

    def test_alias_lookup_resolves_country_prior(self) -> None:
        self.assertEqual(get_country_macro_prior("USA"), get_country_macro_prior("United States"))

    def test_high_savings_countries_are_capped_until_econometric_pass(self) -> None:
        self.assertAlmostEqual(get_savings_rate("United States"), 0.18, places=6)
        self.assertAlmostEqual(get_savings_rate("China"), cal.SAVINGS_BASE, places=6)
        self.assertAlmostEqual(get_savings_rate("Rest of World"), cal.SAVINGS_BASE, places=6)

    def test_public_finances_use_country_tax_and_social_shares(self) -> None:
        us_agent = self._make_agent("United States")
        us_world = self._make_world(us_agent)
        update_public_finances(us_agent, us_world)

        expected_us_adapt = cal.CLIMATE_ADAPT_BASE + cal.CLIMATE_ADAPT_RISK_SENS * 0.2
        self.assertAlmostEqual(us_agent.economy.taxes, get_tax_rate("United States") * 10.0, places=6)
        self.assertAlmostEqual(
            us_agent.economy.gov_spending,
            10.0 * (get_social_spend_share("United States") + cal.MILITARY_SPEND_BASE + expected_us_adapt),
            places=6,
        )

        fr_agent = self._make_agent("France")
        fr_world = self._make_world(fr_agent)
        update_public_finances(fr_agent, fr_world)

        self.assertAlmostEqual(fr_agent.economy.taxes, get_tax_rate("France") * 10.0, places=6)
        self.assertGreater(fr_agent.economy.gov_spending, us_agent.economy.gov_spending)


if __name__ == "__main__":
    unittest.main()
