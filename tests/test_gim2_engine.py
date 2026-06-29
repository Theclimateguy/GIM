"""THE-65 — deterministic engine API + reproducible CLI + parity.

Asserts ``compute_* == CLI == engine`` for the deterministic modes (the parity
guarantee), plus auth, meta endpoints and an SSE round-trip.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import threading

import pytest

from gim2 import scenario as S
from gim2.engine_service import build_engine_server


# --------------------------------------------------------------------------- #
# in-process engine server
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def engine():
    server = build_engine_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.ready_payload["port"], server.ready_payload["token"]  # type: ignore[attr-defined]
    finally:
        server.shutdown()
        server.server_close()


def _post(port, token, path, body, *, sse=False):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if sse:
        headers["Accept"] = "text/event-stream"
    conn.request("POST", path, body=json.dumps(body), headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    conn.close()
    return resp.status, raw


def _get(port, token, path, *, auth=True):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    headers = {"Authorization": f"Bearer {token}"} if auth else {}
    conn.request("GET", path, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    conn.close()
    return resp.status, raw


def _strip(d: dict) -> dict:
    d = dict(d)
    d.pop("trace", None)
    d.pop("equiv_cli", None)
    return d


# --------------------------------------------------------------------------- #
# parity: compute_* == CLI == engine
# --------------------------------------------------------------------------- #


def test_parity_ensemble():
    kw = dict(state_csv=None, members=4, years=4, max_agents=8, seed=2026, prior_set="key", jobs=1)
    direct = S.compute_ensemble(**kw)
    cli = S.run_ensemble_cli(argparse.Namespace(state_year=None, **kw))
    assert _strip(cli) == direct
    with engine() as (port, token):
        status, raw = _post(port, token, "/run/ensemble", {**kw})
    assert status == 200
    assert _strip(json.loads(raw)) == direct


def test_parity_scenario():
    kw = dict(state_csv=None, members=4, years=4, max_agents=8, seed=2026, prior_set="key", jobs=1)
    direct = S.compute_scenario(levers=["decarbonization"], magnitude=1.0, actors=None, **kw)
    cli = S.run_scenario_cli(argparse.Namespace(
        state_year=None, lever=["decarbonization"], magnitude=1.0, actors=None, **kw))
    assert _strip(cli) == direct
    with engine() as (port, token):
        status, raw = _post(port, token, "/run/scenario",
                            {"levers": ["decarbonization"], "magnitude": 1.0, **kw})
    assert status == 200
    assert _strip(json.loads(raw)) == direct


def test_parity_sensitivity():
    kw = dict(state_csv=None, metric="co2", years=3, params=None, r=2, levels=4, max_agents=8, seed=2026)
    direct = S.compute_sensitivity(**kw)
    cli = S.run_sensitivity_cli(argparse.Namespace(state_year=None, **kw))
    assert _strip(cli) == direct
    with engine() as (port, token):
        status, raw = _post(port, token, "/run/sensitivity", {**kw})
    assert status == 200
    assert _strip(json.loads(raw)) == direct


# --------------------------------------------------------------------------- #
# endpoints: meta / ontology / auth / cancel-route
# --------------------------------------------------------------------------- #


def test_meta_conflict_auc_endpoint():
    with engine() as (port, token):
        status, raw = _get(port, token, "/meta/conflict_auc")
    assert status == 200
    d = json.loads(raw)
    assert d["projection"]["auc"] == pytest.approx(0.736)


def test_ontology_endpoint_lists_grounded_levers():
    with engine() as (port, token):
        status, raw = _get(port, token, "/ontology?max_agents=12")
    assert status == 200
    ids = {lever["id"] for lever in json.loads(raw)["ontology"]["levers"]}
    assert {"carbon_price", "energy_shock", "stagflation"} <= ids


def test_unauthorized_is_401():
    with engine() as (port, token):
        status, _ = _get(port, token, "/healthz", auth=False)
    assert status == 401


def test_v2_engine_exposes_no_exploratory_routes():
    # THE-71: the v2 surface has no softmax game / criticality / persona modes.
    with engine() as (port, token):
        status, _ = _get(port, token, "/healthz")
        assert status == 200
        for mode in ("whatif", "play", "composed", "game"):
            st, _raw = _post(port, token, f"/run/{mode}",
                             {"members": 2, "years": 2, "max_agents": 8, "jobs": 1})
            assert st == 404, f"exploratory mode {mode} must not be a v2 route"


def test_unknown_lever_is_bad_request():
    with engine() as (port, token):
        status, raw = _post(port, token, "/run/scenario",
                            {"levers": ["not_a_lever"], "members": 2, "years": 2, "max_agents": 8, "jobs": 1})
    assert status == 400
    assert "unknown lever" in json.loads(raw)["error"]["message"]


# --------------------------------------------------------------------------- #
# SSE round-trip (progress + terminal result)
# --------------------------------------------------------------------------- #


def test_sse_scenario_streams_progress_and_result():
    with engine() as (port, token):
        status, raw = _post(port, token, "/run/scenario",
                            {"levers": ["energy_shock"], "members": 3, "years": 3, "max_agents": 8, "jobs": 1},
                            sse=True)
    assert status == 200
    events = [blk for blk in raw.split("\n\n") if blk.strip()]
    kinds = [e.split("event:", 1)[1].split("\n", 1)[0].strip() for e in events if "event:" in e]
    assert "result" in kinds
    assert kinds.count("progress") >= 1
    result_blk = next(e for e in events if "event: result" in e)
    payload = json.loads(result_blk.split("data:", 1)[1].strip())
    assert payload["mode"] == "scenario"
