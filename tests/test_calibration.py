from pathlib import Path
import json
import unittest

from gim.__main__ import build_parser
from gim.calibration import (
    CalibrationRunConfig,
    DEFAULT_CALIBRATION_SUITE,
    discover_calibration_cases,
    discover_calibration_suites,
    load_calibration_cases,
    run_operational_calibration,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_STATE = REPO_ROOT / "data" / "agent_states_operational.csv"


class GIM13CalibrationTests(unittest.TestCase):
    def test_operational_suite_is_discoverable(self) -> None:
        suites = discover_calibration_suites()
        self.assertIn(DEFAULT_CALIBRATION_SUITE, suites)
        cases = discover_calibration_cases(DEFAULT_CALIBRATION_SUITE)
        self.assertGreaterEqual(len(cases), 10)

    def test_operational_suite_includes_stable_status_quo_cases(self) -> None:
        cases = [
            json.loads(path.read_text())
            for path in discover_calibration_cases(DEFAULT_CALIBRATION_SUITE)
        ]
        status_quo_cases = [
            case
            for case in cases
            if "status_quo" in case.get("expectations", {}).get("top_outcomes", [])
        ]
        self.assertGreaterEqual(len(status_quo_cases), 4)

    def test_calibrate_subcommand_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["calibrate"])
        self.assertEqual(args.command, "calibrate")
        self.assertEqual(args.suite, DEFAULT_CALIBRATION_SUITE)

    def test_operational_calibration_runs_on_primary_state(self) -> None:
        result = run_operational_calibration(state_csv=str(PRIMARY_STATE))
        self.assertEqual(result.case_count, len(result.results))
        self.assertGreaterEqual(result.case_count, 10)
        self.assertGreaterEqual(result.pass_count, result.case_count - 1)
        self.assertGreater(result.average_score, 0.75)
        self.assertGreater(result.average_criticality_score, 0.45)

    def test_stable_cases_pass_with_status_quo_top_outcome(self) -> None:
        stable_case_ids = {
            "norway_stability_2023",
            "switzerland_stability_2023",
            "canada_stability_2023",
            "australia_stability_2023",
        }
        result = run_operational_calibration(
            state_csv=str(PRIMARY_STATE),
            case_ids=stable_case_ids,
        )
        self.assertEqual(result.pass_count, result.case_count)
        for case_result in result.results:
            with self.subTest(case_id=case_result.case_id):
                self.assertEqual(case_result.snapshot.dominant_outcomes[0], "status_quo")

    def test_operational_calibration_supports_simulation_config(self) -> None:
        result = run_operational_calibration(
            state_csv=str(PRIMARY_STATE),
            config=CalibrationRunConfig(
                n_runs=1,
                horizon_years=1,
                use_sim=True,
                default_mode="simple",
            ),
        )
        self.assertEqual(result.case_count, len(result.results))
        self.assertGreaterEqual(result.case_count, 10)
        self.assertTrue(all(case_result.std_score >= 0.0 for case_result in result.results))

    def test_operational_v2_suite_all_cases_pass(self) -> None:
        result = run_operational_calibration(
            suite_id="operational_v2",
            state_csv=str(PRIMARY_STATE),
        )
        self.assertEqual(result.case_count, 5)
        self.assertEqual(result.pass_count, 5)
        self.assertGreater(result.average_score, 0.90)
        expected_top = {
            "argentina_default_2001": "internal_destabilization",
            "brazil_lula_crisis_2002": "negotiated_deescalation",
            "france_gilets_jaunes_2018": "status_quo",
            "south_korea_imf_1997": "negotiated_deescalation",
            "turkey_fx_crisis_2018": "internal_destabilization",
        }
        for case_result in result.results:
            with self.subTest(case_id=case_result.case_id):
                self.assertEqual(case_result.snapshot.dominant_outcomes[0], expected_top[case_result.case_id])

    def test_operational_v2_uses_discriminating_driver_expectations(self) -> None:
        cases = {case.id: case for case in load_calibration_cases("operational_v2")}
        self.assertEqual(cases["brazil_lula_crisis_2002"].expectations.drivers, ["negotiation_capacity", "debt_stress"])
        self.assertEqual(cases["france_gilets_jaunes_2018"].expectations.drivers, ["policy_space", "social_stress"])


if __name__ == "__main__":
    unittest.main()
