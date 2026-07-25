# Global Integrated Model — GIM18

A year-by-year simulation of the world as interacting countries (~50 countries plus regional
groupings), integrating **economy, climate, climate damage, resources, society, politics,
geopolitics, culture, risk/crises and finance** into one model. It is built for scenario
exploration and uncertainty-aware analysis — "what tends to happen, and how confident can we be" —
not pinpoint forecasting.

**New here? Start with [`docs/MODEL_LAYERS.md`](docs/MODEL_LAYERS.md)** — a plain-language tour of
every layer, what it can do, and its limits. For where the model stands and what comes next, see
[`docs/ROADMAP.md`](docs/ROADMAP.md).

**Want to play?** There's a live browser game built on the model — **God Mode**, playable now at
**[godmode-rwhp.onrender.com](https://godmode-rwhp.onrender.com/)** (no install). See
[Play online](#play-online--god-mode) below.

## What's inside

Every run starts from one **validated 2023 baseline** — 57 actors covering essentially all of world
output (GDP ≈ $107T, population ≈ 8.06B, CO₂ ≈ 38 Gt), reconciled against World Bank / UN / Global
Carbon Project to within ~1%.

- **A closed, objective economic core.** A calibrated capital–energy (nested-CES) production
  function, cost-minimising energy demand, energy/resource and capital markets that clear by price,
  and a closed stock-flow-consistent bank balance sheet (money = deposits = loans). Long-run growth
  and emissions are development-structured — poorer economies catch up, richer economies cut CO₂/GDP
  faster — both fit to the 2015–2023 World Bank panel.
- **Grounded against the record.** The economy reproduces 2015–2023 national-income history; the
  climate matches mainstream science (ECS ≈ 3.0, the 1990–2023 warming/carbon record). Conflict risk
  is validated against the standard armed-conflict record (AUC ≈ 0.74). Cost of carbon is reported
  honestly across horizons and discount rates (~$22–$89/tCO₂).
- **Real spatial coupling.** Shocks propagate over a literature-anchored trade-gravity graph, with
  switchable conflict/tension/climate contagion.
- **Weak-signal detection.** A dedicated module (Mahalanobis anomaly + structural-break +
  critical-slowing-down) for what-if and early-warning analysis (`gim/weak_signal.py`).
- **Honest about uncertainty.** Deep-uncertainty mechanisms (carbon-cycle feedbacks, fat-tailed
  crises, growth-effect damages) are switches, **off by default**, so the headline run stays anchored
  and they are explored separately.

Headline backtest: GDP error ≈ 0.60, global CO₂ error ≈ 0.94, temperature error ≈ 0.145. Full
methodology and the calibration ledger are in [Documentation](#documentation).

## Play online — God Mode

A live, playable browser front end built on the model: **God Mode** —
**[godmode-rwhp.onrender.com](https://godmode-rwhp.onrender.com/)**. Pick a country and steer it
year by year while the deterministic engine runs the rest of the world; no install, nothing to build.
It's the hosted, public-facing take on the "play as a country" role-play
([Ролевая игра акторов](#native-app--gim2-gim2)) — a single narrative trajectory, not an uncertainty
ensemble, and not validated the way the deterministic core is. Hosted on a free Render tier, so the
first load after idle can take ~30 s to wake.

## Install

```bash
pip install -e .          # Python 3.10+
```

## Quick start

```bash
python3 -m gim                                   # core multi-year world simulation
python3 -m gim question "Will Red Sea tensions escalate?"
python3 -m gim game --case scenarios/maritime_pressure_game.json --dashboard
python3 -m gim metrics --agents Iran "United States"
python3 -m gim calibrate --suite operational_v1
```

Subcommands: `world`, `question`, `game`, `hybrid`, `metrics`, `calibrate`, `brief`, `console`.
Full command reference: [`COMMAND_REFERENCE.md`](COMMAND_REFERENCE.md). Run artifacts are written to
timestamped folders under `results/` (each with a `run_manifest.json`).

## Native app — GIM2 (`gim2/`)

The graphical shell is a **native macOS app** (SwiftUI, macOS 13+), not a browser page: a small,
deterministic Python engine (`python3 -m gim2 engine`, HTTP+SSE over loopback, schema `gim-engine/2`)
sits behind a Situation-Room-style interface with six areas —

<table>
<tr>
<td width="50%">

**Ассистент** — describe a scenario in words; the map shows per-country winners/losers.

![Ассистент — analytical result](gim2/docs/screenshots/assistant.png)

</td>
<td width="50%">

**Экспертный режим** — direct control over every lever, horizon, and ensemble size.

![Экспертный режим — run configuration](gim2/docs/screenshots/expert_mode.png)

</td>
</tr>
</table>

- **Ассистент** — natural-language front end. Describe a scenario in words; the assistant maps it to
  grounded levers or a composed scenario, runs the deterministic engine, and returns a verdict,
  tipping point, per-domain cascade, and per-country outcomes. All numbers come from the engine, never
  the language model. Every conversation is a named, on-disk session (survives a restart) with a raw
  agent-trace view for debugging why a given tool was routed.
- **Экспертный режим** — direct control: Сценарий (levers vs. baseline), Ансамбли (Monte-Carlo fans),
  Отклик (dose-response), Чувствительность (Morris screening, all 33 calibrated priors), Сигналы
  (Mahalanobis anomaly / structural-break / critical-slowing-down scan), and **Ролевая игра акторов**
  (below). Every chart shows the equivalent `python3 -m gim2 …` CLI command for reproducibility.
- **Сравнение** — every run made anywhere in the app (Экспертный режим or Ассистент) is written to disk
  individually and stays available across restarts; pick up to three against the validated baseline for
  a Δ matrix, with a PDF export per run or for the comparison as a whole.
- **Документация** / **Инструкции** — architecture, modules, data sources and the LLM tool-calling path
  on one tab; a practical analyst's guide (when to use which mode, how to read every chart, what's
  validated vs. exploratory) on the other.
- **Валидация** — retro-backtest RMSE, ensemble fans, conflict AUC, and Morris sensitivity, drawn live
  from the running engine (not static images).

**Ролевая игра акторов ("play as a country").** The one deliberate exception to "the engine is
deterministic, the LLM only narrates": pick up to five actors and an LLM compiles each one's multi-year
governing **doctrine** — a 9-dimensional vector (escalation bias, trade openness, sanctions tolerance,
mediation openness, …) derived from that country's own state — instead of the engine's scripted policy;
every other actor keeps running the scripted policy, so the run costs one LLM call per selected actor,
not per year or per country. A persona (protectionist hawk, dove, technocrat) can additively bias the
compiled doctrine. It reuses whichever LLM connection is already configured for the Assistant (a local
Ollama model or an OpenAI-compatible key); without one, doctrines fall back to a deterministic
heuristic. The point of the exercise is the per-year, per-actor decision log (what it did and, in its
own words, why) — a single trajectory, not an uncertainty ensemble, and explicitly **not** validated the
way the deterministic core is. The public **[God Mode](#play-online--god-mode)** web game is the hosted
version of this idea.

### Build & run

```bash
gim2/app/freeze/freeze_engine.sh   # PyInstaller-freeze the engine (~3 min, one-time; needs pyinstaller)
gim2/app/build_app.sh              # swift build -c release + assemble GIM18.app
gim2/app/make_dmg.sh               # (optional) wrap it in a drag-to-Applications GIM18-<ver>.dmg
open gim2/app/GIM18.app
```

`build_app.sh` embeds the frozen engine for a self-contained, offline app if
`gim2/app/Resources/gim-engine` exists (from the freeze step above); otherwise the app falls back to
launching `python3 -m gim2 engine` from the repo (dev mode). Engine bridge contract and CLI reference:
[`gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md`](gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md),
[`gim2/README.md`](gim2/README.md).

## Documentation

Full index: [`docs/README.md`](docs/README.md). Key entry points:

- Plain-language overview — [`docs/MODEL_LAYERS.md`](docs/MODEL_LAYERS.md)
- Where it stands / next steps — [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Model specification & methodology — [`docs/GIM18_UNIFIED_MODEL_SPEC.md`](docs/GIM18_UNIFIED_MODEL_SPEC.md), [`docs/MODEL_METHODOLOGY.md`](docs/MODEL_METHODOLOGY.md)
- Calibration ledger — [`docs/CALIBRATION_REFERENCE.md`](docs/calibration/CALIBRATION_REFERENCE.md)
- Data contract — [`docs/agent_state_data_contract.md`](docs/agent_state_data_contract.md)

## Tests

```bash
python3 -m unittest discover -s tests             # full suite
./scripts/run_validation_package_gim18.sh         # release validation (non-LLM)
```

## Version & history

Current release, per-version detail, and the full v17→v18 lineage live in
[`CHANGELOG.md`](CHANGELOG.md).
