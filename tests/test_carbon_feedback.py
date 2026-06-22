"""Carbon-cycle completion: land-use CO2 source + smooth feedback (E2.1 / E2.2).

Guards that both new channels are switchable and default-OFF (golden-preserving), and that when
enabled they move CO2 / temperature in the physically correct direction.
"""
import unittest

from gim.core import calibration_params as cal
from gim.core.climate import update_global_climate
from gim.core.params import default_params
from gim.core.world_factory import make_world_from_csv

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _run(overrides, years=30, emit=35.0):
    world = make_world_from_csv(STATE, max_agents=8, base_year=2026)
    world.params = default_params().with_overrides(overrides) if overrides else default_params()
    world.global_state._temperature_variability_sigma = 0.0  # deterministic
    # fixed annual emissions so the only difference is the channel under test
    agents = list(world.agents.values())
    for a in agents:
        a.climate.co2_annual_emissions = emit / len(agents)
    for _ in range(years):
        for a in agents:  # keep emissions fixed each year
            a.climate.co2_annual_emissions = emit / len(agents)
        update_global_climate(world)
    return world.global_state.co2, world.global_state.temperature_global


class CarbonFeedbackTests(unittest.TestCase):
    def test_headline_defaults(self):
        # [E2.4 re-anchor] land-use is ON in the headline; the smooth feedback + tipping stay
        # ensemble-only (off) because they blow up the deterministic long-horizon SCC.
        self.assertEqual(cal.LAND_USE_CO2_GTCO2_YR, 0.6)
        self.assertFalse(cal.CARBON_CYCLE_FEEDBACK)
        self.assertFalse(cal.CARBON_TIPPING)

    def test_land_use_raises_co2_and_warming(self):
        co2_off, t_off = _run(None)
        co2_on, t_on = _run({"LAND_USE_CO2_GTCO2_YR": 5.0})
        self.assertGreater(co2_on, co2_off)
        self.assertGreater(t_on, t_off)

    def test_smooth_feedback_raises_warming(self):
        co2_off, t_off = _run(None)
        co2_on, t_on = _run({
            "CARBON_CYCLE_FEEDBACK": True,
            "CARBON_FEEDBACK_CO2_GTCO2_PER_C": 1.5,
            "CARBON_FEEDBACK_CH4_WM2_PER_C": 0.03,
        })
        self.assertGreater(t_on, t_off)
        self.assertGreater(co2_on, co2_off)  # permafrost CO2 flux adds to pools

    def test_feedback_explicit_off_matches_default(self):
        # The smooth feedback is off in the headline; setting it explicitly off changes nothing.
        base = _run(None)
        off = _run({"CARBON_CYCLE_FEEDBACK": False})
        self.assertEqual(base, off)

    def test_abrupt_tipping_default_off_and_active_when_enabled(self):
        self.assertFalse(cal.CARBON_TIPPING)
        co2_off, _ = _run(None)
        # high onset hazard + low threshold so events reliably fire in a warm run
        co2_on, _ = _run({
            "CARBON_TIPPING": True,
            "CARBON_TIPPING_T_THRESHOLD": 0.0,
            "CARBON_TIPPING_BASE_PROB": 0.8,
            "CARBON_TIPPING_SCALE_GTCO2": 10.0,
        })
        self.assertGreater(co2_on, co2_off)

    def test_abrupt_release_helper_zero_when_no_hazard(self):
        import random
        from gim.criticality import abrupt_carbon_release
        rng = random.Random(1)
        # below threshold and zero base prob -> never fires
        self.assertEqual(abrupt_carbon_release(rng, 0.5, t_threshold=1.5, base_prob=0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
