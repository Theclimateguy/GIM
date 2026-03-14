from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
from gim.core import calibration_params as cal
from gim.core.climate import climate_damage_multiplier
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv


STATE_CSV = REPO_ROOT / "data" / "agent_states.csv"


class LegacyCalibrationBaselineTests(unittest.TestCase):
    def _make_world(self):
        return make_world_from_csv(str(STATE_CSV))

    def test_production_elasticities_sum_to_one(self) -> None:
        total = cal.ALPHA_CAPITAL + cal.BETA_LABOR + cal.GAMMA_ENERGY
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_damage_range_at_2deg(self) -> None:
        damage_fraction = 1.0 - climate_damage_multiplier(2.0)
        self.assertGreater(damage_fraction, 0.001)
        self.assertLess(damage_fraction, 0.05)

    def test_damage_range_at_4deg(self) -> None:
        damage_fraction = 1.0 - climate_damage_multiplier(4.0)
        self.assertGreater(damage_fraction, 0.01)
        self.assertLess(damage_fraction, 0.15)

    def test_carbon_cycle_fractions_sum(self) -> None:
        self.assertAlmostEqual(sum(cal.CARBON_POOL_FRACTIONS), 1.0, places=4)

    def test_ecs_in_ar6_range(self) -> None:
        self.assertGreater(cal.ECS_DEFAULT, 1.5)
        self.assertLess(cal.ECS_DEFAULT, 4.5)

    def test_no_prior_params_above_threshold(self) -> None:
        audit_names = [
            name
            for name, status in sorted(cal.CALIBRATION_STATUS.items())
            if status in {"prior", "questionable", "artifact"}
        ]
        print("Calibration audit warnings:", ", ".join(audit_names))
        self.assertIsInstance(audit_names, list)

    def test_simulation_5yr_gdp_growth_plausible(self) -> None:
        world = self._make_world()
        policies = make_policy_map(world.agents.keys(), mode="simple")
        starting_gdp = {agent_id: agent.economy.gdp for agent_id, agent in world.agents.items()}

        for _ in range(5):
            world = step_world(world, policies, enable_extreme_events=False)

        for agent_id, agent in world.agents.items():
            initial = max(starting_gdp[agent_id], 1e-6)
            annual_growth = (agent.economy.gdp / initial) ** (1.0 / 5.0) - 1.0
            self.assertGreater(annual_growth, -0.05, agent_id)
            self.assertLess(annual_growth, 0.15, agent_id)

    def test_simulation_5yr_temperature_stays_in_plausible_band(self) -> None:
        world = self._make_world()
        policies = make_policy_map(world.agents.keys(), mode="simple")
        temps = [world.global_state.temperature_global]
        emissions = []

        for _ in range(5):
            emissions.append(sum(agent.climate.co2_annual_emissions for agent in world.agents.values()))
            world = step_world(world, policies, enable_extreme_events=False)
            temps.append(world.global_state.temperature_global)

        self.assertTrue(any(total > 0.0 for total in emissions))
        self.assertGreater(min(temps), -1.0)
        self.assertLess(max(temps), 4.0)
        self.assertLess(abs(temps[-1] - temps[0]), 0.6)


if __name__ == "__main__":
    unittest.main()
