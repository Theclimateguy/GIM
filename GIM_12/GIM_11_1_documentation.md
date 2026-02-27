# GIM_11_1 Multi-Agent World Model

## Overview
`gim_11_1` is an endogenous multi-agent world simulation with yearly steps.
Each country-agent evolves through economy, resources, social dynamics, climate, and geopolitics.

Code layout:
- `GIM_11_1.py`: top-level wrapper entrypoint.
- `gim_11_1/`: modular package (core logic).

## Repository Setup (Git-friendly)
From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

Optional (only if you plan to use LLM mode):

```bash
pip install requests
```

Optional (for dashboards):

```bash
pip install matplotlib
```

## Run Commands
Run from repository root:

```bash
cd .
```

### 1. Fast deterministic baseline (no LLM)

```bash
POLICY_MODE=simple SIM_YEARS=5 SIM_SEED=7 python3 -m gim_11_1
```

### 1b. Deterministic growth-seeking baseline (no LLM)

```bash
POLICY_MODE=growth SIM_YEARS=5 SIM_SEED=7 python3 -m gim_11_1
```

### 2. Baseline with stochastic shocks disabled (diagnostic)

```bash
POLICY_MODE=simple SIM_YEARS=5 SIM_SEED=7 DISABLE_EXTREME_EVENTS=1 python3 -m gim_11_1
```

### 3. LLM mode

```bash
export DEEPSEEK_API_KEY='your_key_here'
POLICY_MODE=llm SIM_YEARS=5 python3 -m gim_11_1
```

### 4. Wrapper entrypoint (equivalent)

```bash
POLICY_MODE=simple SIM_YEARS=5 python3 GIM_11_1.py
```

### 5. Reduce console detail (optional)

```bash
POLICY_MODE=simple SIM_YEARS=5 VERBOSE_COUNTRY_DETAILS=0 python3 -m gim_11_1
```

### 6. Build a visual dashboard from the latest log

```bash
python3 visual.py --logs-dir logs
```

This generates a `*_dashboard.png` next to the latest log file. The dashboard plots 20 countries (excluding "Rest of World").

## Inputs and Outputs
Input:
- `agent_states.csv` (expected in current working directory).

Outputs:
- `logs/GIM_11_1_<timestamp>_t0-tN.csv`
- `logs/GIM_11_1_<timestamp>_actions.csv`
- `logs/GIM_11_1_<timestamp>_institutions.csv`

## Environment Variables
- `POLICY_MODE`: `simple` | `growth` | `llm` | `auto`
- `SIM_YEARS`: number of simulated years (default `5`)
- `SIM_SEED`: integer RNG seed for reproducibility
- `DISABLE_EXTREME_EVENTS=1`: disables stochastic climate extreme events
- `VERBOSE_COUNTRY_DETAILS=0`: compact verbose mode (hides per-country foreign detail lines)
- `LLM_TIMEOUT_SEC`: per-request timeout in seconds (default `120`)
- `LLM_MAX_RETRIES`: retry count on LLM request failures (default `2`)
- `LLM_RETRY_BACKOFF_SEC`: retry backoff base in seconds (default `2.0`)
- `DEEPSEEK_API_KEY`: required for `POLICY_MODE=llm`
- `USE_SIMPLE_POLICIES=1`: hard override to disable LLM
- `NO_LLM=1`: hard override to disable LLM

## Module Map
- `gim_11_1/core.py`: dataclasses, types, constants.
- `gim_11_1/political_dynamics.py`: endogenous political state, coalitions, sanctions, trade barriers, and relation updates.
- `gim_11_1/institutions.py`: global institutions, signals, and reports.
- `gim_11_1/world_factory.py`: world construction from CSV.
- `gim_11_1/observation.py`: observation builder.
- `gim_11_1/memory.py`: agent memory and summaries.
- `gim_11_1/policy.py`: simple/growth policies, LLM policy, policy selection helpers.
- `gim_11_1/actions.py`: domestic policy and trade effects.
- `gim_11_1/geopolitics.py`: sanctions and security interactions.
- `gim_11_1/resources.py`: reserves and global resource prices.
- `gim_11_1/climate.py`: climate state and extreme events.
- `gim_11_1/economy.py`: GDP, capital, finance, interest.
- `gim_11_1/metrics.py`: comparative and risk metrics.
- `gim_11_1/social.py`: social evolution and crisis checks.
- `gim_11_1/simulation.py`: step execution and simulation loop.
- `gim_11_1/logging_utils.py`: run IDs and CSV logging.
- `gim_11_1/cli.py`: command-line runtime.

## Programmatic Usage
```python
import gim_11_1 as m

world = m.make_world_from_csv('agent_states.csv')
policies = m.make_policy_map(world.agents.keys(), mode='simple')

for _ in range(5):
    world = m.step_world(world, policies)

print(world.time)
```

## Common API
- `make_world_from_csv(path='agent_states.csv')`
- `make_policy_map(agent_ids, mode='auto')`
- `step_world(world, policies, memory=None, enable_extreme_events=True, apply_political_filters=True, action_log=None, institution_log=None)`
- `step_world_verbose(world, policies, enable_extreme_events=True, detailed_output=True, action_log=None, institution_log=None)`
- `run_simulation(world, policies, years, enable_extreme_events=True, detailed_output=True, action_log=None, institution_log=None)`
- `log_world_to_csv(world_history, sim_id, base_dir='logs')`
- `log_actions_to_csv(action_records, sim_id, base_dir='logs')`
- `log_institutions_to_csv(reports, sim_id, base_dir='logs')`
- `make_sim_id(name)`

## Notes
- Model growth includes endogenous dynamics plus a small baseline TFP drift.
- Climate uses a 4-pool carbon cycle + radiative forcing + 2-layer energy balance model (ECS capped at 4C).
- Emissions are tied to GDP, tech, energy efficiency, and fuel/climate policies, with a global decarbonization trend.
- Climate risk targets include baseline vulnerability (water stress + inequality) plus temperature response.
- Extreme events can impose a 2-year output penalty; adaptation spending improves resilience.
- Geopolitics includes conflict propagation via trade ties and alliance blocks, mitigated by SecurityOrgs.
- Active conflicts persist and end on exhaustion (resource depletion, population loss, or major GDP contraction).
- Sanctions require minimum support to activate and persist for a short minimum duration.
- Endogenous escalation can trigger limited security incidents under high conflict/resource stress.
- LLM policy prompt includes a coercion ladder to avoid overly passive foreign policy.
- Climate extreme events are calibrated and can be toggled for diagnostics.
- The actions log includes realized trade records (`trade_realized`) in addition to trade intents.
