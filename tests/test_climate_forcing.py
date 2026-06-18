from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
from gim.core import calibration_params as cal
from gim.core.climate import update_emissions_from_economy, update_global_climate
from gim.core.core import (
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

    def test_heat_cap_surface_is_resolved_at_call_time(self) -> None:
        world_fast = self._make_world()
        world_slow = self._make_world()

        original_surface = cal.HEAT_CAP_SURFACE
        try:
            cal.HEAT_CAP_SURFACE = 10.0
            update_global_climate(world_fast, dt=1.0, f_nonco2=0.4)

            cal.HEAT_CAP_SURFACE = 50.0
            update_global_climate(world_slow, dt=1.0, f_nonco2=0.4)
        finally:
            cal.HEAT_CAP_SURFACE = original_surface

        self.assertGreater(
            abs(world_fast.global_state.temperature_global - 1.0),
            abs(world_slow.global_state.temperature_global - 1.0),
        )

    def test_temperature_variability_uses_seeded_annual_shocks(self) -> None:
        world_left = self._make_world()
        world_left.global_state._calendar_year_base = 2015
        world_left.global_state._enable_temperature_variability = True
        world_left.global_state._temperature_variability_seed = 11
        world_left.time = 2

        world_right = self._make_world()
        world_right.global_state._calendar_year_base = 2015
        world_right.global_state._enable_temperature_variability = True
        world_right.global_state._temperature_variability_seed = 11
        world_right.time = 2

        update_global_climate(world_left, dt=1.0, f_nonco2=0.4)
        update_global_climate(world_right, dt=1.0, f_nonco2=0.4)
        self.assertAlmostEqual(
            world_left.global_state.temperature_global,
            world_right.global_state.temperature_global,
            places=12,
        )

        world_other_seed = self._make_world()
        world_other_seed.global_state._calendar_year_base = 2015
        world_other_seed.global_state._enable_temperature_variability = True
        world_other_seed.global_state._temperature_variability_seed = 12
        world_other_seed.time = 2
        update_global_climate(world_other_seed, dt=1.0, f_nonco2=0.4)

        self.assertNotAlmostEqual(
            world_left.global_state.temperature_global,
            world_other_seed.global_state.temperature_global,
            places=9,
        )

    def test_dt_zero_suppresses_temperature_variability(self) -> None:
        world = self._make_world()
        world.global_state._enable_temperature_variability = True
        world.global_state._temperature_variability_seed = 5
        original_temp = world.global_state.temperature_global

        update_global_climate(world, dt=0.0, f_nonco2=0.4)
        self.assertAlmostEqual(world.global_state.temperature_global, original_temp, places=12)

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

        no_policy = self._make_agent()
        policy = self._make_agent()

        update_emissions_from_economy(no_policy, time=0, policy_reduction=0.0, fuel_tax_change=0.0)
        update_emissions_from_economy(policy, time=0, policy_reduction=0.15, fuel_tax_change=0.3)
        ratio_now = policy.climate.co2_annual_emissions / no_policy.climate.co2_annual_emissions

        update_emissions_from_economy(no_policy, time=1, policy_reduction=0.0, fuel_tax_change=0.0)
        update_emissions_from_economy(policy, time=1, policy_reduction=0.15, fuel_tax_change=0.3)
        ratio_later = policy.climate.co2_annual_emissions / no_policy.climate.co2_annual_emissions

        self.assertLess(ratio_later, ratio_now)

    def test_current_policy_only_accelerates_future_structural_progress(self) -> None:
        reduction = 0.15
        fuel_tax_change = 0.3
        no_policy = self._make_agent()
        policy = self._make_agent()

        update_emissions_from_economy(no_policy, time=10, policy_reduction=0.0, fuel_tax_change=0.0)
        update_emissions_from_economy(
            policy,
            time=10,
            policy_reduction=reduction,
            fuel_tax_change=fuel_tax_change,
        )

        tax_effect = 1.0 - cal.FUEL_TAX_EMISSIONS_SENS * fuel_tax_change
        tax_effect = min(cal.FUEL_TAX_EFFECT_MAX, max(cal.FUEL_TAX_EFFECT_MIN, tax_effect))
        expected_ratio = (1.0 - reduction) * tax_effect
        actual_ratio = policy.climate.co2_annual_emissions / no_policy.climate.co2_annual_emissions

        self.assertAlmostEqual(actual_ratio, expected_ratio, places=6)
        self.assertGreater(
            policy.climate._structural_transition_progress,
            no_policy.climate._structural_transition_progress,
        )

    def test_structural_progress_does_not_reverse_after_policy_removal(self) -> None:
        agent = self._make_agent()
        progress = []

        for time in range(5):
            update_emissions_from_economy(
                agent,
                time=time,
                policy_reduction=0.15,
                fuel_tax_change=0.3,
            )
            progress.append(agent.climate._structural_transition_progress)

        for time in range(5, 8):
            update_emissions_from_economy(
                agent,
                time=time,
                policy_reduction=0.0,
                fuel_tax_change=0.0,
            )
            progress.append(agent.climate._structural_transition_progress)

        self.assertTrue(
            all(progress[index + 1] >= progress[index] for index in range(len(progress) - 1))
        )


if __name__ == "__main__":
    unittest.main()
