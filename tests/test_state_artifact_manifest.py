from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import warnings
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
from gim.core import state_artifact
from misc.calibration.refresh_state_artifact_manifest import build_manifest


PRIMARY_MANIFEST = REPO_ROOT / "misc" / "data" / "agent_states_operational.artifacts.json"
REFERENCE_STATE = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_state_2015.csv"
OBSERVED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_observed.json"


class StateArtifactManifestTests(unittest.TestCase):
    def test_primary_manifest_exists(self) -> None:
        self.assertTrue(PRIMARY_MANIFEST.exists(), PRIMARY_MANIFEST)

    def test_emissions_scale_is_data_derived_from_backtest_fixture(self) -> None:
        observed = json.loads(OBSERVED_FIXTURE.read_text(encoding="utf-8"))
        derived = state_artifact.compute_emissions_scale_from_state_csv(
            REFERENCE_STATE,
            observed["global_co2_gtco2"]["2015"],
        )
        self.assertAlmostEqual(derived, 0.9755424434, delta=0.02)

        binding = state_artifact.PRIMARY_STATE_ARTIFACT
        self.assertEqual(binding.rebuild_source, "data")
        self.assertAlmostEqual(binding.emissions_scale, derived, delta=1e-9)
        self.assertEqual(binding.decarb_source, "legacy")

    def test_primary_load_can_warn_and_fallback_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            state_csv = repo_root / "misc" / "data" / "agent_states_operational.csv"
            state_csv.parent.mkdir(parents=True, exist_ok=True)
            state_csv.write_text("id,value\nA,1\n", encoding="utf-8")

            with patch.object(state_artifact, "_repo_root", return_value=repo_root):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    binding = state_artifact.load_primary_state_artifact(allow_legacy_fallback=True)

        self.assertEqual(binding.rebuild_source, "legacy")
        self.assertAlmostEqual(binding.emissions_scale, state_artifact.LEGACY_EMISSIONS_SCALE)
        self.assertTrue(any("legacy artifact values" in str(item.message) for item in caught))

    def test_manifest_builder_can_stamp_observed_decarb_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state_csv = tmp / "state.csv"
            state_csv.write_text("id,value\nA,1\n", encoding="utf-8")
            manifest = build_manifest(
                state_csv=state_csv,
                manifest_path=tmp / "state.artifacts.json",
                emissions_scale=0.98,
                decarb_rate=0.022,
                target_year=2023,
                builder_reference="test",
                handoff_contract="test contract",
                rebuild_source="data",
                emissions_reference_year=2015,
                emissions_reference_gtco2=35.4,
                emissions_reference_state_csv=REFERENCE_STATE,
                decarb_source="observed",
                decarb_reference_rate=0.022,
                decarb_reference_start_year=2010,
                decarb_reference_end_year=2022,
            )

        self.assertEqual(manifest["decarb_reference"]["source"], "observed")
        self.assertEqual(manifest["decarb_reference"]["rate"], 0.022)
        self.assertEqual(manifest["decarb_reference"]["start_year"], 2010)
        self.assertEqual(manifest["decarb_reference"]["end_year"], 2022)


if __name__ == "__main__":
    unittest.main()
