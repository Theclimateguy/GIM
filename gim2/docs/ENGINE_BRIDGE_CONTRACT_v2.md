# GIM17 v2 engine bridge contract (`gim-engine/2`)

Loopback HTTP+SSE sidecar (`python3 -m gim2 engine`). Deterministic, validated
modes only. Every endpoint emits the **same JSON the CLI prints** (parity).

## Transport

* Binds `127.0.0.1` on an ephemeral port; one ready-line of JSON on **stdout**:
  `{"ready":true,"schema":"gim-engine/2","port":N,"token":"…","gim2_version":"2.0.0-dev","engine_line":"17.2.0","modes":[…],"meta":[…],"offline":true,"exploratory":false}`
* Every request needs `Authorization: Bearer <token>`. 401 otherwise.
* SSE (`Accept: text/event-stream`) is **close-delimited** (`Connection: close`):
  read to EOF. Events: `progress` (heavy modes), then terminal `result` or `error`.
* Logs to **stderr**; self-exits if the parent process dies.

## Run endpoints — `POST /run/<mode>`

| mode | key body fields | projection `kind` |
|---|---|---|
| `ensemble` | members, years, max_agents, seed, prior_set, jobs | `ensemble` |
| `scenario` | levers[], magnitude, actors[], members, years, … | `scenario_delta` (+ baseline/scenario/brief) |
| `dose_response` | lever, grid[], metric, actors[], members, years, … | `dose_response` |
| `sensitivity` | metric, years, params[], r, levels, … | `tornado` |
| `weak_signals` | levers[], magnitude, actors[], years, … | (mahalanobis/breaks/early_warning) |
| `answer` | archetype \| levers[], magnitude, actors[], members, years, threshold_lever/metric | **decision card**: verdict + delta fans + threshold + cascade + brief |

Sync (no SSE) → `{schema, mode, config, projection, …, trace:{run_id, elapsed_ms}}`.
SSE → `progress {percent, done, total}` … then `result` carrying the same object.
Heavy modes (`ensemble`/`scenario`/`dose_response`) stream progress and honour
`POST /run/<run_id>/cancel` (cooperative; `error{code:"cancelled"}`).

## Meta / menu — `GET`

* `/meta/scc` — central SCC at horizons + prior distribution (percentiles).
* `/meta/backtest` — retro 2015–23 RMSE (GDP / CO₂ / temperature) + series.
* `/meta/conflict_auc` — validated AUC 0.736 [0.59, 0.86], p≈0.001 + `compare_to_benchmarks` (`reproduce` pointer; not recomputed per request).
* `/ontology?max_agents=57` — the grounded lever menu (`gim2.levers.ontology_spec`).
* `/archetypes?segment=energy` — the mixed-scenario library + segment profiles (`gim2.archetypes.catalog`).
* `/healthz` — the ready payload.

## Decision card — `POST /run/answer`

The "so-what" assembly (Increment 1): one call answers a strategic question on a
mixed scenario. Body takes either `archetype` (id from `/archetypes`) or explicit
`levers[]`. Returns `{verdict, headline_metric, cards[], projection (delta fans),
threshold{lever, metric, crossing_magnitude, note, curve}, cascade{nodes,affected,
selection_actors}, actors{…}, brief}`. No new math — orchestrates `compute_scenario`
+ `compute_dose` + one shared per-agent ensemble pair (`cascade.run_actor_pair`).

### `actors` block — per-actor states (who wins / who loses)

From the shared per-agent run: each country's terminal Δ across domains + crisis
timeline + a composite winner/loser score.

```
actors:   [{id, name, region, score, verdict (выигрыш|проигрыш|нейтрально),
            aggregate, mappable, geo_name, domains:{gdp_pct, tension, debt_pct,
            inflation_pp, unemployment_pp, crisis_years, crisis_added}}]
leaders:  top-K by score        laggards: bottom-K by score
geo:      {domains:[gdp_pct,tension,debt_pct,crisis_years], countries:[…mappable…]}
```

**Map (Leaflet).** `geo.countries[].geo_name` joins to `data/world_countries.geojson`
by feature `name` (the app embeds the vendored `vendor/leaflet/` + the local geojson
in a `WKWebView` → a true choropleth by the selected domain). Regional aggregates
(`AG_*` / "Rest of …") and tiny states absent from the geojson carry `mappable:false`
— shown in the lists, off the map.

> The per-domain Δ are model outputs; the composite **score** (`gdp_pct − 60·tension
> − 0.5·debt_pct − 3·crisis_added`) is a tunable presentation **heuristic** for
> ranking, not a validated index.

## Projection shapes (`gim2.projections`)

* **fan** `{metric, years, p5, p25, p50, p75, p95, mean}` (Fig. 4).
* **scenario_delta** `{metrics:[{metric, delta:<fan>, baseline_p50[], scenario_p50[]}], zero_line:true}` (Fig. 6–9 / E6).
* **dose_response** `{metric, x:[mag], delta[], scenario[], baseline}` (Fig. 6–9).
* **tornado** `{metric, params:[{name, mu_star, mu, sigma}]}` (Fig. 3).
* **conflict_auc** `{auc, ci95, p_value, comparison}` (Fig. 2b).

## Reproducibility

Each run also carries `equiv_cli` — the exact `python3 -m gim2 …` that reproduces
it. `tests/test_gim2_engine.py` asserts `compute_* == CLI == engine`.
