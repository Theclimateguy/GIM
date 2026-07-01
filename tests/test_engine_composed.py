"""The composed-scenario path is reachable through the assistant executor.

Exercises the wiring added for Part 1: the assistant's ``run_composed`` tool ->
``_RUN_DISPATCH['composed']`` -> ``compose_scenario`` -> ``evaluate_scenario`` ->
the stable UI projection. No HTTP server; we call the in-process executor the
``/assistant`` handler uses, so this guards the exact path the chat takes.
"""
from __future__ import annotations

import unittest

from gim.engine_service import _make_assistant_executor, _world_key_for


class RunComposedExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        # Default world (state_csv=None), mirroring what /world/load registers.
        # Stored on the instance (not the class) so the closure is not bound as a
        # method when accessed via ``self``.
        world_key = _world_key_for(None, None, None)
        self.executor = _make_assistant_executor(world_key)

    def test_executor_composes_and_evaluates(self) -> None:
        out = self.executor(
            "run_composed",
            {"question": "energy shock plus export controls, China and the United States"},
        )
        result = out.get("result")
        self.assertIsNotNone(result)
        self.assertEqual(result["mode"], "composed")
        self.assertIn("criticality", result)
        self.assertTrue(result["outcomes"], "composed run produced no outcome distribution")
        # The composer (not a frozen template) authored the scenario.
        self.assertEqual(result["scenario"]["template_id"], "composed")
        channels = {s["channel"] for s in result["scenario"]["shocks"]}
        self.assertEqual(channels, {"resource", "technology"})
        # Reproduce trace points at the real CLI flag.
        self.assertIn("--compose", result["trace"]["equiv_cli"])

    def test_summary_is_nonempty(self) -> None:
        out = self.executor("run_composed", {"question": "a sanctions spiral against Russia"})
        self.assertTrue(out.get("summary"))

    def test_llm_authored_levers_are_honored(self) -> None:
        # C1: the assistant can author the scenario by passing explicit levers.
        out = self.executor("run_composed", {
            "question": "siege economy on Iran",
            "levers": [{"lever": "resource", "magnitude": 0.9}, {"lever": "sanctions", "magnitude": 0.7}],
            "actors": ["Iran", "United States"],
        })
        scenario = out["result"]["scenario"]
        by_channel = {s["channel"]: s["magnitude"] for s in scenario["shocks"]}
        self.assertEqual(set(by_channel), {"resource", "sanctions"})
        self.assertAlmostEqual(by_channel["resource"], 0.9, places=3)
        self.assertEqual(scenario["actor_names"], ["Iran", "United States"])

    def test_dimensions_readout_present(self) -> None:
        # C4: non-military readout grouped economy/society/climate/security.
        out = self.executor("run_composed", {"question": "energy shock and export controls in China"})
        dims = out["result"].get("dimensions")
        self.assertTrue(dims)
        self.assertEqual([g["group"] for g in dims], ["Экономика", "Социум", "Климат", "Безопасность"])
        self.assertTrue(all("value" in m for g in dims for m in g["metrics"]))


if __name__ == "__main__":
    unittest.main()
