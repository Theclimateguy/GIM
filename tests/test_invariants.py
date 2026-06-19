"""Tests for the GIM17 accounting/integrity invariant layer (Stage B)."""

import unittest

from gim.core.invariants import (
    CHANNEL_TELESCOPE_TOL,
    InvariantViolation,
    RECONCILE_CLAMP_TOL,
    TRADE_BALANCE_TOL,
    aggregate_run,
    enforce,
    evaluate_violations,
    resolve_invariant_mode,
    summarize_step,
)
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"


def _run(years: int = 4, max_agents: int = 15, mode: str | None = None):
    world = make_world_from_csv(STATE_CSV, max_agents=max_agents, base_year=2026)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    log: list[dict] = []
    for _ in range(years):
        step_world(world, policies, invariant_log=log, invariant_mode=mode)
    return log


def _clean_summary(year: int = 1) -> dict:
    return {
        "year": year,
        "bounds": {"breach_count": 0, "breaches": []},
        "reconcile_clamp": {"max_abs": 0.0, "over_tol": []},
        "channel_telescope": {"max_abs": 0.0, "over_tol": []},
        "debt_fiscal_residual": {"abs_share_max": 0.84, "abs_share_mean": 0.1, "count": 1, "top": []},
        "trade_balance": {"net_exports_sum": 0.0, "world_gdp": 100.0, "abs_share": 0.0},
        "resource_consistency": {},
    }


class EnforceableInvariantsTests(unittest.TestCase):
    def test_enforceable_invariants_clean_under_default_scenario(self):
        log = _run()
        agg = aggregate_run(log)
        self.assertEqual(agg["enforceable"]["total_bounds_breaches"], 0)
        self.assertLessEqual(agg["enforceable"]["max_reconcile_clamp"], RECONCILE_CLAMP_TOL)
        self.assertLessEqual(agg["enforceable"]["max_channel_telescope"], CHANNEL_TELESCOPE_TOL)
        self.assertTrue(agg["enforceable"]["clean"])

    def test_strict_mode_runs_default_scenario_without_raising(self):
        # The default scenario satisfies all enforceable invariants, so strict is safe.
        _run(mode="strict")


class StrictModeUnitTests(unittest.TestCase):
    def test_clean_summary_does_not_raise(self):
        enforce(_clean_summary(), "strict")  # must not raise

    def test_bounds_breach_raises(self):
        s = _clean_summary()
        s["bounds"] = {"breach_count": 1, "breaches": [{"agent_id": "X", "field": "economy.gdp", "value": -1.0}]}
        with self.assertRaises(InvariantViolation):
            enforce(s, "strict")

    def test_reconcile_clamp_over_tolerance_raises(self):
        s = _clean_summary()
        s["reconcile_clamp"] = {"max_abs": 1e-3, "over_tol": [{"agent_id": "X", "field": "gdp", "adjustment": -1e-3}]}
        with self.assertRaises(InvariantViolation):
            enforce(s, "strict")

    def test_channel_telescope_over_tolerance_raises(self):
        s = _clean_summary()
        s["channel_telescope"] = {"max_abs": 1e-3, "over_tol": [{"agent_id": "X", "field": "public_debt", "diff": 1e-3}]}
        with self.assertRaises(InvariantViolation):
            enforce(s, "strict")

    def test_observe_mode_never_raises(self):
        s = _clean_summary()
        s["bounds"] = {"breach_count": 5, "breaches": []}
        enforce(s, "observe")  # must not raise even with a breach


class TradeBalanceTests(unittest.TestCase):
    def test_world_trade_balance_closed_under_default_scenario(self):
        log = _run()
        agg = aggregate_run(log)
        self.assertLessEqual(agg["enforceable"]["max_trade_balance_abs_share"], TRADE_BALANCE_TOL)

    def test_strict_mode_raises_on_trade_imbalance(self):
        s = _clean_summary()
        s["trade_balance"] = {"net_exports_sum": 5.0, "world_gdp": 100.0, "abs_share": 0.05}
        with self.assertRaises(InvariantViolation):
            enforce(s, "strict")

    def test_trade_imbalance_listed_in_violations(self):
        s = _clean_summary()
        s["trade_balance"] = {"net_exports_sum": 5.0, "world_gdp": 100.0, "abs_share": 0.05}
        self.assertTrue(any("trade balance" in v for v in evaluate_violations(s)))


