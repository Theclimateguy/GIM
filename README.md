# GIM V10.3

Production snapshot for the Global Interaction Model (V10.3).

Documentation:
- `V10_3_prod_documentation.md` (module overview)
- `methodic.md` (full mechanics map with equations)

## Quick Run
```bash
POLICY_MODE=simple SIM_YEARS=5 python -m v10_3_prod
```

## LLM Run
```bash
export DEEPSEEK_API_KEY="..."
POLICY_MODE=llm SIM_YEARS=3 python -m v10_3_prod
```

## Inputs and Outputs
Input:
- `agent_states.csv`

Outputs:
- CSV logs in `logs/`
- Filename format: `V10_3_prod_<timestamp>_t0-tN.csv`
