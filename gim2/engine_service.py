"""GIM17 v2 deterministic engine sidecar (THE-65).

A loopback HTTP+SSE service that surfaces the *validated* deterministic modes for
the v2 app. It calls the **same** ``gim2.scenario.compute_*`` / ``gim2.dose_response``
functions the CLI calls, so ``engine JSON == CLI JSON`` by construction (parity
test). No model math here — pure transport + projection.

Endpoints
---------
POST ``/run/ensemble`` ``/run/scenario`` ``/run/dose_response`` ``/run/sensitivity``
``/run/weak_signals``  — JSON body; SSE (``Accept: text/event-stream``) streams
``progress`` then a terminal ``result`` for the heavy modes.
POST ``/run/<id>/cancel`` — cooperative cancel.
GET  ``/meta/scc`` ``/meta/backtest`` ``/meta/conflict_auc`` ``/ontology`` ``/healthz``.

Transport mirrors v1: binds 127.0.0.1 on an ephemeral port, requires a per-session
bearer token, prints one ready-line of JSON on stdout, logs to stderr, self-exits
if the parent dies. SSE is **close-delimited** (the v1 gotcha): ``Connection: close``.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from . import SCHEMA, __version__, is_exploratory_enabled
from . import archetypes as _archetypes
from . import levers as L
from . import scenario as S
from .answer import compute_answer
from .assistant import AssistantConfig, run_assistant_turn
from .dose_response import compute_dose
from .runtime import load_world_for  # local light loader (no v1 world cache)


# --------------------------------------------------------------------------- #
# run registry (cancel flags)
# --------------------------------------------------------------------------- #


class EngineRun:
    def __init__(self, run_id: str, mode: str) -> None:
        self.run_id = run_id
        self.mode = mode
        self.cancelled = threading.Event()
        self.started_at = time.time()


_RUNS: Dict[str, EngineRun] = {}
_RUNS_LOCK = threading.Lock()


def _new_run(mode: str) -> EngineRun:
    run_id = f"{mode}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run = EngineRun(run_id, mode)
    with _RUNS_LOCK:
        _RUNS[run_id] = run
    return run


def _get_run(run_id: str) -> Optional[EngineRun]:
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


# --------------------------------------------------------------------------- #
# body -> compute_* arg adapters (defaults mirror the compute_* signatures)
# --------------------------------------------------------------------------- #


def _members(body: Dict[str, Any], default: int) -> int:
    return int(body.get("members", body.get("n_members", default)) or default)


def _run_ensemble(body, progress, cancel):
    return S.compute_ensemble(
        state_csv=body.get("state_csv"), members=_members(body, 200), years=int(body.get("years", 10)),
        max_agents=int(body.get("max_agents", 100)), seed=int(body.get("seed", 2026)),
        prior_set=str(body.get("prior_set", "key")), jobs=int(body.get("jobs", 0)),
        progress=progress, cancel=cancel,
    )


def _run_scenario(body, progress, cancel):
    return S.compute_scenario(
        state_csv=body.get("state_csv"), levers=body.get("levers", []), magnitude=body.get("magnitude"),
        actors=body.get("actors"), members=_members(body, 200), years=int(body.get("years", 10)),
        max_agents=int(body.get("max_agents", 100)), seed=int(body.get("seed", 2026)),
        prior_set=str(body.get("prior_set", "key")), jobs=int(body.get("jobs", 0)),
        progress=progress, cancel=cancel,
    )


def _run_dose(body, progress, cancel):
    return compute_dose(
        state_csv=body.get("state_csv"), lever=str(body.get("lever", "")),
        grid=body.get("grid", [0.0, 0.25, 0.5, 0.75, 1.0, 1.25]), metric=str(body.get("metric", "world_gdp")),
        actors=body.get("actors"), members=_members(body, 120), years=int(body.get("years", 10)),
        max_agents=int(body.get("max_agents", 100)), seed=int(body.get("seed", 2026)),
        progress=progress, cancel=cancel,
    )


def _run_sensitivity(body, progress, cancel):
    return S.compute_sensitivity(
        state_csv=body.get("state_csv"), metric=str(body.get("metric", "world_gdp")),
        years=int(body.get("years", 10)), params=body.get("params"), r=int(body.get("r", 10)),
        levels=int(body.get("levels", 4)), max_agents=int(body.get("max_agents", 100)),
        seed=int(body.get("seed", 2026)),
    )


def _run_weak(body, progress, cancel):
    return S.compute_weak(
        state_csv=body.get("state_csv"), levers=body.get("levers", []), magnitude=body.get("magnitude"),
        actors=body.get("actors"), years=int(body.get("years", 12)),
        max_agents=int(body.get("max_agents", 100)), seed=int(body.get("seed", 2026)),
    )


def _run_answer(body, progress, cancel):
    return compute_answer(
        state_csv=body.get("state_csv"), archetype=body.get("archetype"),
        levers=body.get("levers", []), magnitude=body.get("magnitude"), actors=body.get("actors"),
        members=_members(body, 160), years=int(body.get("years", 10)),
        max_agents=int(body.get("max_agents", 100)), seed=int(body.get("seed", 2026)),
        jobs=int(body.get("jobs", 0)), threshold_lever=body.get("threshold_lever"),
        threshold_metric=body.get("threshold_metric"),
        threshold_members=int(body.get("threshold_members", 100)),
        cascade_members=int(body.get("cascade_members", 24)),
        progress=progress, cancel=cancel,
    )


_RUN_DISPATCH: Dict[str, Callable[[Dict[str, Any], Any, Any], Dict[str, Any]]] = {
    "ensemble": _run_ensemble,
    "scenario": _run_scenario,
    "dose_response": _run_dose,
    "sensitivity": _run_sensitivity,
    "weak_signals": _run_weak,
    "answer": _run_answer,
}
_HEAVY = {"ensemble", "scenario", "dose_response", "answer"}


# --------------------------------------------------------------------------- #
# assistant (NL → run_answer); numbers always engine-produced
# --------------------------------------------------------------------------- #


def _summarize_answer(r: Dict[str, Any]) -> str:
    parts = [str(r.get("verdict", ""))]
    actors = r.get("actors", {}) or {}
    if actors.get("leaders"):
        parts.append("В выигрыше: " + ", ".join(l["name"] for l in actors["leaders"][:3]))
    if actors.get("laggards"):
        parts.append("В проигрыше: " + ", ".join(l["name"] for l in actors["laggards"][:3]))
    th = r.get("threshold") or {}
    if th.get("note"):
        parts.append(str(th["note"]))
    return " · ".join(p for p in parts if p)


def _assistant_executor(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if name == "list_archetypes":
            cat = _archetypes.catalog()
            lines = [f"{a['id']} — {a['name_ru']}: {a['description']}" for a in cat["archetypes"]]
            return {"summary": "Типовые сценарии:\n" + "\n".join(lines), "result": None}
        if name == "list_levers":
            spec = L.ontology_spec()
            lines = [f"{lv['id']} — {lv['label_ru']}" for lv in spec["levers"]]
            return {"summary": "Заземлённые рычаги: " + ", ".join(lines), "result": None}
        if name == "run_answer":
            archetype = args.get("archetype") or None
            actors = args.get("actors") or None
            question = str(args.get("question") or "")
            items: list = []
            if not archetype:
                if args.get("levers"):
                    items = args["levers"]
                elif question:
                    items = [{"lever": lev} for lev in L.match_levers(question)]
                if not items:
                    return {"summary": "Уточните: какой шок или какой типовой сценарий запустить?",
                            "result": None}
            result = compute_answer(archetype=archetype, levers=items, actors=actors,
                                    members=24, years=8, max_agents=57,
                                    threshold_members=16, cascade_members=20)
            return {"summary": _summarize_answer(result), "result": result}
    except (ValueError, KeyError) as exc:
        return {"summary": f"Не получилось: {exc}", "result": None}
    except Exception as exc:  # noqa: BLE001
        return {"summary": f"Ошибка инструмента {name}: {exc}", "result": None}
    return {"summary": f"unknown tool: {name}", "result": None}


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #


class EngineHandler(BaseHTTPRequestHandler):
    server_version = "GIM17EngineV2/2.0"

    @property
    def _token(self) -> str:
        return self.server.session_token  # type: ignore[attr-defined]

    @property
    def _ready(self) -> Dict[str, Any]:
        return self.server.ready_payload  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("[engine-v2] " + (fmt % args) + "\n")

    # -- helpers ----------------------------------------------------------- #

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return secrets.compare_digest(header[len("Bearer "):].strip(), self._token)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, code: str, message: str, status: int, detail: Any = None) -> None:
        self._send_json({"error": {"code": code, "message": message, "detail": detail}, "schema": SCHEMA}, status)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def _wants_sse(self) -> bool:
        return "text/event-stream" in (self.headers.get("Accept", "") or "")

    def _sse_start(self) -> None:
        self.close_connection = True  # close-delimited stream (v1 gotcha)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _sse_emit(self, event: str, data: Dict[str, Any]) -> None:
        chunk = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(chunk.encode("utf-8"))
        self.wfile.flush()

    # -- GET --------------------------------------------------------------- #

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if not self._authorized():
            self._send_error("unauthorized", "missing or invalid bearer token", 401)
            return
        try:
            if path == "/healthz":
                self._send_json(self._ready)
                return
            if path == "/ontology":
                world = load_world_for(query.get("state_csv", [None])[0],
                                       int(query.get("max_agents", ["57"])[0]))
                self._send_json({"schema": SCHEMA, "ontology": L.ontology_spec(world)})
                return
            if path == "/archetypes":
                segment = query.get("segment", [None])[0]
                self._send_json({"schema": SCHEMA, **_archetypes.catalog(segment)})
                return
            if path.startswith("/meta/"):
                kind = path[len("/meta/"):]
                if kind not in {"scc", "backtest", "conflict_auc"}:
                    self._send_error("not_found", f"unknown meta kind: {kind}", 404)
                    return
                self._send_json(S.compute_meta(kind=kind, state_csv=query.get("state_csv", [None])[0],
                                               max_agents=int(query.get("max_agents", ["100"])[0]),
                                               seed=int(query.get("seed", ["2026"])[0])))
                return
        except (ValueError, KeyError) as exc:
            self._send_error("bad_request", str(exc), 400)
            return
        except Exception as exc:  # noqa: BLE001
            self._send_error("internal", str(exc), 500)
            return
        self._send_error("not_found", f"no route for {path}", 404)

    # -- POST -------------------------------------------------------------- #

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._authorized():
            self._send_error("unauthorized", "missing or invalid bearer token", 401)
            return

        if path == "/assistant":
            self._handle_assistant(self._read_body())
            return

        if path.startswith("/run/") and path.endswith("/cancel"):
            run_id = path[len("/run/"):-len("/cancel")]
            run = _get_run(run_id)
            if run is None:
                self._send_error("unknown_run", f"unknown run_id: {run_id}", 404)
                return
            run.cancelled.set()
            self._send_json({"run_id": run_id, "cancelled": True, "schema": SCHEMA})
            return

        if path.startswith("/run/"):
            mode = path[len("/run/"):]
            if mode not in _RUN_DISPATCH:
                self._send_error("not_found", f"unknown run mode: {mode}", 404)
                return
            body = self._read_body()
            run = _new_run(mode)
            if self._wants_sse():
                self._run_streaming(run, mode, body)
            else:
                self._run_sync(run, mode, body)
            return

        self._send_error("not_found", f"no route for {path}", 404)

    def _handle_assistant(self, body: Dict[str, Any]) -> None:
        config = AssistantConfig(
            provider=str(body.get("provider", "deterministic")),
            model=str(body.get("model", "")),
            api_key=str(body.get("api_key", "")),
            base_url=str(body.get("base_url", "")),
        )
        messages = body.get("messages") or []
        self._sse_start()
        try:
            run_assistant_turn(messages, config, _assistant_executor,
                               lambda ev, data: self._sse_emit(ev, data))
        except Exception as exc:  # noqa: BLE001
            self._sse_emit("error", {"message": str(exc)})

    def _trace(self, run: EngineRun) -> Dict[str, Any]:
        return {"run_id": run.run_id, "elapsed_ms": int((time.time() - run.started_at) * 1000)}

    def _run_sync(self, run: EngineRun, mode: str, body: Dict[str, Any]) -> None:
        try:
            result = _RUN_DISPATCH[mode](body, None, run.cancelled)
        except S.RunCancelled:
            self._send_error("cancelled", "run was cancelled", 409, detail={"run_id": run.run_id})
            return
        except (ValueError, KeyError) as exc:
            self._send_error("bad_request", str(exc), 400, detail={"run_id": run.run_id})
            return
        except Exception as exc:  # noqa: BLE001
            self._send_error("run_failed", str(exc), 500, detail={"run_id": run.run_id})
            return
        result["trace"] = self._trace(run)
        self._send_json(result)

    def _run_streaming(self, run: EngineRun, mode: str, body: Dict[str, Any]) -> None:
        self._sse_start()
        last = {"pct": -1}

        def progress(done: int, total: int) -> None:
            if run.cancelled.is_set():
                raise S.RunCancelled()
            pct = int(100 * done / total) if total else 0
            if pct != last["pct"]:
                last["pct"] = pct
                self._sse_emit("progress", {"run_id": run.run_id, "percent": pct,
                                            "done": done, "total": total})

        prog = progress if mode in _HEAVY else None
        try:
            result = _RUN_DISPATCH[mode](body, prog, run.cancelled)
        except S.RunCancelled:
            self._sse_emit("error", {"run_id": run.run_id, "code": "cancelled", "message": "run was cancelled"})
            return
        except (ValueError, KeyError) as exc:
            self._sse_emit("error", {"run_id": run.run_id, "code": "bad_request", "message": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._sse_emit("error", {"run_id": run.run_id, "code": "run_failed", "message": str(exc)})
            return
        result["trace"] = self._trace(run)
        self._sse_emit("result", result)


# --------------------------------------------------------------------------- #
# lifecycle (token, ready-line, parent watchdog) — mirrors v1
# --------------------------------------------------------------------------- #


def _ready_payload(port: int, token: str) -> Dict[str, Any]:
    return {
        "ready": True, "schema": SCHEMA, "port": port, "token": token, "pid": os.getpid(),
        "gim2_version": __version__, "engine_line": "17.2.0", "offline": True,
        "exploratory": is_exploratory_enabled(),
        "modes": sorted(_RUN_DISPATCH), "meta": ["scc", "backtest", "conflict_auc"],
    }


def _start_parent_watchdog(server: ThreadingHTTPServer) -> None:
    parent_pid = os.getppid()
    if parent_pid <= 1:
        return

    def _watch() -> None:
        while True:
            time.sleep(2.0)
            if os.getppid() != parent_pid:
                sys.stderr.write("[engine-v2] parent gone; shutting down\n")
                try:
                    server.shutdown()
                finally:
                    os._exit(0)

    threading.Thread(target=_watch, name="engine-v2-watchdog", daemon=True).start()


def build_engine_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), EngineHandler)
    token = secrets.token_hex(32)
    server.session_token = token  # type: ignore[attr-defined]
    server.ready_payload = _ready_payload(server.server_address[1], token)  # type: ignore[attr-defined]
    return server


def run_engine_service(host: str = "127.0.0.1", port: int = 0) -> None:
    server = build_engine_server(host, port)
    sys.stdout.write(json.dumps(server.ready_payload, ensure_ascii=False) + "\n")  # type: ignore[attr-defined]
    sys.stdout.flush()
    _start_parent_watchdog(server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_engine_service()
