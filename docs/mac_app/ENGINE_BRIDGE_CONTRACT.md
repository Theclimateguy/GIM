# GIM17 macOS — Engine Bridge Contract (Stage 0)

Status: design/spec. The seam between the **SwiftUI app** and the **embedded Python engine**
(`gim-engine` sidecar). The engine is a thin wrapper over the *unchanged* in-process API in `gim/`;
it adds no model math. All function references below already exist in the repo.

Контракт намеренно тонкий: приложение рендерит JSON, движок считает. Воспроизводимость и весь расчёт
остаются на стороне Python (источник истины — `gim/`).

---

## 1. Transport & security

- **Loopback only.** Engine binds `127.0.0.1` on an **ephemeral port** (`:0` → OS-assigned). Never
  binds a routable interface. No CORS; not a network service.
- **Per-session token.** On startup the engine generates a random 256-bit token. Every request must
  carry `Authorization: Bearer <token>`. Requests without it → `401`.
- **Handshake.** The app spawns the engine and reads **one line of JSON on stdout**, then stops
  reading stdout (logs go to stderr):
  ```json
  {"ready": true, "schema": "gim-engine/1", "port": 51734, "token": "…", "pid": 4123,
   "gim_version": "17.2.0", "offline": true}
  ```
  If no ready-line within 15 s → app surfaces an engine-launch error.
- **Lifecycle.** App owns the process: terminates the engine on quit; engine self-exits if its parent
  dies (parent-pid watchdog). Single client assumed (the app).
- **Streaming.** Long calls use **SSE** (`Content-Type: text/event-stream`). Light calls are plain
  JSON. Cancellation is a separate `POST …/cancel`.

---

## 2. Conventions

- JSON, UTF-8. Snake_case keys (mirror the Python dataclasses via `dataclasses.asdict`).
- **Versioning:** every response carries `"schema": "gim-engine/1"`. Breaking change → bump.
- **World handle:** a run targets a loaded world identified by `world_key` (see `/world/load`). The
  engine keeps an LRU of `WorldState` objects (mirrors `_WORLD_CACHE` in `gim/ui_server.py`), so
  repeated light calls are <1 s.
- **Error shape** (any non-2xx):
  ```json
  {"error": {"code": "unknown_country", "message": "…", "detail": {…}}, "schema": "gim-engine/1"}
  ```
- **Determinism:** identical request (same `world_key`, params, `seed`) ⇒ identical payload. Each
  result echoes a `trace` block (below) for reproducibility.

### `trace` block (on every run result)
```json
"trace": {"run_id": "whatif-20260626-143012", "equiv_cli": "python3 -m gim question --question … --sim --horizon 3",
          "seed": 2026, "artifacts_dir": "results/whatif-20260626-143012", "elapsed_ms": 870}
```
`equiv_cli` is the exact CLI that reproduces the run (powers the muted trace line in the UI; honesty).

---

## 3. Endpoints

### Health & world
| Method · Path | Purpose | Wraps (existing) |
|---|---|---|
| `GET /healthz` | liveness; returns ready-line payload | — |
| `POST /world/load` | load/cache a world, return `world_key` + actor/persona catalog | `runtime.load_world` |
| `GET /actors?world_key=` | actor list (id, name, label) | `scenario_compiler.resolve_actor_names`, CSV scan |
| `GET /personas` | persona archetype catalog | `persona.list_personas().to_payload()` |
| `GET /personas/{id}/doctrine?world_key=&country=` | base→shift doctrine preview | `CompiledLLMPolicyManager(prefer_llm=False).doctrine_preview` + `core.observation.build_observation` |
| `GET /metrics?world_key=&agents=` | crisis snapshot (0.2 s) | `CrisisMetricsEngine().compute_dashboard` |

`POST /world/load` request:
```json
{"state_csv": "data/agent_states_operational.csv", "state_year": 2023, "max_countries": null}
```
Response: `{"world_key":"w_8f3…","state_year":2026,"actors":[…],"personas":[…],"schema":"gim-engine/1"}`

### Runs (the four modes)

All run endpoints accept a common envelope and stream progress over SSE, then end with a terminal
`result` event. `Accept: text/event-stream` ⇒ SSE; otherwise the engine runs sync and returns the
final JSON (used by light What-if and by parity tests).

Common run fields: `world_key`, `seed?`, `horizon` (years), `background_policy`
(`compiled-llm|llm|simple|growth`, default `compiled-llm`), `llm_refresh`
(`trigger|periodic|never`), `llm_refresh_years?`.

| Method · Path | Mode | Wraps (existing) | Latency |
|---|---|---|---|
| `POST /run/whatif` | What if… | `compile_question` → `SimBridge.evaluate_scenario(progress_callback=…)` (or static `GameRunner.evaluate_scenario` when `horizon=0`) | 0.6–1 s |
| `POST /run/play` | Play as a country | `HybridSimulator.run_round(…)` → `hybrid_result_payload` + intents feed | seconds |
| `POST /run/game` | Game / equilibrium | `SimBridge.run_game(progress_callback=…)` + `run_equilibrium_search` | ~10–73 s |
| `POST /run/compare` | Compare 2–3 runs | diff of stored `evaluation.json` (see `ui_server._compare_payload`) | instant |
| `POST /run/{run_id}/cancel` | cancel a streaming run | cooperative flag checked in `progress_callback` | — |

