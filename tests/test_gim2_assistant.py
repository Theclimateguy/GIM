"""v2 assistant — deterministic NL router → run_answer, and the /assistant SSE route.

Routing is unit-tested with a fake executor (fast); the heavy compute_answer path it
routes into is already covered by tests/test_gim2_answer.py.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import threading

from gim2.assistant import AssistantConfig, run_assistant_turn
from gim2.engine_service import build_engine_server


def _drive(text: str):
    events: list = []
    calls: list = []

    def emit(ev, data):
        events.append((ev, data))

    def executor(name, args):
        calls.append((name, args))
        if name == "run_answer":
            return {"summary": "ок", "result": {"mode": "answer", "verdict": "v",
                                                "actors": {"leaders": [], "laggards": []}}}
        return {"summary": "list", "result": None}

    run_assistant_turn([{"role": "user", "content": text}],
                       AssistantConfig(provider="deterministic"), executor, emit)
    return events, calls


def test_router_matches_archetype():
    events, calls = _drive("что если начнётся энергетическая война?")
    assert calls and calls[0][0] == "run_answer"
    assert calls[0][1].get("archetype") == "energy_war"
    assert any(ev == "run_result" for ev, _ in events)


def test_router_composes_levers_when_no_archetype():
    events, calls = _drive("резкий рост цен на нефть и газ")
    assert calls and calls[0][0] == "run_answer"
    levers = calls[0][1].get("levers")
    assert levers and any(l["lever"] == "energy_shock" for l in levers)
    assert calls[0][1].get("archetype") is None


def test_router_help_when_no_match():
    events, calls = _drive("привет, как дела")
    assert not any(name == "run_answer" for name, _ in calls)
    assert any(ev == "assistant_delta" for ev, _ in events)
    assert not any(ev == "run_result" for ev, _ in events)


# --------------------------------------------------------------------------- #
# /assistant SSE endpoint (help path — no engine run, fast)
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def _engine():
    server = build_engine_server("127.0.0.1", 0)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield server.ready_payload["port"], server.ready_payload["token"]  # type: ignore[attr-defined]
    finally:
        server.shutdown()
        server.server_close()


def test_assistant_endpoint_streams_sse():
    with _engine() as (port, token):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        body = json.dumps({"provider": "deterministic",
                           "messages": [{"role": "user", "content": "привет"}]})
        conn.request("POST", "/assistant", body=body,
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                              "Accept": "text/event-stream"})
        raw = conn.getresponse().read().decode()
        conn.close()
    kinds = [b.split("event:", 1)[1].split("\n", 1)[0].strip() for b in raw.split("\n\n") if "event:" in b]
    assert "assistant_delta" in kinds and "done" in kinds
