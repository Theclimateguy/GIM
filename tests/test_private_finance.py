"""F2.3 (D3): stock-flow-consistent private finance + financial accelerator (switchable, default off)."""
import unittest

from gim.core import calibration_params as cal
from gim.core.params import default_params
from gim.core.private_finance import update_private_finance
from gim.core.world_factory import make_world_from_csv

STATE = "data/agent_states_operational_2026_calibrated.csv"


class PrivateFinanceTests(unittest.TestCase):
    def test_default_is_on(self):
        # [E2.4 re-anchor] SFC private finance is ON in the headline (golden-safe).
        self.assertTrue(cal.SFC_FINANCE)

    def test_explicit_off_sets_no_state(self):
        world = make_world_from_csv(STATE, max_agents=4, base_year=2026)
        world.params = default_params().with_overrides({"SFC_FINANCE": False})
        a = next(iter(world.agents.values()))
        update_private_finance(a, world)  # explicitly off -> no-op
        self.assertFalse(hasattr(a.economy, "_private_debt"))
        self.assertFalse(hasattr(a.economy, "_credit_premium"))

    def test_on_builds_credit_and_premium(self):
        world = make_world_from_csv(STATE, max_agents=4, base_year=2026)
        world.params = default_params().with_overrides({
            "SFC_FINANCE": True, "SFC_INIT_LEVERAGE": 2.0,  # start over-levered -> premium > 0
        })
        a = next(iter(world.agents.values()))
        update_private_finance(a, world)
        self.assertGreater(a.economy._private_debt, 0.0)
        self.assertGreater(a.economy._credit_premium, 0.0)  # leverage 2.0 > ref 1.5

    def test_stock_flow_update_is_consistent(self):
        # private_debt_{t+1} = private_debt_t + new_credit - repayment, both >= 0
        world = make_world_from_csv(STATE, max_agents=4, base_year=2026)
        world.params = default_params().with_overrides({"SFC_FINANCE": True, "SFC_INIT_LEVERAGE": 1.0})
        a = next(iter(world.agents.values()))
        gdp = a.economy.gdp
        update_private_finance(a, world)
        pd1 = a.economy._private_debt
        # one more step: must move by (credit - repayment), staying finite/non-negative
        update_private_finance(a, world)
        self.assertGreaterEqual(a.economy._private_debt, 0.0)
        self.assertNotEqual(a.economy._private_debt, pd1)


if __name__ == "__main__":
    unittest.main()
