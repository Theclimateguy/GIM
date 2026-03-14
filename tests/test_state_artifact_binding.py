from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
from gim.core import calibration_params as cal
from gim.core.state_artifact import PRIMARY_STATE_ARTIFACT, load_state_artifact


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


class StateArtifactBindingTests(unittest.TestCase):
    def test_primary_manifest_matches_compiled_state(self) -> None:
        binding = PRIMARY_STATE_ARTIFACT

        self.assertEqual(binding.manifest_version, 1)
        self.assertEqual(binding.state_csv_path, REPO_ROOT / "data" / "agent_states_operational.csv")
        self.assertEqual(binding.state_csv_sha256, _compute_sha256(binding.state_csv_path))
        self.assertEqual(binding.state_row_count, _count_rows(binding.state_csv_path))
        self.assertTrue(binding.change_requires_pipeline_rebuild)
        self.assertGreater(binding.emissions_scale, 0.0)
        self.assertGreater(binding.decarb_rate, 0.0)
        self.assertIn("must only change", binding.handoff_contract.lower())
        self.assertEqual(binding.rebuild_source, "data")
        self.assertEqual(binding.emissions_reference_year, 2015)
        self.assertIsNotNone(binding.emissions_reference_gtco2)
        self.assertEqual(
            binding.emissions_reference_state_csv,
            (REPO_ROOT / "tests" / "fixtures" / "historical_backtest_state_2015.csv").resolve(),
        )
        self.assertEqual(binding.decarb_source, "legacy")
        self.assertAlmostEqual(binding.decarb_reference_rate, 0.049)

    def test_calibration_params_use_manifest_bound_coefficients(self) -> None:
        self.assertAlmostEqual(cal.EMISSIONS_SCALE, PRIMARY_STATE_ARTIFACT.emissions_scale)
        self.assertAlmostEqual(cal.DECARB_RATE_STRUCTURAL, PRIMARY_STATE_ARTIFACT.decarb_rate)
        self.assertAlmostEqual(cal.DECARB_RATE, PRIMARY_STATE_ARTIFACT.decarb_rate)

    def test_explicit_state_csv_can_load_sibling_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "mini_state.csv"
            csv_path.write_text("id,value\nA,1\n", encoding="utf-8")
            manifest_path = csv_path.with_suffix(".artifacts.json")
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "state_csv": csv_path.name,
                        "state_csv_sha256": _compute_sha256(csv_path),
                        "state_row_count": 1,
                        "compiled_target_year": 2023,
                        "artifact_parameters": {
                            "emissions_scale": 1.8,
                            "decarb_rate": 0.049,
                        },
                        "change_requires_pipeline_rebuild": True,
                        "builder_reference": "test fixture",
                        "handoff_contract": "Pipeline-bound fixture; values must only change with rebuild.",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            binding = load_state_artifact(csv_path)

        self.assertEqual(binding.state_csv_path, csv_path.resolve())
        self.assertEqual(binding.state_row_count, 1)
        self.assertAlmostEqual(binding.emissions_scale, 1.8)
        self.assertAlmostEqual(binding.decarb_rate, 0.049)
        self.assertEqual(binding.rebuild_source, "legacy")
        self.assertIsNone(binding.emissions_reference_year)
        self.assertEqual(binding.decarb_source, "legacy")
        self.assertIsNone(binding.decarb_reference_start_year)


if __name__ == "__main__":
    unittest.main()
