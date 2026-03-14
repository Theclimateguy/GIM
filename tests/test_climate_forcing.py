from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_CORE = REPO_ROOT / "legacy" / "GIM_11_1"
if str(LEGACY_CORE) not in sys.path:
    sys.path.insert(0, str(LEGACY_CORE))

from gim_11_1 import calibration_params as cal  # noqa: E402
from gim_11_1.climate import update_emissions_from_economy, update_global_climate  # noqa: E402
from gim_11_1.core import (  # noqa: E402
    CO2_PREINDUSTRIAL_GT,
    AgentState,
    ClimateSubState,
    CulturalState,
    EconomyState,
    GlobalState,
    ResourceSubState,
    RiskState,
    SocietyState,
    TechnologyState,
    WorldState,
)


class ClimateForcingTests(unittest.TestCase):
    def _make_world(self) -> WorldState:
        return WorldState(
            time=0,
            agents={},
            global_state=GlobalState(
                co2=CO2_PREINDUSTRIAL_GT,
                temperature_global=1.0,
                biodiversity_index=0.72,
                temperature_ocean=0.6,
            ),
            relations={},
        )

    def _make_agent(self, *, tech_level: float = 1.0, efficiency: float = 1.0) -> AgentState:
        return AgentState(
            id="A",
            type="country",
            name="Agent A",
            region="test",
            economy=EconomyState(
                gdp=10.0,
                capital=20.0,
                population=5.0,
                public_debt=4.0,
                fx_reserves=2.0,
            ),
            resources={
                "energy": ResourceSubState(
                    own_reserve=10.0,
                    production=2.0,
                    consumption=2.0,
                    efficiency=efficiency,
                )
            },
            society=SocietyState(trust_gov=0.6, social_tension=0.2, inequality_gini=35.0),
            climate=ClimateSubState(climate_risk=0.4, co2_annual_emissions=5.0),
            culture=CulturalState(),
            technology=TechnologyState(tech_level=tech_level),
            risk=RiskState(
                water_stress=0.3,
                regime_stability=0.7,
                debt_crisis_prone=0.2,
                conflict_proneness=0.2,
            ),
        )

    def test_nonco2_forcing_uses_calendar_base_year(self) -> None:
        world = self._make_world()
        world.global_state._calendar_year_base = 2015

        update_global_climate(world, dt=0.0)
        self.assertAlmostEqual(world.global_state.forcing_total, cal.F_NONCO2_DEFAULT, places=6)

        world.time = 8
        update_global_climate(world, dt=0.0)
        expected = cal.F_NONCO2_DEFAULT + 8 * cal.F_NONCO2_TREND
        self.assertAlmostEqual(world.global_state.forcing_total, expected, places=6)

    def test_explicit_nonco2_override_beats_calendar_schedule(self) -> None:
        world = self._make_world()
        world.global_state._calendar_year_base = 2015
        world.time = 8

        update_global_climate(world, dt=0.0, f_nonco2=0.25)
        self.assertAlmostEqual(world.global_state.forcing_total, 0.25, places=6)

    def test_tech_decarb_channel_works_without_structural_rate(self) -> None:
        original_structural = cal.DECARB_RATE_STRUCTURAL
        original_alias = cal.DECARB_RATE
        try:
            cal.DECARB_RATE_STRUCTURAL = 0.0
            cal.DECARB_RATE = 0.0

            baseline = self._make_agent(tech_level=1.0, efficiency=1.0)
            improved = self._make_agent(tech_level=2.0, efficiency=1.3)

            update_emissions_from_economy(baseline, time=8)
            update_emissions_from_economy(improved, time=8)

            self.assertLess(improved.climate.co2_annual_emissions, baseline.climate.co2_annual_emissions)
        finally:
            cal.DECARB_RATE_STRUCTURAL = original_structural
            cal.DECARB_RATE = original_alias

    def test_policy_tools_accelerate_structural_transition_over_time(self) -> None:
        self.assertGreater(cal.DECARB_RATE_STRUCTURAL, 0.0)

        no_policy_now = self._make_agent()
        policy_now = self._make_agent()
        no_policy_later = self._make_agent()
        policy_later = self._make_agent()

        update_emissions_from_economy(no_policy_now, time=0, policy_reduction=0.0, fuel_tax_change=0.0)
        update_emissions_from_economy(policy_now, time=0, policy_reduction=0.15, fuel_tax_change=0.3)
        update_emissions_from_economy(no_policy_later, time=10, policy_reduction=0.0, fuel_tax_change=0.0)
        update_emissions_from_economy(policy_later, time=10, policy_reduction=0.15, fuel_tax_change=0.3)

        ratio_now = policy_now.climate.co2_annual_emissions / no_policy_now.climate.co2_annual_emissions
        ratio_later = policy_later.climate.co2_annual_emissions / no_policy_later.climate.co2_annual_emissions

        self.assertLess(ratio_later, ratio_now)


if __name__ == "__main__":
    unittest.main()
