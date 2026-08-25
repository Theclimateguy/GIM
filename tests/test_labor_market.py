"""Tests for endogenous inflation/unemployment (Phillips + Okun), P4-A."""

import unittest

from gim.core import calibration_params as cal
from gim.core.labor_market import (
    _ENERGY_PRICE_PREV_ATTR,
    _GDP_PREV_ATTR,
    update_inflation_unemployment,
)
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"


def _world(n=4):
    return make_world_from_csv(STATE_CSV, max_agents=n, base_year=2023)


def _set_growth(agent, growth):
    """Force a known prior GDP so this step sees `growth`."""
    gdp = float(agent.economy.gdp)
    setattr(agent.economy, _GDP_PREV_ATTR, gdp / (1.0 + growth))


class OkunTests(unittest.TestCase):
    def test_above_potential_growth_lowers_unemployment(self):
        w = _world()
        a = next(iter(w.agents.values()))
        a.economy.unemployment = cal.NAIRU
        _set_growth(a, cal.POTENTIAL_OUTPUT_GROWTH + 0.05)  # boom
        update_inflation_unemployment(w)
        self.assertLess(a.economy.unemployment, cal.NAIRU)

    def test_recession_raises_unemployment(self):
        w = _world()
        a = next(iter(w.agents.values()))
        a.economy.unemployment = cal.NAIRU
        _set_growth(a, cal.POTENTIAL_OUTPUT_GROWTH - 0.06)  # contraction
        update_inflation_unemployment(w)
        self.assertGreater(a.economy.unemployment, cal.NAIRU)

    def test_unemployment_is_bounded(self):
        w = _world()
        for a in w.agents.values():
            a.economy.unemployment = cal.NAIRU
            _set_growth(a, -5.0)  # absurd collapse
        for _ in range(20):
            update_inflation_unemployment(w)
            for a in w.agents.values():
                _set_growth(a, -5.0)
        for a in w.agents.values():
            self.assertLessEqual(a.economy.unemployment, cal.UNEMPLOYMENT_MAX + 1e-9)
            self.assertGreaterEqual(a.economy.unemployment, cal.UNEMPLOYMENT_MIN - 1e-9)


class PhillipsTests(unittest.TestCase):
    def test_tight_labor_market_pushes_inflation_above_anchor(self):
        w = _world()
        a = next(iter(w.agents.values()))
        # Drive unemployment well below NAIRU via a sustained boom; inflation should
        # exceed the anchored target.
        a.economy.unemployment = cal.NAIRU - 0.03
        a.economy.inflation = cal.INFLATION_TARGET
        _set_growth(a, cal.POTENTIAL_OUTPUT_GROWTH + 0.04)
        update_inflation_unemployment(w)
        self.assertGreater(a.economy.inflation, cal.INFLATION_TARGET)

    def test_energy_cost_push_raises_inflation(self):
        # Same labor state, two energy-price histories: a price spike yields higher
        # inflation than a flat price.
        results = {}
        for change in (0.0, 0.5):
            w = _world(n=1)
            a = next(iter(w.agents.values()))
            a.economy.unemployment = cal.NAIRU  # neutral gap
            a.economy.inflation = cal.INFLATION_TARGET
            _set_growth(a, cal.POTENTIAL_OUTPUT_GROWTH)
            base = 1.0
            setattr(w.global_state, _ENERGY_PRICE_PREV_ATTR, base)
            w.global_state.prices["energy"] = base * (1.0 + change)
            update_inflation_unemployment(w)
            results[change] = a.economy.inflation
        self.assertGreater(results[0.5], results[0.0])
        self.assertAlmostEqual(
            results[0.5] - results[0.0],
            cal.INFLATION_COSTPUSH_COEFF * 0.5,
            places=6,
        )

    def test_inflation_is_bounded(self):
        w = _world()
        for a in w.agents.values():
            a.economy.unemployment = cal.UNEMPLOYMENT_MIN
        setattr(w.global_state, _ENERGY_PRICE_PREV_ATTR, 1.0)
        w.global_state.prices["energy"] = 100.0  # huge cost-push
        update_inflation_unemployment(w)
        for a in w.agents.values():
            self.assertLessEqual(a.economy.inflation, cal.INFLATION_MAX + 1e-9)
            self.assertGreaterEqual(a.economy.inflation, cal.INFLATION_MIN - 1e-9)


class DeterminismTests(unittest.TestCase):
    def test_repeatable(self):
        wa, wb = _world(), _world()
        for w in (wa, wb):
            update_inflation_unemployment(w)
        for a, b in zip(wa.agents.values(), wb.agents.values()):
            self.assertEqual(a.economy.unemployment, b.economy.unemployment)
            self.assertEqual(a.economy.inflation, b.economy.inflation)


if __name__ == "__main__":
    unittest.main()
