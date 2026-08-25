import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "run_climate_energy_stress_test.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_climate_energy_stress_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ClimateEnergyStressRunnerTests(unittest.TestCase):
    def test_scenario_specs_cover_expected_policy_modes(self):
        runner = _load_runner()
        scenario_ids = {spec.scenario_id for spec in runner.SCENARIOS}
        self.assertIn("ssp1_sustainability", scenario_ids)
        self.assertIn("ssp2_middle_road", scenario_ids)
        self.assertIn("ssp3_fragmentation", scenario_ids)
        self.assertIn("ssp5_fossil_growth", scenario_ids)
        self.assertIn("delayed_transition", scenario_ids)

    def test_smoke_run_writes_core_artifacts(self):
        runner = _load_runner()
        with tempfile.TemporaryDirectory(prefix="gim17-climate-energy-") as tmp:
            args = argparse.Namespace(
                years=1,
                base_year=2023,
                state_csv=str(ROOT / "data" / "agent_states_operational.csv"),
                max_countries=6,
                seeds="2026",
                focus_actors="USA,CHN,IND",
                disable_extreme_events=True,
                output_dir=tmp,
            )
            output_dir = runner.run_experiment(args)
            self.assertTrue((output_dir / "scenario_config.json").exists())
            self.assertTrue((output_dir / "trajectories.csv").exists())
            self.assertTrue((output_dir / "all_actor_trajectories.csv").exists())
            self.assertTrue((output_dir / "trajectory_summary.csv").exists())
            self.assertTrue((output_dir / "final_summary.csv").exists())
            self.assertTrue((output_dir / "region_summary.csv").exists())
            self.assertTrue((output_dir / "country_summary.csv").exists())
            self.assertTrue((output_dir / "report.md").exists())
            report = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("GIM18 Climate/Energy Policy Stress Test", report)


if __name__ == "__main__":
    unittest.main()
