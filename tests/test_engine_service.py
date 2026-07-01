"""Tests for the GIM17 macOS engine sidecar (`gim/engine_service.py`).

Each test starts the real service on an OS-assigned ephemeral port in a daemon
thread and drives it over loopback HTTP with the session token. Coverage:

- per-endpoint smoke (200 with token, 401 without, schema fields present);
- SSE progress (a What-if with horizon>0 emits >=1 ``progress`` then exactly one
  ``result``);
- cooperative cancellation (a tiny game can be cancelled mid-stream and ends with
  ``error{code:"cancelled"}``);
- the parity guarantee: a What-if ``result`` minus volatile fields deep-equals the
  ``python3 -m gim question --json`` output of the ``equiv_cli`` it reports —
  proving the engine introduces no math drift vs v17.2.0.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from gim.engine_service import build_engine_server

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_CSV = "data/agent_states_operational.csv"


def _numeric_drifts(a, b, path: str = "", *, rel_tol: float = 1e-9, abs_tol: float = 1e-12) -> list[str]:
    """Recursively compare two JSON-like evaluation objects.

    Returns a list of human-readable drift descriptions. Structure, strings, ints and bools must
    match exactly; floats may differ only within ``rel_tol``/``abs_tol`` (cross-process float
    reduction-order noise is ~1e-15 and must be ignored, while any real drift is >=1e-6).
    """
    import math

    drifts: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            drifts.append(f"{path}: key mismatch {sorted(a.keys()^b.keys())}")
        for k in a.keys() & b.keys():
            drifts += _numeric_drifts(a[k], b[k], f"{path}.{k}", rel_tol=rel_tol, abs_tol=abs_tol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            drifts.append(f"{path}: length {len(a)} != {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                drifts += _numeric_drifts(x, y, f"{path}[{i}]", rel_tol=rel_tol, abs_tol=abs_tol)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a is not b:
            drifts.append(f"{path}: {a!r} != {b!r}")
    elif isinstance(a, float) or isinstance(b, float):
        if not math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol):
            drifts.append(f"{path}: {a!r} != {b!r} (rel {abs(a-b)/max(abs(a),abs(b),1e-12):.1e})")
    elif a != b:
        drifts.append(f"{path}: {a!r} != {b!r}")
    return drifts


def _read_sse(response) -> list[tuple[str, dict]]:
    """Parse a newline-framed SSE stream into (event_name, data) tuples."""
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    for raw in response:
        line = raw.decode("utf-8").rstrip("\n")
        if line.startswith("event: "):
            current_event = line[len("event: "):]
        elif line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"_raw": payload}
            events.append((current_event or "message", data))
            current_event = None
    return events


class _EngineTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = build_engine_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.token = cls.server.session_token  # type: ignore[attr-defined]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    # -- request helpers --------------------------------------------------- #

    def _headers(self, *, with_token: bool = True, accept: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if with_token:
            headers["Authorization"] = f"Bearer {self.token}"
        if accept:
            headers["Accept"] = accept
        return headers

    def get(self, path: str, *, with_token: bool = True):
        req = urllib.request.Request(self.base + path, headers=self._headers(with_token=with_token))
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def post(self, path: str, body: dict, *, with_token: bool = True, accept: str | None = None):
        headers = self._headers(with_token=with_token, accept=accept)
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=180)
        if accept == "text/event-stream":
            return resp  # caller streams it
        with resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def load_world(self) -> str:
        status, payload = self.post(
            "/world/load",
            {"state_csv": STATE_CSV, "state_year": 2026, "max_countries": None},
        )
        self.assertEqual(status, 200)
        return payload["world_key"]


class EngineSmokeTests(_EngineTestBase):
    def test_healthz_requires_token(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/healthz", with_token=False)
        self.assertEqual(ctx.exception.code, 401)

    def test_healthz_ready_payload(self) -> None:
        status, payload = self.get("/healthz")
        self.assertEqual(status, 200)
        for field in ("ready", "schema", "port", "token", "pid", "gim_version", "offline"):
            self.assertIn(field, payload)
        self.assertEqual(payload["schema"], "gim-engine/1")
        self.assertTrue(payload["offline"])

    def test_world_load_returns_key_and_catalog(self) -> None:
        status, payload = self.post(
            "/world/load", {"state_csv": STATE_CSV, "state_year": 2026, "max_countries": None}
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["world_key"].startswith("w_"))
        self.assertEqual(payload["schema"], "gim-engine/1")
        names = {actor["name"] for actor in payload["actors"]}
        self.assertIn("United States", names)
        self.assertTrue(payload["personas"])

    def test_actors_endpoint(self) -> None:
        world_key = self.load_world()
        status, payload = self.get(f"/actors?world_key={world_key}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema"], "gim-engine/1")
        self.assertTrue(any(a["name"] == "United States" for a in payload["actors"]))

    def test_actors_requires_token(self) -> None:
        world_key = self.load_world()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get(f"/actors?world_key={world_key}", with_token=False)
        self.assertEqual(ctx.exception.code, 401)

    def test_personas_catalog(self) -> None:
        status, payload = self.get("/personas")
        self.assertEqual(status, 200)
        ids = {p["id"] for p in payload["personas"]}
        self.assertIn("dove", ids)
        self.assertIn("hawk_protectionist", ids)

    def test_persona_doctrine_preview(self) -> None:
        world_key = self.load_world()
        status, payload = self.get(
            f"/personas/dove/doctrine?world_key={world_key}&country={quote('United States')}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["persona_id"], "dove")
        self.assertIn("base", payload)
        self.assertIn("shifted", payload)
        self.assertIn("deltas", payload)

    def test_persona_doctrine_unknown_country(self) -> None:
        world_key = self.load_world()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get(f"/personas/dove/doctrine?world_key={world_key}&country=Atlantis")
        self.assertEqual(ctx.exception.code, 400)

    def test_metrics_snapshot(self) -> None:
        world_key = self.load_world()
        status, payload = self.get(
            f"/metrics?world_key={world_key}&agents={quote('United States,Iran')}"
        )
        self.assertEqual(status, 200)
        self.assertIn("global_context", payload["metrics"])
        self.assertEqual(len(payload["metrics"]["agents"]), 2)

    def test_unknown_world_key_is_404(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/actors?world_key=w_doesnotexist")
        self.assertEqual(ctx.exception.code, 404)

    def test_whatif_sync_projection_shape(self) -> None:
        world_key = self.load_world()
        status, result = self.post(
            "/run/whatif",
            {
                "world_key": world_key,
                "question": "How will Hormuz tensions escalate?",
                "actors": ["Iran", "United States", "Israel"],
                "horizon": 2,
                "seed": 2026,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["mode"], "whatif")
        self.assertEqual(result["schema"], "gim-engine/1")
        for field in ("verdict", "criticality", "outcomes", "drivers", "years", "series", "trace"):
            self.assertIn(field, result)
        self.assertTrue(result["outcomes"])
        self.assertIn(result["outcomes"][0]["valence"], {"good", "warn", "bad"})
        self.assertIn("gdp", result["series"])
        self.assertIn("equiv_cli", result["trace"])
        self.assertTrue(result["trace"]["equiv_cli"].startswith("python3 -m gim question"))

    def test_run_without_world_key_is_400(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/run/whatif", {"question": "x", "horizon": 0})
        self.assertEqual(ctx.exception.code, 400)

    def test_export_evaluation_roundtrip(self) -> None:
        world_key = self.load_world()
        _status, result = self.post(
            "/run/whatif",
            {
                "world_key": world_key,
                "question": "How will Hormuz tensions escalate?",
                "actors": ["Iran", "United States", "Israel"],
                "horizon": 1,
                "seed": 2026,
            },
        )
        run_id = result["trace"]["run_id"]
        status, payload = self.get(f"/export/evaluation?run_id={run_id}")
        self.assertEqual(status, 200)
        self.assertIn("evaluation", payload)
        self.assertIn("trajectory", payload)


class EngineStreamingTests(_EngineTestBase):
    def test_whatif_sse_emits_progress_then_one_result(self) -> None:
        world_key = self.load_world()
        response = self.post(
            "/run/whatif",
            {
                "world_key": world_key,
                "question": "How will Hormuz tensions escalate?",
                "actors": ["Iran", "United States", "Israel"],
                "horizon": 2,
                "seed": 2026,
            },
            accept="text/event-stream",
        )
        events = _read_sse(response)
        names = [name for name, _ in events]
        self.assertGreaterEqual(names.count("progress"), 1, names)
        self.assertEqual(names.count("result"), 1, names)
        self.assertEqual(names[-1], "result")
        # progress events carry the 8-phase mapping fields.
        first_progress = next(data for name, data in events if name == "progress")
        for field in ("percent", "step_index", "step_total", "message"):
            self.assertIn(field, first_progress)
        self.assertEqual(first_progress["step_total"], 8)


class EngineCancelTests(_EngineTestBase):
    def test_game_stream_can_be_cancelled(self) -> None:
        world_key = self.load_world()
        case_path = REPO_ROOT / "scenarios" / "maritime_pressure_game.json"
        self.assertTrue(case_path.exists(), "expected bundled maritime game case")

        captured: dict[str, object] = {}

        def stream() -> None:
            response = self.post(
                "/run/game",
                {
                    "world_key": world_key,
                    "case": "scenarios/maritime_pressure_game.json",
                    "horizon": 2,
                    "equilibrium": False,
                    "max_combinations": 4,  # tiny action space → fast, cancellable
                    "seed": 2026,
                },
                accept="text/event-stream",
            )
            captured["events"] = _read_sse(response)

        worker = threading.Thread(target=stream)
        worker.start()

        # Wait until at least one progress event has been observed, then cancel.
        run_id = self._await_first_run_id(timeout=30.0)
        self.assertIsNotNone(run_id, "no game run registered in time")
        status, payload = self.post(f"/run/{run_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertTrue(payload["cancelled"])

        worker.join(timeout=90.0)
        self.assertFalse(worker.is_alive(), "streaming worker did not finish after cancel")
        events = captured.get("events", [])
        names = [name for name, _ in events]  # type: ignore[union-attr]
        # The stream must terminate with a cancelled error, not a result.
        self.assertIn("error", names, names)
        error_data = next(data for name, data in events if name == "error")  # type: ignore[union-attr]
        self.assertEqual(error_data["code"], "cancelled")
        self.assertNotIn("result", names, names)

    def _await_first_run_id(self, timeout: float) -> str | None:
        """Poll the engine's run registry for the first game run to appear."""
        from gim import engine_service

        deadline = time.time() + timeout
        while time.time() < deadline:
            with engine_service._RUNS_LOCK:
                for run in engine_service._RUNS.values():
                    if run.mode == "game":
                        return run.run_id
            time.sleep(0.1)
        return None


