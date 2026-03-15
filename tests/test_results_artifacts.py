from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import gim.results as results_module
from gim.results import build_run_artifacts, resolve_run_output_path, write_json_artifact, write_run_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "credit_map_leaflet.py"


def _load_script_module(path: Path):
    spec = spec_from_file_location("credit_map_leaflet_module", path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


credit_map_leaflet = _load_script_module(SCRIPT_PATH)


class ResultsArtifactsTests(unittest.TestCase):
    def test_build_run_artifacts_uses_results_root(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            original_root = results_module.RESULTS_ROOT
            results_module.RESULTS_ROOT = Path(tmp_dir)
            try:
                artifacts = build_run_artifacts("question")
            finally:
                results_module.RESULTS_ROOT = original_root

            self.assertTrue(artifacts.run_dir.is_dir())
            self.assertEqual(artifacts.run_dir.parent, Path(tmp_dir))
            self.assertTrue(artifacts.run_id.startswith("question-"))

    def test_resolve_run_output_path_places_simple_filenames_inside_run_dir(self) -> None:
        run_dir = Path("/tmp/run-123")
        self.assertEqual(
            resolve_run_output_path(run_dir, "dashboard.html", "dashboard.html"),
            run_dir / "dashboard.html",
        )
        self.assertEqual(
            resolve_run_output_path(run_dir, None, "evaluation.json"),
            run_dir / "evaluation.json",
        )
        self.assertEqual(
            resolve_run_output_path(run_dir, "exports/dashboard.html", "dashboard.html"),
            Path("exports/dashboard.html"),
        )

    def test_write_json_artifact_and_manifest_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir) / "question-20260315-210000"
            run_dir.mkdir(parents=True)
            json_path = write_json_artifact({"status": "ok"}, run_dir / "evaluation.json")
            manifest_path = write_run_manifest({"outputs": {"evaluation_json": str(json_path)}}, run_dir)

            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["status"], "ok")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["outputs"]["evaluation_json"], str(json_path))

    def test_credit_map_script_finds_latest_world_log_in_nested_results_dirs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results_root = Path(tmp_dir) / "results"
            older_dir = results_root / "world-20260315-190000"
            newer_dir = results_root / "world-20260315-200000"
            older_dir.mkdir(parents=True)
            newer_dir.mkdir(parents=True)

            older_world = older_dir / "GIM_14_2026-03-15_19-00-00_t0-t5.csv"
            newer_world = newer_dir / "GIM_14_2026-03-15_20-00-00_t0-t5.csv"
            ignored_actions = newer_dir / "GIM_14_2026-03-15_20-00-00_actions.csv"
            ignored_institutions = newer_dir / "GIM_14_2026-03-15_20-00-00_institutions.csv"

            for path in (older_world, newer_world, ignored_actions, ignored_institutions):
                path.write_text("time,agent_id\n", encoding="utf-8")

            os.utime(older_world, (100, 100))
            os.utime(newer_world, (200, 200))
            os.utime(ignored_actions, (300, 300))
            os.utime(ignored_institutions, (400, 400))

            self.assertEqual(credit_map_leaflet.find_latest_world_log(results_root), newer_world)


if __name__ == "__main__":
    unittest.main()
