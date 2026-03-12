from pathlib import Path
import unittest

from GIM_13.__main__ import build_parser
from GIM_13.calibration import (
    CalibrationRunConfig,
    DEFAULT_CALIBRATION_SUITE,
    discover_calibration_cases,
    discover_calibration_suites,
    run_operational_calibration,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTAL_STATE = REPO_ROOT / "GIM_12" / "agent_states_gim13.csv"


class GIM13CalibrationTests(unittest.TestCase):
    def test_operational_suite_is_discoverable(self) -> None:
        suites = discover_calibration_suites()
        self.assertIn(DEFAULT_CALIBRATION_SUITE, suites)
        cases = discover_calibration_cases(DEFAULT_CALIBRATION_SUITE)
        self.assertGreaterEqual(len(cases), 6)

    def test_calibrate_subcommand_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["calibrate"])
        self.assertEqual(args.command, "calibrate")
        self.assertEqual(args.suite, DEFAULT_CALIBRATION_SUITE)

    def test_operational_calibration_runs_on_experimental_state(self) -> None:
        result = run_operational_calibration(state_csv=str(EXPERIMENTAL_STATE))
        self.assertEqual(result.case_count, len(result.results))
        self.assertGreaterEqual(result.case_count, 6)
        self.assertGreaterEqual(result.pass_count, result.case_count - 1)
        self.assertGreater(result.average_score, 0.75)
        self.assertGreater(result.average_criticality_score, 0.50)

    def test_operational_calibration_supports_simulation_config(self) -> None:
        result = run_operational_calibration(
            state_csv=str(EXPERIMENTAL_STATE),
            config=CalibrationRunConfig(
                n_runs=1,
                horizon_years=1,
                use_sim=True,
                default_mode="simple",
            ),
        )
        self.assertEqual(result.case_count, len(result.results))
        self.assertGreaterEqual(result.case_count, 6)
        self.assertTrue(all(case_result.std_score >= 0.0 for case_result in result.results))


if __name__ == "__main__":
    unittest.main()
