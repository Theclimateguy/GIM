from __future__ import annotations

from copy import deepcopy
import random
import unittest

from gim.hybrid_simulator import HUMAN_MODE_WHAT_IF, HybridSimulator, compile_human_intent
from gim.runtime import load_world
from gim.core.simulation import step_world


class HybridSimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world(max_agents=6)
        cls.simulator = HybridSimulator()

    def test_compile_human_intent_maps_ai_prompt_to_rd_lever(self) -> None:
        agent_id = next(agent.id for agent in self.world.agents.values() if agent.name == "United States")
        compiled = compile_human_intent(
            world=self.world,
            agent_id=agent_id,
            intent="Нужно наращивать расходы в ИИ и исследованиях, как это повлияет на экономику?",
            mode=HUMAN_MODE_WHAT_IF,
        )
        self.assertIn("ai_rd", compiled.matched_topics)
        self.assertGreater(compiled.normalized_action.domestic_policy.rd_investment_change, 0.0)
        self.assertGreater(compiled.confidence, 0.4)

    def test_run_round_returns_policy_baseline_and_effective_actions(self) -> None:
        result = self.simulator.run_round(
            deepcopy(self.world),
            intents_by_actor={
                "United States": "Increase AI and R&D spending moderately while keeping the budget stable."
            },
            mode=HUMAN_MODE_WHAT_IF,
            round_years=1,
            ensemble_size=1,
            seed=2026,
            default_mode="simple",
        )
        self.assertEqual(result.mode, HUMAN_MODE_WHAT_IF)
        self.assertEqual(len(result.policy_run.trajectory), 2)
        self.assertEqual(len(result.baseline_run.trajectory), 2)
        self.assertEqual(len(result.actor_comparisons), 1)
        comparison = result.actor_comparisons[0]
        self.assertEqual(comparison.agent_name, "United States")
        self.assertIn(comparison.agent_id, result.effective_actions_by_agent)
        self.assertTrue(result.effective_actions_by_agent[comparison.agent_id])
        self.assertIn("net_crisis_shift", result.crisis_delta_summary)

    def test_hybrid_baseline_path_matches_direct_step_world_logic(self) -> None:
        seed = 2040
        result = self.simulator.run_round(
            deepcopy(self.world),
            intents_by_actor={"United States": "Hold current course and avoid major policy changes."},
            mode=HUMAN_MODE_WHAT_IF,
            round_years=1,
            ensemble_size=1,
            seed=seed,
            default_mode="simple",
        )

        direct_world = deepcopy(self.world)
        direct_world.global_state._temperature_variability_seed = seed
        random.seed(seed)
        policy_map = self.simulator.bridge.build_policy_map(
            direct_world,
            game_def=None,
            default_mode="simple",
            llm_refresh="trigger",
            llm_refresh_years=2,
        )
        direct_world = step_world(direct_world, policy_map, memory={})
        baseline_terminal = result.baseline_run.trajectory[-1]

        self.assertEqual(set(direct_world.agents), set(baseline_terminal.agents))
        for agent_id in direct_world.agents:
            self.assertAlmostEqual(
                direct_world.agents[agent_id].economy.gdp,
                baseline_terminal.agents[agent_id].economy.gdp,
                places=9,
            )
            self.assertAlmostEqual(
                direct_world.agents[agent_id].society.trust_gov,
                baseline_terminal.agents[agent_id].society.trust_gov,
                places=9,
            )
            self.assertAlmostEqual(
                direct_world.agents[agent_id].society.social_tension,
                baseline_terminal.agents[agent_id].society.social_tension,
                places=9,
            )


if __name__ == "__main__":
    unittest.main()
