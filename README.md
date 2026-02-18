# GIM_11_1

Global integrated model is an agent-based integrated assessment model simulates the co-evolution of 20 country economies with global climate, resource, and social systems over multi-year horizons, combining neoclassical growth theory (Cobb-Douglas production with endogenous TFP driven by R&D and trade spillovers) with Earth system dynamics (carbon cycle with airborne fraction enforcement, temperature inertia, and biodiversity feedbacks) and sociopolitical mechanisms (trust-tension coupling, inequality-driven regime instability, and debt crisis contagion through trade networks). 

Each annual time step executes a 12-stage update sequence: policy generation → sanctions/security actions → domestic spending → trade with global balance enforcement → resource depletion and price adjustment → climate damage and extreme events → GDP/capital accumulation → debt service with nonlinear spreads → population change driven by food availability and prosperity → social dynamics with Gini evolution → metrics and memory updates. 

External inputs are limited to initial country states (GDP, population, resources, culture), policy choices (simple rule-based or LLM-generated), and stochastic climate shocks; all macroeconomic outcomes (growth, capital, trade flows), resource prices, emissions trajectories, temperature, biodiversity loss, debt crises, social unrest, and geopolitical tensions emerge endogenously from the interaction of modules, making the model suitable for scenario analysis of climate-economy-society feedbacks, policy stress testing, and exploring emergent global crises.

Production snapshot for the Global Interaction Model (GIM_11_1).

Documentation:
- `GIM_11_1_documentation.md` (module overview)
- `methodic.md` (full mechanics map with equations)

## Quick Run
```bash
POLICY_MODE=simple SIM_YEARS=5 python -m gim_11_1
```

## LLM Run
```bash
export DEEPSEEK_API_KEY="..."
POLICY_MODE=llm SIM_YEARS=3 python -m gim_11_1
```

## Inputs and Outputs
Input:
- `agent_states.csv`

Outputs:
- CSV logs in `logs/`
- Filename format: `GIM_11_1_<timestamp>_t0-tN.csv`

## Notes
- Climate uses a carbon-cycle + radiative forcing + 2-layer energy balance model; emissions depend on GDP, tech, energy efficiency, and policies.

## Archive
Legacy V10.3 sources and docs are preserved in `archive/`.