`POST /run/whatif` request:
```json
{"world_key":"w_8f3…","question":"How will Red Sea tensions escalate?","actors":["Iran","United States","Israel"],
 "template":null,"horizon":3,"background_policy":"compiled-llm","llm_refresh":"trigger","seed":2026}
```

`POST /run/play` request (persona biases compiled doctrine — not an override):
```json
{"world_key":"w_8f3…","country":"United States","persona":"protectionist_hawk",
 "goal":"Pressure China on trade, seek a deal","mode":"WHAT_IF","round_years":4,"ensemble_size":3,"seed":2026}
```
`mode` ∈ {`ACTION`,`WHAT_IF`} (`hybrid_simulator.HUMAN_MODE_*`). Persona → `augment_intent` into the
table intent; background countries run `background_policy`.

`POST /run/game` request:
```json
{"world_key":"w_8f3…","case":"scenarios/maritime_pressure_game.json","description":null,"horizon":3,
 "equilibrium":true,"episodes":50,"threshold":0.02,"trust_alpha":0.5,"max_combinations":256,"seed":2026}
```
(`case` xor `description`; `description` builds a case via `case_builder.build_case_from_text`.)

### Export
| Method · Path | Returns |
|---|---|
| `GET /export/brief?run_id=` | `decision_brief.md` (`AnalyticsBriefRenderer`) |
| `GET /export/dashboard?run_id=` | `dashboard.html` (`DashboardRenderer`) |
| `GET /export/csv?run_id=&kind=world\|actions\|institutions` | run CSV logs |
| `GET /export/evaluation?run_id=` | raw `evaluation.json` |

---

## 4. SSE event stream (run endpoints)

Newline-framed SSE. Event names: `progress`, `intent` (play only), `result`, `error`.

```
event: progress
data: {"run_id":"whatif-…","percent":42,"step_index":4,"step_total":8,"message":"economy"}

event: intent
data: {"agent_id":"USA","agent_name":"United States","posture":"Pressuring China on trade; seeking a deal",
       "tags":["trade","sanctions"],"intensity":"moderate","actions":["sanctions→CHN","trade_restrict→CHN"]}

event: result
data: { …full mode payload incl. trace… }
```

- `progress` is fed by the existing `SimProgress(percent, message)` callback in `gim/sim_bridge.py`;
  `step_index/step_total` mirror the 8-phase pipeline (`baseline → resolve_foreign_policy → sanctions →
  resource → economy → migration → reconcile → credit`), as already parsed in `ui_server._update_progress`.
- `intent` events power the CICERO-style "stated intent → actions" feed (`play` mode), sourced from
  `hybrid_result.intents` + `effective_actions_by_agent` (see `ui_server._intents_feed_payload`).
- Exactly one terminal `result` **or** `error`.
- **Cancel:** `POST /run/{run_id}/cancel` sets a cooperative flag; the `progress_callback` raises
  `RunCancelled`; the stream ends with `error{code:"cancelled"}`. (Equilibrium 73 s ⇒ cancel matters.)

---

## 5. Result payloads (shapes the UI renders)

Engine echoes the Python dataclasses; the UI reads a stable projection (same fields the current web UI
derives in `ui_server._analytics_payload_from_evaluation_path`). Minimum the Situation Room needs:

```json
{"mode":"whatif","schema":"gim-engine/1","trace":{…},
 "verdict":"Скорее деэскалация, чем срыв — при удержании пролива.",
 "criticality":0.38,
 "outcomes":[{"name":"Status quo","value":0.46,"valence":"good"},
             {"name":"Proxy escalation","value":0.21,"valence":"bad"}],
 "drivers":[{"name":"Oil market stress","value":0.62},{"name":"Sanctions footprint","value":0.41}],
 "years":[2026,2027,2028,2029],
 "series":{"gdp":[{"id":"USA","name":"United States","baseline":[100,101,…],"policy":[100,99,…]}],
           "social_tension":[…],"prices":{"energy":[…],"food":[…],"metals":[…]}},
 "intents_feed":[…]   // play mode only
}
```

`valence` ∈ {`good`,`warn`,`bad`} drives the weather-forecast colors. `baseline` vs `policy` realizes
the "always current-vs-baseline" design principle (data already in `evaluation.json` trajectory).

---

## 6. Parity guarantee (Stage 8 hook)

For any run, `result` minus volatile fields (timestamps, `run_id`, `elapsed_ms`) must equal the
`--json` output of the `equiv_cli` it reports. The parity test asserts this on a fixed matrix
(Hormuz what-if, US-hawk play, maritime game) → proves the app introduces **no math drift** vs v17.2.0.
