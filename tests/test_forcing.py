"""Tests for the multi-GHG non-CO2 forcing decomposition (P4-B)."""

import unittest

from gim.core.forcing import (
    NONCO2_ERF_REFERENCE,
    NONCO2_ERF_REFERENCE_NET,
    lumped_nonco2_forcing,
    nonco2_forcing,
    nonco2_forcing_components,
    set_nonco2_component_scales,
)
from gim.core.params import build_params
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"


class ReferenceTests(unittest.TestCase):
    def test_reference_net_matches_ar6_nonco2(self):
        # AR6/IGCC ~2019 net non-CO2 anthropogenic ERF is ~+0.5 to +0.6 W/m2.
        self.assertTrue(0.45 < NONCO2_ERF_REFERENCE_NET < 0.65, NONCO2_ERF_REFERENCE_NET)

    def test_signs_are_physical(self):
        # GHGs warm, aerosols cool.
        for gas in ("CH4", "N2O", "halogen", "O3"):
            self.assertGreater(NONCO2_ERF_REFERENCE[gas], 0.0)
        self.assertLess(NONCO2_ERF_REFERENCE["aerosol"], 0.0)


class DefaultBehaviourTests(unittest.TestCase):
    def test_default_net_equals_lumped_path(self):
        p = build_params()
        for year in (1990, 2015, 2019, 2023, 2050):
            self.assertAlmostEqual(nonco2_forcing(p, year), lumped_nonco2_forcing(p, year), places=12)

    def test_components_sum_to_net(self):
        p = build_params()
        comps = nonco2_forcing_components(p, 2023)
        self.assertAlmostEqual(sum(comps.values()), nonco2_forcing(p, 2023), places=10)


class LeverTests(unittest.TestCase):
    def test_methane_mitigation_lowers_net(self):
        p = build_params()
        base = nonco2_forcing(p, 2023)
        cut = nonco2_forcing(p, 2023, {"CH4": 0.5})
        self.assertAlmostEqual(cut - base, -0.5 * NONCO2_ERF_REFERENCE["CH4"], places=10)
        self.assertLess(cut, base)

    def test_aerosol_cleanup_unmasks_warming(self):
        # Reducing (negative) aerosol forcing magnitude raises the net -> more warming.
        p = build_params()
        base = nonco2_forcing(p, 2023)
        cleaner = nonco2_forcing(p, 2023, {"aerosol": 0.5})
        self.assertGreater(cleaner, base)

    def test_unknown_component_raises(self):
        p = build_params()
        with self.assertRaises(KeyError):
            nonco2_forcing(p, 2023, {"CO2": 0.5})


class IntegrationTests(unittest.TestCase):
    def test_methane_scenario_runs_cooler_than_baseline(self):
        def final_temp(scales):
            w = make_world_from_csv(STATE_CSV, max_agents=6, base_year=2026)
            set_nonco2_component_scales(w, scales)
            pol = make_policy_map(w.agents.keys(), mode="simple")
            for _ in range(8):
                step_world(w, pol)
            return w.global_state.temperature_global

        baseline = final_temp(None)
        mitigated = final_temp({"CH4": 0.3})  # strong methane cut
        self.assertLess(mitigated, baseline)

    def test_default_world_unchanged_by_empty_scales(self):
        def run(set_scales):
            w = make_world_from_csv(STATE_CSV, max_agents=6, base_year=2026)
            if set_scales:
                set_nonco2_component_scales(w, None)
            pol = make_policy_map(w.agents.keys(), mode="simple")
            for _ in range(5):
                step_world(w, pol)
            return w.global_state.temperature_global

        self.assertEqual(run(False), run(True))


if __name__ == "__main__":
    unittest.main()
