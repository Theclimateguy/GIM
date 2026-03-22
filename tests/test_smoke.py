from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv
from gim.paths import DEFAULT_STATE_CSV, REPO_ROOT


class GIM16SmokeTests(unittest.TestCase):
    def test_default_state_csv_exists(self) -> None:
        self.assertTrue(DEFAULT_STATE_CSV.exists(), DEFAULT_STATE_CSV)

    def test_world_loads_from_repo_data(self) -> None:
        world = make_world_from_csv(str(DEFAULT_STATE_CSV))
        self.assertGreaterEqual(len(world.agents), 20)
        self.assertGreater(sum(agent.climate.co2_annual_emissions for agent in world.agents.values()), 0.0)

    def test_one_step_simulation_runs_with_simple_policies(self) -> None:
        world = make_world_from_csv(str(DEFAULT_STATE_CSV))
        policies = make_policy_map(world.agents.keys(), mode="simple")
        starting_time = world.time
        next_world = step_world(world, policies, enable_extreme_events=False)

        self.assertEqual(next_world.time, starting_time + 1)
        self.assertGreater(next_world.global_state.co2, 0.0)
        self.assertGreater(next_world.global_state.temperature_global, 0.0)

    def test_cli_smoke_run(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "POLICY_MODE": "simple",
                "SIM_YEARS": "1",
                "SAVE_CSV_LOGS": "0",
                "GENERATE_CREDIT_MAP": "0",
                "STATE_CSV": str(DEFAULT_STATE_CSV),
            }
        )
        result = subprocess.run(
            [sys.executable, "-m", "gim"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("MODEL GIM16", result.stdout)
        self.assertIn("Simulation complete", result.stdout)


if __name__ == "__main__":
    unittest.main()
