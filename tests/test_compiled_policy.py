from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from GIM_13.compiled_policy import CompiledLLMPolicyManager
from GIM_13.runtime import load_world
from GIM_13.scenario_compiler import compile_question
from GIM_13.sim_bridge import SimBridge
from gim_11_1.observation import build_observation


REPO_ROOT = Path(__file__).resolve().parents[1]


class CompiledPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()

    def _fake_doctrine(self, manager: CompiledLLMPolicyManager, obs, signature: str):
        return manager._doctrine_from_payload(
            obs=obs,
            signature=signature,
            source="compiled-llm",
            payload={
                "domestic_priority": 0.45,
                "escalation_bias": 0.40,
                "sanctions_tolerance": 0.35,
                "trade_openness": 0.55,
                "mediation_openness": 0.60,
                "reserve_protection": 0.45,
                "military_readiness": 0.42,
                "finance_defensiveness": 0.38,
                "climate_pragmatism": 0.44,
                "explanation": "test doctrine",
            },
        )

    def test_never_refresh_compiles_once_per_agent(self) -> None:
        manager = CompiledLLMPolicyManager(refresh_mode="never", prefer_llm=True)
        obs = build_observation(self.world, "USA")
        policy = manager.policy_for_agent("USA")

        with patch.object(manager, "_llm_status", return_value=(True, "ok")), patch.object(
            manager,
            "_compile_doctrine_with_llm",
            side_effect=lambda current_obs, signature, memory: self._fake_doctrine(
                manager, current_obs, signature
            ),
        ) as mocked_compile:
            policy(obs, None)
            policy(obs, None)

        self.assertEqual(mocked_compile.call_count, 1)
        self.assertEqual(manager.cache_size(), 1)

    def test_trigger_refresh_recompiles_on_regime_shift(self) -> None:
        manager = CompiledLLMPolicyManager(refresh_mode="trigger", prefer_llm=True)
        obs = build_observation(self.world, "USA")
        shifted = deepcopy(obs)
        shifted.self_state["competitive"]["protest_risk"] = 0.95
        policy = manager.policy_for_agent("USA")

        with patch.object(manager, "_llm_status", return_value=(True, "ok")), patch.object(
            manager,
            "_compile_doctrine_with_llm",
            side_effect=lambda current_obs, signature, memory: self._fake_doctrine(
                manager, current_obs, signature
            ),
        ) as mocked_compile:
            policy(obs, None)
            policy(shifted, None)

        self.assertEqual(mocked_compile.call_count, 2)
        self.assertEqual(manager.cache_size(), 2)

    def test_compiled_mode_runs_without_live_llm_key(self) -> None:
        scenario = compile_question(
            question="Will Red Sea tensions escalate for Saudi Arabia, Turkey and China?",
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "China"],
            template_id="maritime_deterrence",
        )
        bridge = SimBridge()
        env = dict(os.environ)
        env["NO_LLM"] = "1"
        env.pop("DEEPSEEK_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            evaluation, trajectory = bridge.evaluate_scenario(
                self.world,
                scenario,
                n_years=1,
                default_mode="compiled-llm",
                llm_refresh="trigger",
                llm_refresh_years=2,
            )

        self.assertEqual(len(trajectory), 2)
        self.assertIn("net_crisis_shift", evaluation.crisis_signal_summary)
        self.assertTrue(evaluation.dominant_outcomes)


if __name__ == "__main__":
    unittest.main()