class EngineParityTests(_EngineTestBase):
    """The core anti-drift guarantee (contract §6)."""

    def test_whatif_result_matches_equiv_cli_json(self) -> None:
        world_key = self.load_world()
        _status, result = self.post(
            "/run/whatif",
            {
                "world_key": world_key,
                "question": "How will Hormuz tensions escalate?",
                "actors": ["Iran", "United States", "Israel"],
                "horizon": 3,
                "seed": 2026,
            },
        )
        engine_evaluation = result["evaluation"]
        equiv_cli = result["trace"]["equiv_cli"]
        self.assertTrue(equiv_cli.startswith("python3 -m gim question"))

        # Run the exact CLI the engine reports and compare its --json evaluation.
        argv = shlex.split(equiv_cli)
        argv[0] = sys.executable  # use this interpreter, not whatever "python3" resolves to
        completed = subprocess.run(
            argv, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        cli_evaluation = json.loads(completed.stdout)

        # No math drift between the engine and the equivalent CLI. We assert NUMERIC agreement
        # (not bitwise): both build a fresh world and run identical code, but the 3-year sim
        # contains float reductions whose summation order depends on object allocation order,
        # which differs between the in-process engine and the CLI subprocess. That makes the last
        # ~1e-15 bit non-reproducible *across processes* (IEEE-754 non-associativity), which is
        # not "drift". A tight relative tolerance (1e-9) ignores that last-bit noise while still
        # catching any genuine divergence (a real code/data drift moves values by >=1e-6).
        # Structure, strings, ints, and booleans must still match exactly.
        # (run_id / elapsed_ms / timestamps live only in the engine's trace block, excluded here.)
        drifts = _numeric_drifts(engine_evaluation, cli_evaluation)
        self.assertEqual(
            drifts, [], "engine What-if evaluation drifted from the equivalent CLI --json output:\n"
            + "\n".join(drifts[:20]),
        )

    def test_world_for_key_returns_isolated_copy(self) -> None:
        # Anti-drift regression (contract §6): every run must receive a PRIVATE, freshly built
        # world so that stepping it in place cannot leak into a later run. Previously run handlers
        # shared the cached world instance; once a prior run mutated it, the parity test above
        # diverged from the always-fresh CLI in full-suite order. _world_for_key now rebuilds.
        from gim import engine_service as es

        world_key = self.load_world()
        w1 = es._world_for_key(world_key)
        w2 = es._world_for_key(world_key)
        self.assertIsNot(w1, w2)  # distinct private copies
        aid = next(iter(w1.agents))
        baseline = w2.agents[aid].economy.gdp
        w1.agents[aid].economy.gdp = baseline + 123.0  # mutate one copy
        w3 = es._world_for_key(world_key)
        self.assertEqual(w3.agents[aid].economy.gdp, baseline)  # cache stayed pristine


if __name__ == "__main__":
    unittest.main()
