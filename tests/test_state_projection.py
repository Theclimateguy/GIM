from pathlib import Path
import csv
import tempfile
import unittest

from gim.paths import OPERATIONAL_STATE_CSV
from gim.state_projection import COMPILED_STATE_COLUMNS, project_state_csv, write_projection_metadata
from gim.core.world_factory import make_world_from_csv


class StateProjectionTests(unittest.TestCase):
    def test_project_state_csv_writes_reloadable_compiled_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_csv = Path(tmpdir) / "agent_states_operational_2024.csv"
            metadata_json = Path(tmpdir) / "agent_states_operational_2024.projection.json"

            summary = project_state_csv(
                state_csv=OPERATIONAL_STATE_CSV,
                output_csv=output_csv,
                years=1,
                state_year=2020,
                policy_mode="simple",
                enable_extreme_events=False,
                seed=0,
            )
            write_projection_metadata(summary, metadata_json)

            self.assertEqual(summary.baseline_year, 2020)
            self.assertEqual(summary.target_year, 2021)
            self.assertTrue(output_csv.exists())
            self.assertTrue(metadata_json.exists())

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

            self.assertEqual(reader.fieldnames, list(COMPILED_STATE_COLUMNS))
            self.assertEqual(len(rows), summary.agent_count)
            self.assertGreater(summary.world_gdp_end, 0.0)

            reloaded_world = make_world_from_csv(str(output_csv), base_year=summary.target_year)
            self.assertEqual(len(reloaded_world.agents), summary.agent_count)


if __name__ == "__main__":
    unittest.main()