class ResourceConsistencyTests(unittest.TestCase):
    def test_resource_ledger_is_coherent_after_t1_2(self):
        # T1.2 RESOLVED Finding C-1: global_reserves == sum of country own_reserve, so no pool
        # is exhausted-with-production and the enforceable ledger divergence is ~0.
        log = _run()
        agg = aggregate_run(log)
        diag = agg["diagnostic_resource_consistency"]
        self.assertEqual(diag["pools_exhausted_with_active_production"], [])
        self.assertFalse(diag["flagged"])
        from gim.core.invariants import RESOURCE_LEDGER_TOL
        self.assertLessEqual(agg["enforceable"]["max_resource_ledger_abs_share"], RESOURCE_LEDGER_TOL)

    def test_resource_consistency_not_enforced(self):
        # A flagged resource pool must not cause an enforceable violation.
        log = _run()
        for s in log:
            self.assertEqual(
                [v for v in evaluate_violations(s) if "resource" in v.lower()],
                [],
            )


class DebtIdentityTests(unittest.TestCase):
    """T1.1: the debt stock-flow identity (Delta debt == sum of recorded flows) is enforceable."""

    def test_identity_closes_over_run(self):
        log = _run(years=12, max_agents=30)
        agg = aggregate_run(log)
        from gim.core.invariants import DEBT_IDENTITY_TOL
        self.assertLessEqual(agg["enforceable"]["max_debt_identity_abs_share"], DEBT_IDENTITY_TOL)
        self.assertTrue(agg["enforceable"]["clean"])

    def test_strict_mode_runs_without_raising(self):
        _run(years=10, max_agents=30, mode="strict")  # must not raise InvariantViolation

    def test_debt_flow_ledger_records_and_resets(self):
        from gim.core.critical_pending import get_debt_flows, record_debt_flow, reset_debt_flows
        from gim.core.world_factory import make_world_from_csv

        w = make_world_from_csv(STATE_CSV, max_agents=4, base_year=2026)
        reset_debt_flows(w)
        aid = next(iter(w.agents))
        record_debt_flow(w, aid, "restructuring", -0.5)
        record_debt_flow(w, aid, "fiscal", 0.2)
        self.assertAlmostEqual(get_debt_flows(w)[aid]["restructuring"], -0.5)
        self.assertAlmostEqual(get_debt_flows(w)[aid]["fiscal"], 0.2)
        reset_debt_flows(w)
        self.assertEqual(get_debt_flows(w), {})


class DiagnosticResidualTests(unittest.TestCase):
    def test_fiscal_residual_is_reported_not_enforced(self):
        # A large debt fiscal residual must NOT trigger an enforceable violation.
        s = _clean_summary()
        s["debt_fiscal_residual"]["abs_share_max"] = 0.84
        self.assertEqual(evaluate_violations(s), [])
        enforce(s, "strict")  # must not raise

    def test_aggregate_flags_large_residual(self):
        log = _run()
        agg = aggregate_run(log)
        diag = agg["diagnostic_debt_fiscal_residual"]
        self.assertIn("worst_abs_share", diag)
        self.assertIn("flagged", diag)
        self.assertGreaterEqual(diag["worst_abs_share"], 0.0)


class ModeResolutionTests(unittest.TestCase):
    def test_default_is_observe(self):
        self.assertEqual(resolve_invariant_mode(None), "observe")

    def test_explicit_overrides(self):
        self.assertEqual(resolve_invariant_mode("strict"), "strict")
        self.assertEqual(resolve_invariant_mode("off"), "off")

    def test_unknown_falls_back_to_observe(self):
        self.assertEqual(resolve_invariant_mode("nonsense"), "observe")


class SummaryShapeTests(unittest.TestCase):
    def test_summarize_step_shape(self):
        report = {
            "breach_count": 0,
            "breaches": [],
            "debt_accounting_residual_top10": [],
            "debt_residual_abs_share_max": 0.2,
            "debt_residual_abs_share_mean": 0.05,
            "debt_residual_count": 3,
        }
        accounting = {
            "X": {
                "reconcile_adjustment": {"gdp": 0.0, "capital": 0.0, "public_debt": 0.0, "trust_gov": 0.0, "social_tension": 0.0},
                "channels": {
                    "sanctions_conflict": {"public_debt": 0.1},
                    "policy_trade": {"public_debt": 0.0},
                    "climate_macro": {"public_debt": 0.0},
                    "social_feedback": {"public_debt": 0.0},
                    "net_propagation": {"public_debt": 0.1},
                },
            }
        }
        s = summarize_step(year=2, invariant_report=report, critical_accounting=accounting)
        self.assertEqual(s["year"], 2)
        self.assertIn("reconcile_clamp", s)
        self.assertIn("channel_telescope", s)
        self.assertEqual(s["debt_fiscal_residual"]["abs_share_max"], 0.2)
        # net == sum of channels for this agent -> telescope diff ~ 0
        self.assertLessEqual(s["channel_telescope"]["max_abs"], CHANNEL_TELESCOPE_TOL)


if __name__ == "__main__":
    unittest.main()
