# V10.3 Multi-Agent World Model

## Overview
`V10_3_prod` is an endogenous multi-agent world simulation with yearly steps.
Each country-agent evolves through economy, resources, social dynamics, climate, and geopolitics.

Code layout:
- `V10_3_prod.py`: top-level wrapper entrypoint.
- `v10_3_prod/`: modular package (core logic).

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

## Run Commands
Run from repository root:

```bash
cd .
```

### 1. Fast deterministic baseline (no LLM)

```bash
POLICY_MODE=simple SIM_YEARS=5 SIM_SEED=7 python3 -m v10_3_prod
```

### 2. Baseline with stochastic shocks disabled (diagnostic)

```bash
POLICY_MODE=simple SIM_YEARS=5 SIM_SEED=7 DISABLE_EXTREME_EVENTS=1 python3 -m v10_3_prod
```

### 3. LLM mode

```bash
export DEEPSEEK_API_KEY='your_key_here'
POLICY_MODE=llm SIM_YEARS=5 python3 -m v10_3_prod
```

### 4. Wrapper entrypoint (equivalent)

```bash
POLICY_MODE=simple SIM_YEARS=5 python3 V10_3_prod.py
```

### 5. Reduce console detail (optional)

```bash
POLICY_MODE=simple SIM_YEARS=5 VERBOSE_COUNTRY_DETAILS=0 python3 -m v10_3_prod
```

## Inputs and Outputs
Input:
- `agent_states.csv` (expected in current working directory).

Outputs:
- `logs/V10_3_prod_<timestamp>_t0-tN.csv`

## Environment Variables
- `POLICY_MODE`: `simple` | `llm` | `auto`
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
- `v10_3_prod/core.py`: dataclasses, types, constants.
- `v10_3_prod/world_factory.py`: world construction from CSV.
- `v10_3_prod/observation.py`: observation builder.
- `v10_3_prod/memory.py`: agent memory and summaries.
- `v10_3_prod/policy.py`: simple policy, LLM policy, policy selection helpers.
- `v10_3_prod/actions.py`: domestic policy and trade effects.
- `v10_3_prod/geopolitics.py`: sanctions and security interactions.
- `v10_3_prod/resources.py`: reserves and global resource prices.
- `v10_3_prod/climate.py`: climate state and extreme events.
- `v10_3_prod/economy.py`: GDP, capital, finance, interest.
- `v10_3_prod/metrics.py`: comparative and risk metrics.
- `v10_3_prod/social.py`: social evolution and crisis checks.
- `v10_3_prod/simulation.py`: step execution and simulation loop.
- `v10_3_prod/logging_utils.py`: run IDs and CSV logging.
- `v10_3_prod/cli.py`: command-line runtime.

## Programmatic Usage
```python
import V10_3_prod as m

world = m.make_world_from_csv('agent_states.csv')
policies = m.make_policy_map(world.agents.keys(), mode='simple')

for _ in range(5):
    world = m.step_world(world, policies)

print(world.time)
```

## Common API
- `make_world_from_csv(path='agent_states.csv')`
- `make_policy_map(agent_ids, mode='auto')`
- `step_world(world, policies, memory=None, enable_extreme_events=True)`
- `step_world_verbose(world, policies, enable_extreme_events=True, detailed_output=True)`
- `run_simulation(world, policies, years, enable_extreme_events=True, detailed_output=True)`
- `log_world_to_csv(world_history, sim_id, base_dir='logs')`
- `make_sim_id(name)`

## Notes
- Model growth is endogenous (no exogenous trend term).
- Climate extreme events are calibrated and can be toggled for diagnostics.
