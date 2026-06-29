"""Proof prototype: ontology-driven, on-the-fly scenario composition.

These tests demonstrate the thesis behind the redesign — that scenarios can be
*composed* from a bounded calibrated ontology instead of picked from a handful of
frozen templates, and that the engine **measurably reacts** to what is composed
(so it is not a narrative-only "theatre of depth"). No model math is touched: the
proof runs composed scenarios through the existing ``GameRunner.evaluate_scenario``.
"""
from __future__ import annotations

import unittest

from gim import scenario_ontology as onto
from gim.game_runner import GameRunner
from gim.runtime import load_world
from gim.scenario_composer import (
    CompositionError,
    LeverSelection,
    baseline_scenario,
    compose_scenario,
)
from gim.types import ScenarioShock


def _l1(p: dict[str, float], q: dict[str, float]) -> float:
    keys = set(p) | set(q)
    return sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


class OntologyContractTests(unittest.TestCase):
    def test_channels_are_engine_honoured(self) -> None:
        # The lever vocabulary may only target channels the engine acts on.
        for lever in onto.LEVERS.values():
            self.assertIn(lever.channel, onto.ENGINE_CHANNELS)

    def test_bilingual_lever_matching(self) -> None:
        self.assertEqual(onto.match_levers("ввести санкции против банков"), ["sanctions"])
        self.assertEqual(onto.match_levers("a sanctions spiral"), ["sanctions"])
        self.assertIn("maritime", onto.match_levers("blockade of the Hormuz strait"))

    def test_validator_flags_bogus_channel_and_range(self) -> None:
        world = _WORLD
        scenario = compose_scenario("sanctions on Russia", world)
        self.assertEqual(onto.validate_scenario(scenario, world), [])

        scenario.shocks.append(ScenarioShock("not_a_channel", 0.5, "monthly", ""))
        scenario.shocks.append(ScenarioShock("sanctions", 9.0, "monthly", ""))
        problems = onto.validate_scenario(scenario, world)
        self.assertTrue(any("not an engine channel" in p for p in problems))
        self.assertTrue(any("outside calibrated band" in p for p in problems))


class CompositionTests(unittest.TestCase):
    def test_distinct_prompts_compose_distinct_scenarios(self) -> None:
        world = _WORLD
        sanctions = compose_scenario("Sanctions spiral against Russia and Germany", world)
        maritime = compose_scenario("Maritime blockade in the Hormuz strait, Iran and the United States", world)

        # Both are composed (not one of the frozen templates)...
        self.assertEqual(sanctions.template_id, "composed")
        self.assertEqual(maritime.template_id, "composed")
        # ...and they target genuinely different engine channels.
        self.assertEqual({s.channel for s in sanctions.shocks}, {"sanctions"})
        self.assertEqual({s.channel for s in maritime.shocks}, {"maritime"})

    def test_out_of_range_magnitude_is_clamped(self) -> None:
        world = _WORLD

        def hot_selector(prompt: str, spec: dict) -> LeverSelection:
            return LeverSelection(lever_magnitudes={"sanctions": 99.0}, actors=["Russia"])

        scenario = compose_scenario("anything", world, selector=hot_selector)
        self.assertLessEqual(scenario.shocks[0].magnitude, onto.MAGNITUDE_MAX)

    def test_llm_seam_composes_valid_scenario(self) -> None:
        world = _WORLD
        seen: dict[str, object] = {}

        def fake_llm_selector(prompt: str, spec: dict) -> LeverSelection:
            seen["spec"] = spec  # the seam really receives the ontology menu
            return LeverSelection(
                lever_magnitudes={"cyber": 0.7, "domestic": 0.5},
                actors=["China", "United States"],
                rationale="fake LLM",
            )

        scenario = compose_scenario("play it out", world, selector=fake_llm_selector)
        self.assertEqual({s.channel for s in scenario.shocks}, {"cyber", "domestic"})
        self.assertEqual(onto.validate_scenario(scenario, world), [])
        self.assertIn("levers", seen["spec"])


class EngineReactsTests(unittest.TestCase):
    """The honesty test: composed scenarios must move the risk distribution."""

    def test_composed_scenario_diverges_from_baseline(self) -> None:
        world = _WORLD
        runner = GameRunner(world)

        scenario = compose_scenario("Sanctions spiral against Russia and Germany", world)
        base = baseline_scenario(world, actors=scenario.actor_names)

        scored = runner.evaluate_scenario(scenario).risk_probabilities
        baseline = runner.evaluate_scenario(base).risk_probabilities

        # A composed shock is not cosmetic: it measurably shifts the outcome mix.
        self.assertGreater(_l1(scored, baseline), 0.02)

    def test_different_scenarios_diverge_from_each_other(self) -> None:
        world = _WORLD
        runner = GameRunner(world)

        sanctions = compose_scenario("Sanctions spiral, Russia and Germany", world)
        maritime = compose_scenario("Maritime blockade Hormuz, Iran and United States", world)

        a = runner.evaluate_scenario(sanctions).risk_probabilities
        b = runner.evaluate_scenario(maritime).risk_probabilities
        self.assertGreater(_l1(a, b), 0.02)


def setUpModule() -> None:
    global _WORLD
    _WORLD = load_world()


_WORLD = None  # populated by setUpModule


if __name__ == "__main__":
    unittest.main()
